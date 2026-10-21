import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from print_png import discover_address, e210_candidates, main


class DiscoveryTests(unittest.TestCase):
    def test_registered_and_visible_e210_on_selected_adapter(self):
        def device(name, address, **extra):
            return {'org.bluez.Device1': {'Name': name, 'Address': address, **extra}}
        objects = {
            '/org/bluez/hci0/dev_A': device('E210', 'AA:AA:AA:AA:AA:AA', RSSI=-50),
            '/org/bluez/hci0/dev_B': device('E210', 'BB:BB:BB:BB:BB:BB'),
            '/org/bluez/hci1/dev_C': device('E210', 'CC:CC:CC:CC:CC:CC', RSSI=-40),
            '/org/bluez/hci0/dev_D': device('Other Printer', 'DD:DD:DD:DD:DD:DD', RSSI=-40),
            '/org/bluez/hci0/dev_E': device('e210', 'EE:EE:EE:EE:EE:EE', Connected=True),
        }
        self.assertEqual(e210_candidates(objects, '/org/bluez/hci0'),
                         ['AA:AA:AA:AA:AA:AA', 'BB:BB:BB:BB:BB:BB', 'EE:EE:EE:EE:EE:EE'])

    def test_no_devices(self):
        self.assertEqual(e210_candidates({}, '/org/bluez/hci0'), [])

    def test_registered_device_used_without_discovery(self):
        def device(name, address, **extra):
            return {'org.bluez.Device1': {'Name': name, 'Address': address, **extra}}
        objects = {
            '/org/bluez/hci0/dev_B': device('E210', 'BB:BB:BB:BB:BB:BB'),
        }
        mock_bus = Mock()
        mock_manager = Mock()
        mock_manager.GetManagedObjects.return_value = objects
        mock_adapter = Mock()

        def get_object(service, path):
            if path == '/':
                return mock_manager
            return mock_adapter

        mock_bus.get_object.side_effect = get_object
        with patch('dbus.SystemBus', return_value=mock_bus), \
                patch('dbus.Interface', side_effect=lambda obj, iface: obj), \
                patch('builtins.print'):
            address = discover_address('hci0')
        self.assertEqual(address, 'BB:BB:BB:BB:BB:BB')
        mock_adapter.StartDiscovery.assert_not_called()

    def test_dry_run_does_not_discover_or_print(self):
        from PIL import Image
        with patch('sys.argv', ['print_png.py', 'example.png', '--dry-run']), \
                patch('print_png.prepare_png', return_value=([b'example'], Image.new('1', (384, 8)))), \
                patch('print_png.discover_address') as discover, patch('builtins.print'):
            self.assertEqual(main(), 0)
        discover.assert_not_called()

    def test_discovered_address_is_used_for_printing(self):
        from PIL import Image
        address = 'AA:BB:CC:DD:EE:FF'
        with patch('sys.argv', ['print_png.py', 'example.png']), \
                patch('print_png.prepare_png', return_value=([b'example'], Image.new('1', (384, 8)))), \
                patch('print_png.discover_address', return_value=address) as discover, \
                patch('probe_bluez.run_connection', return_value=0) as connect, patch('builtins.print'):
            self.assertEqual(main(), 0)
        discover.assert_called_once_with('hci0')
        self.assertEqual(connect.call_args.args[:2], (address, 'hci0'))

    def test_explicit_address_skips_discovery(self):
        from PIL import Image
        address = 'AA:BB:CC:DD:EE:FF'
        with patch('sys.argv', ['print_png.py', 'example.png', '--address', address]), \
                patch('print_png.prepare_png', return_value=([b'example'], Image.new('1', (384, 8)))), \
                patch('print_png.discover_address') as discover, \
                patch('probe_bluez.run_connection', return_value=0) as connect, patch('builtins.print'):
            self.assertEqual(main(), 0)
        discover.assert_not_called()
        self.assertEqual(connect.call_args.args[:2], (address, 'hci0'))

    def test_discovery_failure_does_not_print(self):
        from PIL import Image
        with patch('sys.argv', ['print_png.py', 'example.png']), \
                patch('print_png.prepare_png', return_value=([b'example'], Image.new('1', (384, 8)))), \
                patch('print_png.discover_address', side_effect=ValueError('Multiple E210 devices found')), \
                patch('probe_bluez.run_connection') as connect, patch('builtins.print'), \
                patch('sys.stderr'), self.assertRaises(SystemExit) as failure:
            main()
        self.assertEqual(failure.exception.code, 1)
        connect.assert_not_called()


if __name__ == '__main__':
    unittest.main()
