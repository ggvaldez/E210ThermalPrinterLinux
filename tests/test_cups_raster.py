import io
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


def create_synthetic_cups_raster_stream(width=384, height=64, bpp=8, cspace=0, magic=b'RaS2', page_name='Label50x50mm'):
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

    # Bitmap payload (e.g. alternating test bytes)
    payload = bytes([(y * 7 + x) % 256 for y in range(height) for x in range(bytes_per_line)])

    return magic + bytes(header) + payload


class CupsRasterTests(unittest.TestCase):
    def test_parse_cups_options(self):
        opts = parse_cups_options('finishings=3 media=Label50x50mm Darkness=8 Dither=Threshold landscape')
        self.assertEqual(opts['finishings'], '3')
        self.assertEqual(opts['media'], 'Label50x50mm')
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
        self.assertEqual(resolve_media_type({}, 'Continuous50mm'), 0)
        self.assertEqual(resolve_media_type({'media': 'gap'}, 'Continuous50mm'), 2)
        self.assertEqual(resolve_media_type({}, 'Label50x50mm'), 2)
        self.assertEqual(resolve_media_type({'mediatype': 'blackmark'}, 'Label50x50mm'), 3)

    def test_read_cups_raster_stream(self):
        stream_bytes = create_synthetic_cups_raster_stream(width=384, height=32, bpp=8)
        stream = io.BytesIO(stream_bytes)
        pages = list(read_cups_raster_stream(stream))
        self.assertEqual(len(pages), 1)
        page = pages[0]
        self.assertEqual(page.width, 384)
        self.assertEqual(page.height, 32)
        self.assertEqual(page.bpp, 8)
        self.assertEqual(page.page_name, 'Label50x50mm')

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

    def test_narrower_label_centering(self):
        # 40mm label
        stream_bytes = create_synthetic_cups_raster_stream(width=320, height=40, bpp=8, page_name='Label40x60mm')
        stream = io.BytesIO(stream_bytes)
        page = next(read_cups_raster_stream(stream))
        chunks = convert_page_to_e210_chunks(page)
        # All output rows are formatted for 384 dots printhead
        self.assertEqual(chunks[-2:], [bytes.fromhex('1b69'), bytes.fromhex('1b4a00')])

    def test_filter_main_cli_execution(self):
        stream_bytes = create_synthetic_cups_raster_stream(width=384, height=16, bpp=8)
        with patch('sys.argv', ['rastertoe210', '1', 'guest', 'Test', '1', 'Darkness=8 media=gap']), \
                patch('sys.stdin.buffer.read', side_effect=[stream_bytes[:4], stream_bytes[4:1800], stream_bytes[1800:], b'']), \
                patch('sys.stdout.buffer.write') as mock_write, patch('sys.stderr.write'):
            exit_code = filter_main()
            self.assertEqual(exit_code, 0)
            self.assertTrue(mock_write.called)


if __name__ == '__main__':
    unittest.main()
