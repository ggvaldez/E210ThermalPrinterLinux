import struct
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from png_job import prepare_png


class PngTests(unittest.TestCase):
    def prepare(self, image, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.png'
            image.save(path)
            return prepare_png(path, **kwargs)

    def test_maximum_width_and_aspect_ratio(self):
        chunks, preview = self.prepare(Image.new('RGB', (768, 320), 'white'))
        self.assertEqual(preview.size, (384, 160))
        self.assertEqual(chunks[5], bytes.fromhex('1b29') + struct.pack('<HHHB', 161, 500, 200, 0))
        self.assertEqual(chunks[6:-2], [bytes.fromhex('1b19010130')] * 160)

    def test_transparent_black_is_white_paper(self):
        chunks, preview = self.prepare(Image.new('RGBA', (384, 2), (0, 0, 0, 0)))
        self.assertEqual(preview.getextrema(), (255, 255))
        self.assertEqual(chunks[6], bytes.fromhex('1b19010130'))

    def test_pixel_order_and_payload_polarity(self):
        image = Image.new('RGB', (384, 1), 'white')
        image.putpixel((0, 0), (0, 0, 0))
        image.putpixel((9, 0), (0, 0, 0))
        chunks, _ = self.prepare(image, threshold=128)
        self.assertEqual(chunks[6], bytes.fromhex('1b190103008040'))

    def test_threshold_and_density(self):
        chunks, preview = self.prepare(Image.new('L', (384, 1), 100), threshold=128, density=4)
        self.assertEqual(chunks[0], bytes.fromhex('1c2104'))
        self.assertEqual(preview.getextrema(), (0, 0))
        self.assertEqual(chunks[6], bytes.fromhex('1b19013100') + bytes([255]) * 48)

    def test_rejects_invalid_density_and_oversized_height(self):
        with self.assertRaises(ValueError):
            self.prepare(Image.new('RGB', (384, 1)), density=17)
        with self.assertRaises(ValueError):
            self.prepare(Image.new('RGB', (1, 1000)))

    def test_rejects_other_file_format(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'not-png.png'
            Image.new('RGB', (10, 10)).save(path, format='JPEG')
            with self.assertRaises(ValueError):
                prepare_png(path)


if __name__ == '__main__':
    unittest.main()
