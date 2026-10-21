import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from probe_bluez import Profile, run_connection


class SendTimingTests(unittest.TestCase):
    def test_known_device_connects_without_discovery_or_polling(self):
        bus, adapter, manager, objects, device, loop = (Mock() for _ in range(6))
        path = '/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF'
        proxies = {'/': objects, '/org/bluez': manager, '/org/bluez/hci0': adapter, path: device}
        bus.get_object.side_effect = lambda service, path: proxies[path]
        objects.GetManagedObjects.return_value = {path: {}}
        profile = SimpleNamespace(connected=True, error=None, query=None, print_test=False,
                                  feed_test=False, job=None, close=Mock(), fail=Mock())
        with patch('probe_bluez.dbus.SystemBus', return_value=bus), \
                patch('probe_bluez.dbus.Interface', side_effect=lambda obj, interface: obj), \
                patch('probe_bluez.GLib.MainLoop', return_value=loop), \
                patch('probe_bluez.GLib.timeout_add_seconds', return_value=10003), \
                patch('probe_bluez.GLib.timeout_add') as poll:
            self.assertEqual(run_connection('AA:BB:CC:DD:EE:FF', 'hci0', 10,
                                            lambda bus, loop: profile), 0)
        device.ConnectProfile.assert_called_once()
        adapter.StartDiscovery.assert_not_called()
        poll.assert_not_called()

    def test_partial_write_keeps_unsent_bytes(self):
        state = SimpleNamespace(stream=Mock(), pending=b'abcdef', chunks=[])
        state.stream.send.return_value = 2
        with patch('probe_bluez.GLib.timeout_add') as timer:
            self.assertTrue(Profile.write(state, None, None))
        self.assertEqual(state.pending, b'cdef')
        timer.assert_not_called()

    def test_delay_only_before_page_feed(self):
        for chunks, expected in [([b'\x1b\x19\x01\x01\x30'], 0),
                                 ([b'\x1b\x4a\x00', b'\x1b\x69'], 2000),
                                 ([b'\x1b\x69', b'\x1b\x4a\x00'], 2000),
                                 ([b'\x1b\x69'], 0), ([b'\x1b\x4a\x00'], 0)]:
            with self.subTest(chunks=chunks):
                next_chunk = chunks[0]
                state = SimpleNamespace(stream=Mock(), pending=b'\xff',
                                        chunks=list(chunks), paced=False, pause_ms=20,
                                        job=True, finish_delay_ms=2000,
                                        start_write=Mock(), write_watch=1)
                state.stream.send.return_value = 1
                with patch('probe_bluez.GLib.timeout_add', return_value=42) as timer, patch('builtins.print'):
                    self.assertFalse(Profile.write(state, None, None))
                timer.assert_called_once_with(expected, state.start_write)
                self.assertEqual(state.pending, next_chunk)

    def test_send_completion_schedules_finish_without_waiting_for_messages(self):
        state = SimpleNamespace(stream=Mock(), pending=b'\xff', chunks=[],
                                operation=Mock(return_value='print-png'),
                                total_bytes=1, query=None, finish_send=Mock(),
                                finish_timer=None)
        state.stream.send.return_value = 1
        with patch('probe_bluez.GLib.timeout_add', return_value=123) as timer, patch('builtins.print'):
            self.assertFalse(Profile.write(state, None, None))
        self.assertTrue(state.sent)
        self.assertIsNone(state.write_watch)
        timer.assert_called_once_with(200, state.finish_send)

    def test_query_read_schedules_finish_after_receiving_response(self):
        state = SimpleNamespace(stream=Mock(), received=bytearray(),
                                query='status', finish_send=Mock(), finish_timer=None)
        state.stream.recv.return_value = bytes.fromhex('1b060003')
        with patch('probe_bluez.GLib.timeout_add', return_value=456) as timer, patch('builtins.print'):
            self.assertTrue(Profile.read(state, None, None))
        self.assertEqual(state.received, bytes.fromhex('1b060003'))
        timer.assert_called_once_with(200, state.finish_send)


if __name__ == '__main__':
    unittest.main()
