"""Preparação de PNG para a largura raster validada na E210."""

import math
import struct

from PIL import Image, ImageOps

from e210_raster import encode_rows


WIDTH = 384
DOTS_PER_MM = 8


def prepare_png(path, density=6, threshold=None):
    if not 0 <= density <= 16:
        raise ValueError('A densidade deve estar entre 0 e 16')
    if threshold is not None and not 0 <= threshold <= 255:
        raise ValueError('O limiar deve estar entre 0 e 255')
    with Image.open(path) as source:
        if source.format != 'PNG':
            raise ValueError('O arquivo deve ser uma imagem PNG')
        source = ImageOps.exif_transpose(source)
        height = max(1, round(source.height * WIDTH / source.width))
        length_tenths = math.ceil(height * 10 / DOTS_PER_MM)
        if height + 1 > 65535 or length_tenths > 65535:
            raise ValueError('Imagem longa demais para os campos de 16 bits do protocolo')
        rgba = source.convert('RGBA')
        white = Image.new('RGBA', rgba.size, 'white')
        white.alpha_composite(rgba)
        gray = white.convert('L').resize((WIDTH, height), Image.Resampling.LANCZOS)
        if threshold is None:
            preview = gray.convert('1', dither=Image.Dither.FLOYDSTEINBERG)
        else:
            preview = gray.point(lambda p: 255 if p >= threshold else 0, mode='1')
    # Pillow: branco=1; protocolo da E210: preto=1.
    raster = bytes(value ^ 255 for value in preview.tobytes())
    encoded = encode_rows(raster, WIDTH, height)
    chunks = [bytes.fromhex('1c21') + bytes([density]),
              bytes.fromhex('1b350000'), bytes.fromhex('1b340000'),
              bytes.fromhex('1c2500'), bytes.fromhex('1b33'),
              bytes.fromhex('1b29') + struct.pack('<HHHB', height + 1, 500, length_tenths, 0)]
    start = 0
    for _ in range(height):
        end = start + encoded[start + 3] + 4
        chunks.append(encoded[start:end])
        start = end
    chunks.extend([bytes.fromhex('1b4a00'), bytes.fromhex('1b69')])
    return chunks, preview
