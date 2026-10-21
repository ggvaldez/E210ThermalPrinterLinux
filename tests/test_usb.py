import ctypes as ct
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from e210_usb import (PID, VID, USBConnection, USBError, USBPrinter,
                      find_usb_printers, select_usb_printer, send_usb, validate_selector)


class FakeUSB:
    def __init__(self):
        self.devices = (ct.c_void_p * 1)(42)
        self.libusb_init = Mock(side_effect=self.init)
        self.libusb_exit = Mock()
        self.libusb_get_device_list = Mock(side_effect=self.device_list)
        self.libusb_free_device_list = Mock()
        self.libusb_get_bus_number = Mock(return_value=1)
        self.libusb_get_device_address = Mock(return_value=28)
        self.libusb_get_device_descriptor = Mock(side_effect=self.descriptor)
        self.libusb_open = Mock(side_effect=self.open)
        self.libusb_close = Mock()
        self.libusb_set_auto_detach_kernel_driver = Mock(return_value=0)
        self.libusb_claim_interface = Mock(return_value=0)
        self.libusb_release_interface = Mock(return_value=0)
        self.libusb_error_name = Mock(return_value=b'USB_TEST_ERROR')
        self.libusb_bulk_transfer = Mock(side_effect=self.transfer)
        self.transfers = []
        self.partial = None
        self.transfer_error = 0

    def init(self, context):
        context._obj.value = 1
        return 0

    def device_list(self, context, result):
        ct.cast(result, ct.POINTER(ct.POINTER(ct.c_void_p)))[0] = self.devices
        return 1

    def descriptor(self, device, result):
        result._obj.vendor, result._obj.product = VID, PID
        return 0

    def open(self, device, result):
        result._obj.value = 7
        return 0

    def transfer(self, handle, endpoint, data, length, transferred, timeout):
        count = length if self.partial is None else min(length, self.partial)
        transferred._obj.value = count
        self.transfers.append((endpoint, ct.string_at(data, count)))
        return self.transfer_error


class USBTests(unittest.TestCase):
    def test_discovery_filters_ids_and_tolerates_removed_devices(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, vendor, product in [('1-3', '08c5', '4001'), ('1-4', '08c5', '4002')]:
                device = root / name
                device.mkdir()
                for field, value in {'idVendor': vendor, 'idProduct': product,
                                     'busnum': '1', 'devnum': '28', 'product': 'YC3121'}.items():
                    (device / field).write_text(value)
            (root / '1-3:1.0').mkdir()
            self.assertEqual(find_usb_printers(root), [USBPrinter(1, 28, 'YC3121')])

    def test_selection_requires_unambiguous_device(self):
        first, second = USBPrinter(1, 28, 'E210'), USBPrinter(2, 3, 'E210')
        with patch('e210_usb.find_usb_printers', return_value=[first, second]):
            self.assertEqual(select_usb_printer('2:3'), second)
            with self.assertRaisesRegex(USBError, 'Multiple'):
                select_usb_printer()
        with patch('e210_usb.find_usb_printers', return_value=[]):
            with self.assertRaisesRegex(USBError, 'No E210'):
                select_usb_printer()
        for selector in ('0:1', '1:128', '256:1', '001/028', '1:2junk'):
            with self.subTest(selector=selector), self.assertRaises(ValueError):
                validate_selector(selector)

    def test_native_transfer_preserves_partial_writes_and_releases_device(self):
        lib = FakeUSB()
        lib.partial = 2
        with patch('e210_usb._load_libusb', return_value=lib):
            with USBConnection(USBPrinter(1, 28, 'E210')) as connection:
                connection.send(b'abcdefg')
        self.assertEqual(lib.transfers, [(1, b'ab'), (1, b'cd'), (1, b'ef'), (1, b'g')])
        lib.libusb_release_interface.assert_called_once()
        lib.libusb_close.assert_called_once()
        lib.libusb_exit.assert_called_once()

    def test_transfer_error_does_not_resend_and_still_releases(self):
        lib = FakeUSB()
        lib.partial, lib.transfer_error = 2, -7
        with patch('e210_usb._load_libusb', return_value=lib), self.assertRaises(USBError):
            with USBConnection(USBPrinter(1, 28, 'E210')) as connection:
                connection.send(b'abcdefg')
        self.assertEqual(lib.transfers, [(1, b'ab')])
        lib.libusb_release_interface.assert_called_once()
        lib.libusb_close.assert_called_once()
        lib.libusb_exit.assert_called_once()

    def test_claim_failure_closes_without_releasing_unclaimed_interface(self):
        lib = FakeUSB()
        lib.libusb_claim_interface.return_value = -6
        with patch('e210_usb._load_libusb', return_value=lib), self.assertRaisesRegex(USBError, 'Another application'):
            with USBConnection(USBPrinter(1, 28, 'E210')):
                self.fail('Claim unexpectedly succeeded')
        lib.libusb_release_interface.assert_not_called()
        lib.libusb_close.assert_called_once()
        lib.libusb_exit.assert_called_once()

    def test_send_preserves_qlabel_bytes_and_optional_copy_delays(self):
        chunks = [b'row', b'\x1bi', b'\x1bJ\0'] * 2
        printer = USBPrinter(1, 28, 'E210')
        with patch('e210_usb.select_usb_printer', return_value=printer), \
                patch('e210_usb.USBConnection') as connection, patch('e210_usb.time.sleep') as sleep:
            send_usb(chunks)
            connection.return_value.__enter__.return_value.send.assert_called_once_with(b''.join(chunks))
            sleep.assert_not_called()
        with patch('e210_usb.select_usb_printer', return_value=printer), \
                patch('e210_usb.USBConnection') as connection, patch('e210_usb.time.sleep') as sleep:
            send_usb(chunks, finish_delay_ms=250)
            self.assertEqual(sleep.call_count, 2)
            self.assertEqual(connection.return_value.__enter__.return_value.send.call_count, 6)

    def test_cli_usb_does_not_import_bluez(self):
        from print_png import main
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / 'input.png'
            Image.new('1', (384, 8), 1).save(image)
            with patch('sys.argv', ['print_png', str(image), '--transport', 'usb']), \
                    patch('e210_usb.send_usb', return_value=USBPrinter(1, 28, 'E210')) as send, \
                    patch.dict('sys.modules', {'probe_bluez': None, 'dbus': None}), \
                    patch('sys.stdout', new_callable=io.StringIO):
                self.assertEqual(main(), 0)
                self.assertEqual(send.call_args.args[0][0], bytes.fromhex('1c210a'))
                self.assertEqual(send.call_args.args[0][-2:], [b'\x1bi', b'\x1bJ\0'])


if __name__ == '__main__':
    unittest.main()
