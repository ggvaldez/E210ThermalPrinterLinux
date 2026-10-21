"""PNG preparation for the validated raster width on the E210."""

import math
import struct

from PIL import Image, ImageOps

from e210_raster import encode_rows
from monochrome import DEFAULT_DITHER, to_monochrome


WIDTH = 384
DOTS_PER_MM = 8
MEDIA_TYPES = {'continuous': 0, 'gap': 2, 'black-mark': 3}


def prepare_png(path, density=10, threshold=None, media='continuous', label_height_mm=None, copies=1,
                dither=DEFAULT_DITHER):
    if not 0 <= density <= 16:
        raise ValueError('Density must be between 0 and 16')
    if threshold is not None and not 0 <= threshold <= 255:
        raise ValueError('Threshold must be between 0 and 255')
    if media not in MEDIA_TYPES:
        raise ValueError('Invalid media type')
    if not isinstance(copies, int) or copies < 1:
        raise ValueError('Number of copies must be a positive integer')
    if label_height_mm is not None and (not math.isfinite(label_height_mm) or label_height_mm <= 0):
        raise ValueError('Label height must be positive and finite')
    if media != 'continuous' and label_height_mm is None:
        raise ValueError('Specify --label-height for fixed-size labels')
    with Image.open(path) as source:
        if source.format != 'PNG':
            raise ValueError('File must be a PNG image')
        source = ImageOps.exif_transpose(source)
        height = max(1, round(source.height * WIDTH / source.width))
        length_tenths = math.ceil(height * 10 / DOTS_PER_MM)
        if label_height_mm is not None:
            if height > round(label_height_mm * DOTS_PER_MM):
                raise ValueError('Image exceeds label height; adjust its aspect ratio')
            length_tenths = math.ceil(label_height_mm * 10)
        if height + 1 > 65535 or length_tenths > 65535:
            raise ValueError('Image too long for the protocol 16-bit fields')
        rgba = source.convert('RGBA')
        white = Image.new('RGBA', rgba.size, 'white')
        white.alpha_composite(rgba)
        gray = white.convert('L').resize((WIDTH, height), Image.Resampling.LANCZOS)
        preview = to_monochrome(gray, dither, threshold)
    # Pillow: white=1; E210 protocol: black=1.
    raster = bytes(value ^ 255 for value in preview.tobytes())
    encoded = encode_rows(raster, WIDTH, height)
    chunks = [bytes.fromhex('1c21') + bytes([density]),
              bytes.fromhex('1b350000'), bytes.fromhex('1b340000'),
              bytes.fromhex('1c25') + bytes([MEDIA_TYPES[media]]), bytes.fromhex('1b33'),
              bytes.fromhex('1b29') + struct.pack('<HHHB', height + 1, 500, length_tenths, 0)]
    start = 0
    for _ in range(height):
        end = start + encoded[start + 3] + 4
        chunks.append(encoded[start:end])
        start = end
    chunks.extend([bytes.fromhex('1b69'), bytes.fromhex('1b4a00')])
    return chunks * copies, preview
