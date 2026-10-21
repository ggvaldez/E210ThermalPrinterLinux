import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from monochrome import to_monochrome
from png_job import prepare_png


class MonochromeTests(unittest.TestCase):
    def test_atkinson_known_small_pattern_and_edges(self):
        image = Image.new('L', (2, 2), 128)
        result = to_monochrome(image)
        self.assertEqual(list(result.convert('L').tobytes()), [255, 0, 0, 255])
        for size in ((1, 1), (1, 9), (9, 1), (5, 7)):
            for value in (0, 255):
                with self.subTest(size=size, value=value):
                    source = Image.new('L', size, value)
                    self.assertEqual(to_monochrome(source).convert('L').tobytes(), source.tobytes())

    def test_binary_input_is_unchanged_for_every_method(self):
        source = Image.new('1', (17, 11))
        source.putdata([255 if i % 3 else 0 for i in range(17 * 11)])
        for method in ('atkinson', 'floydsteinberg', 'bayer', 'clustered', 'threshold'):
            self.assertEqual(to_monochrome(source, method).tobytes(), source.tobytes())

    def test_bayer_midgray_pattern_repeats_and_threshold_overrides_it(self):
        image = Image.new('L', (5, 5), 128)
        result = to_monochrome(image, 'bayer').convert('L')
        self.assertEqual(result.size, image.size)
        self.assertEqual(result.tobytes(), bytes(
            255 if (x + y) % 2 == 0 else 0 for y in range(5) for x in range(5)))
        self.assertEqual(to_monochrome(image, 'bayer', threshold=129).getextrema(), (0, 0))
        self.assertEqual(to_monochrome(Image.new('L', (4, 4), 32), 'bayer')
                         .convert('L').tobytes().count(255), 2)

    def test_floyd_option_and_explicit_threshold(self):
        image = Image.new('L', (8, 8))
        image.putdata([i * 4 for i in range(64)])
        expected = image.convert('1', dither=Image.Dither.FLOYDSTEINBERG)
        self.assertEqual(to_monochrome(image, 'FloydSteinberg').tobytes(), expected.tobytes())
        threshold = to_monochrome(image, threshold=100).convert('L').tobytes()
        self.assertEqual(threshold, bytes(255 if i * 4 >= 100 else 0 for i in range(64)))
        self.assertNotEqual(to_monochrome(image).tobytes(), expected.tobytes())
        for kwargs in ({'method': 'invalid'}, {'threshold': 256}, {'threshold': -1}):
            with self.assertRaises(ValueError):
                to_monochrome(image, **kwargs)

    def test_clustered_midgray_forms_repeating_clusters(self):
        expected = ('..###...', '..###...', '.######.', '########',
                    '######..', '..###...', '..##....', '...#....')
        image = Image.new('L', (9, 9), 128)
        mono = to_monochrome(image, 'clustered')
        self.assertEqual(mono.size, image.size)
        self.assertEqual(mono.convert('L').tobytes(), bytes(
            0 if expected[y % 8][x % 8] == '#' else 255
            for y in range(9) for x in range(9)))
        self.assertEqual(to_monochrome(image, 'clustered', threshold=129).getextrema(), (0, 0))

    def test_png_and_cups_share_new_defaults_and_raster(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cups'))
        from rastertoe210 import CupsRasterPage, convert_page_to_e210_chunks
        source = Image.new('L', (384, 24))
        source.putdata([32 + (i * 17) % 192 for i in range(384 * 24)])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.png'
            source.save(path)
            png_chunks, preview = prepare_png(path, media='gap', label_height_mm=3)
        page = CupsRasterPage(384, 24, 8, 384, 0, '<', source.tobytes(), '')
        cups_chunks = convert_page_to_e210_chunks(page, media_type=2, scaling='actualsize')
        self.assertEqual(png_chunks[0], bytes.fromhex('1c210a'))
        self.assertEqual(preview.tobytes(), to_monochrome(source).tobytes())
        self.assertEqual(png_chunks, cups_chunks)
        ppd = (Path(__file__).resolve().parents[1] / 'ppd/e210.ppd').read_text()
        self.assertIn('*DefaultDither: Atkinson', ppd)
        self.assertIn('*DefaultDarkness: 10', ppd)
        for method in ('bayer', 'clustered'):
            with self.subTest(method=method), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'synthetic.png'
                source.save(path)
                png, _ = prepare_png(path, media='gap', label_height_mm=3, dither=method)
                cups = convert_page_to_e210_chunks(page, media_type=2, scaling='actualsize',
                                                  dither=method.title())
                self.assertEqual(png, cups)
        self.assertIn('*Dither Bayer/Bayer 4x4 Ordered Dithering:', ppd)
        self.assertIn('*Dither Clustered/Clustered 8x8 Halftone:', ppd)


if __name__ == '__main__':
    unittest.main()
