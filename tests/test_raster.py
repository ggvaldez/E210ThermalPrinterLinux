import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from e210_raster import encode_rows, test_pattern, test_pattern_chunks


class RasterTests(unittest.TestCase):
    def test_paced_chunks_preserve_original_bytes(self):
        chunks = test_pattern_chunks()
        self.assertEqual(len(chunks), 6 + 152 + 2)
        self.assertEqual(b''.join(chunks), test_pattern()[0])
        self.assertEqual(chunks[-2:], [bytes.fromhex('1b69'), bytes.fromhex('1b4a00')])

    def test_java_row_vectors(self):
        self.assertEqual(encode_rows(bytes.fromhex('00800100'), 32, 1), bytes.fromhex('1b190103018001'))
        self.assertEqual(encode_rows(bytes(4), 32, 1), bytes.fromhex('1b19010104'))
        self.assertEqual(encode_rows(bytes.fromhex('ffffffff'), 32, 1), bytes.fromhex('1b19010500ffffffff'))

    def test_full_pattern_roundtrip(self):
        packet, pbm = test_pattern()
        self.assertTrue(packet.startswith(bytes.fromhex('1c2106 1b350000 1b340000 1c2500 1b33 1b299900f401c80000')))
        self.assertTrue(packet.endswith(bytes.fromhex('1b691b4a00')))
        data = packet[25:-5]
        restored = bytearray()
        for _ in range(152):
            self.assertEqual(data[:3], bytes.fromhex('1b1901'))
            size, offset = data[3] - 1, data[4]
            restored.extend(bytes(offset) + data[5:5 + size] + bytes(48 - offset - size))
            data = data[5 + size:]
        self.assertEqual(data, b'')
        self.assertEqual(bytes(restored), pbm.split(b'\n', 2)[2])


if __name__ == '__main__':
    unittest.main()
