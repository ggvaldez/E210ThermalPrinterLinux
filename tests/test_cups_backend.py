import io
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cups'))
from backend_e210 import (
    CUPS_BACKEND_FAILED,
    CUPS_BACKEND_OK,
    CUPS_BACKEND_RETRY,
    extract_target_address,
    main as backend_main,
    run_discovery,
)


class CupsBackendTests(unittest.TestCase):
    def test_run_discovery_emits_auto_and_registered(self):
        def device(name, address):
            return {'org.bluez.Device1': {'Name': name, 'Address': address}}

        objects = {
            '/org/bluez/hci0/dev_AA': device('E210', 'AA:BB:CC:DD:EE:FF'),
            '/org/bluez/hci0/dev_OTHER': device('Headphones', '11:22:33:44:55:66'),
        }

        mock_bus = Mock()
        mock_manager = Mock()
        mock_manager.GetManagedObjects.return_value = objects
        mock_bus.get_object.return_value = mock_manager

        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout, \
                patch('dbus.SystemBus', return_value=mock_bus), \
                patch('dbus.Interface', return_value=mock_manager):
            code = run_discovery()

        self.assertEqual(code, CUPS_BACKEND_OK)
        output = mock_stdout.getvalue()
        self.assertIn('direct e210://auto', output)
        self.assertIn('direct e210://AA:BB:CC:DD:EE:FF', output)
        self.assertNotIn('11:22:33:44:55:66', output)

    def test_extract_target_address_explicit_mac(self):
        addr = extract_target_address('e210://AA:BB:CC:DD:EE:FF')
        self.assertEqual(addr, 'AA:BB:CC:DD:EE:FF')

    def test_extract_target_address_rejects_invalid(self):
        with patch('sys.stderr', new_callable=io.StringIO):
            self.assertIsNone(extract_target_address('invalid://uri'))
            self.assertIsNone(extract_target_address('e210://bad_mac'))
            self.assertIsNone(extract_target_address(''))

    def test_extract_target_address_auto_resolves(self):
        with patch('e210_discovery.discover_address', return_value='AA:BB:CC:DD:EE:FF'):
            addr = extract_target_address('e210://auto')
        self.assertEqual(addr, 'AA:BB:CC:DD:EE:FF')

    def test_backend_main_discovery_mode(self):
        with patch('sys.argv', ['e210']), \
                patch('backend_e210.run_discovery', return_value=CUPS_BACKEND_OK) as mock_disc:
            code = backend_main()
            self.assertEqual(code, CUPS_BACKEND_OK)
            mock_disc.assert_called_once()

    def test_backend_main_print_mode_success(self):
        payload = b'\x1c\x21\x06test'
        with patch('sys.argv', ['e210', '1', 'guest', 'Job', '1', '']), \
                patch.dict('os.environ', {'DEVICE_URI': 'e210://AA:BB:CC:DD:EE:FF'}), \
                patch('sys.stdin.buffer.read', return_value=payload), \
                patch('probe_bluez.run_connection', return_value=0) as mock_connect, \
                patch('sys.stderr'):
            code = backend_main()
            self.assertEqual(code, CUPS_BACKEND_OK)
            self.assertEqual(mock_connect.call_args.args[0], 'AA:BB:CC:DD:EE:FF')

    def test_backend_main_print_mode_failure_returns_retry(self):
        payload = b'\x1c\x21\x06test'
        with patch('sys.argv', ['e210', '1', 'guest', 'Job', '1', '']), \
                patch.dict('os.environ', {'DEVICE_URI': 'e210://AA:BB:CC:DD:EE:FF'}), \
                patch('sys.stdin.buffer.read', return_value=payload), \
                patch('probe_bluez.run_connection', return_value=1), \
                patch('sys.stderr'):
            code = backend_main()
            self.assertEqual(code, CUPS_BACKEND_RETRY)


if __name__ == '__main__':
    unittest.main()
