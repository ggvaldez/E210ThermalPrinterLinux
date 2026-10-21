import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from probe_bluez import Profile


class SendTimingTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
