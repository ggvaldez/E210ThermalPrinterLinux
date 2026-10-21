import io
import ctypes
import ctypes.util
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cups'))
from rastertoe210 import (
    CupsRasterPage,
    convert_page_to_e210_chunks,
    encode_rows,
    main as filter_main,
    parse_cups_options,
    read_cups_raster_stream,
    resolve_density,
    resolve_media_type,
)


def create_synthetic_cups_raster_stream(width=384, height=64, bpp=8, cspace=0, magic=b'RaS3', page_name='50x50mm'):
    """Create a valid in-memory binary stream in CUPS raster format."""
    bytes_per_line = (width * bpp + 7) // 8
    # Header format: 1796 bytes for v2
    header = bytearray(1796)

    # Media name at offset 1732
    name_bytes = page_name.encode('latin1')[:63]
    header[1732:1732 + len(name_bytes)] = name_bytes

    # Packed integers at specific offsets:
    # cupsWidth: offset 372
    # cupsHeight: offset 376
    # cupsBitsPerPixel: offset 388
    # cupsBytesPerLine: offset 392
    # cupsColorSpace: offset 400
    struct.pack_into('>I', header, 372, width)
    struct.pack_into('>I', header, 376, height)
    struct.pack_into('>I', header, 388, bpp)
    struct.pack_into('>I', header, 392, bytes_per_line)
    struct.pack_into('>I', header, 400, cspace)
    struct.pack_into('>I', header, 384, 1 if bpp == 1 else 8)
    struct.pack_into('>I', header, 420, 3 if bpp == 24 else 1)

    # Bitmap payload (e.g. alternating test bytes)
    payload = bytes([(y * 7 + x) % 256 for y in range(height) for x in range(bytes_per_line)])

    return magic + bytes(header) + payload


class CupsRasterTests(unittest.TestCase):
    def test_parse_cups_options(self):
        opts = parse_cups_options('finishings=3 media=50x50mm Darkness=8 Dither=Threshold landscape')
        self.assertEqual(opts['finishings'], '3')
        self.assertEqual(opts['media'], '50x50mm')
        self.assertEqual(opts['darkness'], '8')
        self.assertEqual(opts['dither'], 'Threshold')
        self.assertTrue(opts['landscape'])

    def test_resolve_density(self):
        self.assertEqual(resolve_density({}), 6)
        self.assertEqual(resolve_density({'darkness': '6'}), 6)
        self.assertEqual(resolve_density({'darkness': '8'}), 8)
        self.assertEqual(resolve_density({'darkness': 'Draft Light'}), 4)
        self.assertEqual(resolve_density({'darkness': 'Maximum'}), 10)
        self.assertEqual(resolve_density({'density': '14'}), 14)
        self.assertEqual(resolve_density({'density': '99'}), 16)

    def test_resolve_media_type(self):
        self.assertEqual(resolve_media_type({}, '50x100mm'), 0)
        self.assertEqual(resolve_media_type({'media': 'gap'}, '50x100mm'), 2)
        self.assertEqual(resolve_media_type({}, '50x50mm'), 0)
        self.assertEqual(resolve_media_type({'mediatype': 'blackmark'}, '50x50mm'), 3)

    def test_read_cups_raster_stream(self):
        stream_bytes = create_synthetic_cups_raster_stream(width=384, height=32, bpp=8)
        stream = io.BytesIO(stream_bytes)
        pages = list(read_cups_raster_stream(stream))
        self.assertEqual(len(pages), 1)
        page = pages[0]
        self.assertEqual(page.width, 384)
        self.assertEqual(page.height, 32)
        self.assertEqual(page.bpp, 8)
        self.assertEqual(page.page_name, '50x50mm')

    def test_page_to_pil_image_conversions(self):
        # 8-bit grayscale
        p8 = CupsRasterPage(8, 2, 8, 8, 0, '>', bytes(16), 'Test')
        img8 = p8.to_pil_image()
        self.assertEqual(img8.size, (8, 2))
        self.assertEqual(img8.mode, 'L')

        # 24-bit RGB
        p24 = CupsRasterPage(4, 2, 24, 12, 1, '>', bytes(24), 'Test')
        img24 = p24.to_pil_image()
        self.assertEqual(img24.size, (4, 2))
        self.assertEqual(img24.mode, 'L')

    def test_convert_page_to_e210_chunks(self):
        stream_bytes = create_synthetic_cups_raster_stream(width=384, height=40, bpp=8)
        stream = io.BytesIO(stream_bytes)
        page = next(read_cups_raster_stream(stream))
        chunks = convert_page_to_e210_chunks(page, density=8, media_type=2, dither='threshold')

        # First chunk is density
        self.assertEqual(chunks[0], bytes.fromhex('1c2108'))
        # Fourth chunk is media type (2 = gap)
        self.assertEqual(chunks[3], bytes.fromhex('1c2502'))
        # Mode Android
        self.assertEqual(chunks[4], bytes.fromhex('1b33'))
        # Final commands: 1B 69 and 1B 4A 00
        self.assertEqual(chunks[-2:], [bytes.fromhex('1b69'), bytes.fromhex('1b4a00')])

    def test_narrower_label_commands(self):
        # 40mm label
        stream_bytes = create_synthetic_cups_raster_stream(width=320, height=40, bpp=8, page_name='40x60mm')
        stream = io.BytesIO(stream_bytes)
        page = next(read_cups_raster_stream(stream))
        chunks = convert_page_to_e210_chunks(page)
        # All output rows are formatted for 384 dots printhead
        self.assertEqual(chunks[-2:], [bytes.fromhex('1b69'), bytes.fromhex('1b4a00')])

    def test_narrow_content_is_right_aligned_in_all_media_and_scaling_modes(self):
        image = Image.new('L', (240, 160), 0)
        page = CupsRasterPage(240, 160, 8, 240, 0, '=', image.tobytes(),
                              '20x30mmRotated', (203.2, 203.2),
                              (30 * 72 / 25.4, 20 * 72 / 25.4))
        for media in (0, 2, 3):
            for scaling, left in [('fitcontent', 160), ('actualsize', 144)]:
                with self.subTest(media=media, scaling=scaling):
                    chunks = convert_page_to_e210_chunks(page, media_type=media, scaling=scaling)
                    rows = bytearray()
                    for row in chunks[6:-2]:
                        size, offset = row[3] - 1, row[4]
                        rows.extend(bytes(offset) + row[5:5 + size] + bytes(48 - offset - size))
                    # Decode the printer bytes; black pixels must end at the rightmost dot.
                    ink = Image.frombytes('1', (384, len(chunks) - 8), bytes(rows))
                    bbox = ink.getbbox()
                    self.assertEqual(bbox[0], left)
                    self.assertEqual(bbox[2], 384)

    def test_filter_main_cli_execution(self):
        stream_bytes = create_synthetic_cups_raster_stream(width=384, height=16, bpp=8)
        with patch('sys.argv', ['rastertoe210', '1', 'guest', 'Test', '1', 'Darkness=8 media=gap']), \
                patch('sys.stdin', type('Input', (), {'buffer': io.BytesIO(stream_bytes)})()), \
                patch('sys.stdout.buffer.write') as mock_write, patch('sys.stderr.write'):
            exit_code = filter_main()
            self.assertEqual(exit_code, 0)
            self.assertTrue(mock_write.called)

    def test_continuous_content_fills_width_without_page_padding(self):
        image = Image.new('L', (400, 800), 255)
        image.paste(0, (70, 270, 330, 530))  # 32.5 mm artwork on a 50 x 100 mm page.
        page = CupsRasterPage(400, 800, 8, 400, 0, '=', image.tobytes(),
                              '50x100mm', (203.2, 203.2), (50 * 72 / 25.4, 100 * 72 / 25.4))
        chunks = convert_page_to_e210_chunks(page)
        self.assertEqual(len(chunks) - 8, 384)
        self.assertEqual(struct.unpack('<HHHB', chunks[5][2:]), (385, 500, 480, 0))
        self.assertEqual(chunks[6], bytes.fromhex('1b19013100') + b'\xff' * 48)

    def test_fixed_label_keeps_physical_height_but_fits_artwork(self):
        image = Image.new('L', (400, 400), 255)
        image.paste(0, (70, 70, 330, 330))
        page = CupsRasterPage(400, 400, 8, 400, 0, '=', image.tobytes(),
                              '50x50mm', (203.2, 203.2), (50 * 72 / 25.4,) * 2)
        chunks = convert_page_to_e210_chunks(page, media_type=2)
        self.assertEqual(len(chunks) - 8, 400)
        self.assertEqual(struct.unpack('<HHHB', chunks[5][2:]), (401, 500, 500, 0))
        self.assertEqual(chunks[6 + 8], bytes.fromhex('1b19013100') + b'\xff' * 48)

    def test_continuous_square_page_does_not_enlarge_tall_artwork_past_50mm(self):
        image = Image.new('L', (400, 400), 255)
        image.paste(0, (120, 20, 280, 380))  # Tall artwork with large lateral borders.
        page = CupsRasterPage(400, 400, 8, 400, 0, '=', image.tobytes(),
                              '50x50mm', (203.2, 203.2), (50 * 72 / 25.4,) * 2)
        continuous = convert_page_to_e210_chunks(page, media_type=0)
        fixed = convert_page_to_e210_chunks(page, media_type=2)
        # Previously the continuous raster grew to 864 rows / 108 mm.
        self.assertEqual(len(continuous) - 8, 400)
        self.assertEqual(struct.unpack('<HHHB', continuous[5][2:]), (401, 500, 500, 0))
        self.assertEqual(continuous[6:-2], fixed[6:-2])
        row = continuous[6]
        self.assertGreater(row[4], 0)  # Aspect ratio retained, not stretched to head width.

    def test_continuous_trims_unused_height_while_gap_keeps_label_height(self):
        image = Image.new('L', (400, 400), 255)
        image.paste(0, (40, 120, 360, 280))
        page = CupsRasterPage(400, 400, 8, 400, 0, '=', image.tobytes(),
                              '50x50mm', (203.2, 203.2), (50 * 72 / 25.4,) * 2)
        continuous = convert_page_to_e210_chunks(page, media_type=0)
        fixed = convert_page_to_e210_chunks(page, media_type=2)
        self.assertEqual(len(continuous) - 8, 192)
        self.assertEqual(len(fixed) - 8, 400)

    def test_actual_size_preserves_physical_artwork_scale(self):
        image = Image.new('L', (400, 800), 255)
        image.paste(0, (70, 270, 330, 530))
        page = CupsRasterPage(400, 800, 8, 400, 0, '=', image.tobytes(),
                              '50x100mm', (203.2, 203.2))
        chunks = convert_page_to_e210_chunks(page, scaling='actualsize')
        self.assertEqual(len(chunks) - 8, 260)
        row = chunks[6]
        self.assertEqual(row[4], 7)  # Physical position retained, not expanded to full head.

    def test_one_bit_polarity_in_both_cups_color_spaces(self):
        for colorspace, data in [(0, b'\x7f'), (3, b'\x80')]:
            page = CupsRasterPage(8, 1, 1, 1, colorspace, '=', data, '')
            self.assertEqual(list(page.to_pil_image().tobytes()), [0] + [255] * 7)

    def test_header_media_type_precedes_page_name(self):
        self.assertEqual(resolve_media_type({}, '50x50mm', 'Continuous'), 0)
        self.assertEqual(resolve_media_type({}, '50x50mm', 'Gap'), 2)
        self.assertEqual(resolve_media_type({'mediatype': 'BlackMark'}, '', 'Gap'), 3)

    def test_native_compressed_multpage_raster(self):
        # Generate a real compressed stream with libcups, not raw bytes marked RaS2.
        cups = ctypes.CDLL(ctypes.util.find_library('cups'))
        cb_type = ctypes.CFUNCTYPE(ctypes.c_ssize_t, ctypes.c_void_p,
                                  ctypes.POINTER(ctypes.c_ubyte), ctypes.c_size_t)
        parts = []

        @cb_type
        def write_data(context, buffer, length):
            parts.append(ctypes.string_at(buffer, length))
            return length

        cups.cupsRasterOpenIO.argtypes = [cb_type, ctypes.c_void_p, ctypes.c_int]
        cups.cupsRasterOpenIO.restype = ctypes.c_void_p
        cups.cupsRasterWriteHeader2.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        cups.cupsRasterWritePixels.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
        cups.cupsRasterClose.argtypes = [ctypes.c_void_p]
        stream = cups.cupsRasterOpenIO(write_data, None, 2)
        expected = []
        try:
            for color in (0, 255):
                header = bytearray(1796)
                for offset, value in [(276, 203), (280, 203), (372, 16), (376, 12),
                                      (384, 8), (388, 8), (392, 16), (400, 0), (420, 1)]:
                    struct.pack_into('=I', header, offset, value)
                self.assertTrue(cups.cupsRasterWriteHeader2(stream, ctypes.create_string_buffer(bytes(header))))
                data = bytes([color]) * (16 * 12)
                expected.append(data)
                self.assertEqual(cups.cupsRasterWritePixels(stream, ctypes.create_string_buffer(data), len(data)), len(data))
        finally:
            cups.cupsRasterClose(stream)
        pages = list(read_cups_raster_stream(io.BytesIO(b''.join(parts))))
        self.assertEqual([page.data for page in pages], expected)


if __name__ == '__main__':
    unittest.main()
