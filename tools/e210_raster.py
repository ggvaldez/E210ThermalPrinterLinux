"""Encoder raster derivado do caminho Java yp1sdk do QLabel 29.0.22."""

import struct


def encode_rows(raster, width, height):
    stride = (width + 7) // 8
    if not 1 <= stride <= 254 or height < 1 or len(raster) != stride * height:
        raise ValueError('Dimensões ou tamanho do raster inválidos')
    result = bytearray()
    for y in range(height):
        row = raster[y * stride:(y + 1) * stride]
        offset = len(row) - len(row.lstrip(b'\0'))
        payload = row[offset:].rstrip(b'\0')
        result.extend(bytes((0x1b, 0x19, 1, len(payload) + 1, offset)))
        result.extend(payload)
    return bytes(result)


def test_pattern():
    # Mesmas dimensões de LPBTService.printImage para mídia lógica 50 x 20 mm:
    # min(50, 48)*8 por int(48*20/50)*8 = 384 x 152 pixels.
    width, height = 384, 152
    raster = bytearray(width * height // 8)
    for y in range(height):
        for x in range(width):
            border = (8 <= x < width - 8 and (8 <= y < 10 or height - 10 <= y < height - 8))
            border |= (8 <= y < height - 8 and (8 <= x < 10 or width - 10 <= x < width - 8))
            # Marca quadrada à esquerda; três barras verticais de alturas distintas.
            mark = 24 <= x < 40 and 24 <= y < 40
            bars = any(a <= x < a + 8 and 48 <= y < end for a, end in [(80, 80), (120, 104), (160, 128)])
            if border or mark or bars:
                raster[y * (width // 8) + x // 8] |= 0x80 >> (x % 8)
    config = bytes.fromhex('1c2106 1b350000 1b340000 1c2500 1b33')
    config += bytes.fromhex('1b29') + struct.pack('<HHHB', height + 1, 500, 200, 0)
    packet = config + encode_rows(raster, width, height) + bytes.fromhex('1b69 1b4a00')
    return packet, f'P4\n{width} {height}\n'.encode() + raster


def test_pattern_chunks():
    """Mesmos bytes do teste original, separados por comando/linha."""
    packet = test_pattern()[0]
    ends = (3, 7, 11, 14, 16, 25)
    chunks = []
    start = 0
    for end in ends:
        chunks.append(packet[start:end])
        start = end
    while start < len(packet) - 5:
        length = packet[start + 3] + 4
        chunks.append(packet[start:start + length])
        start += length
    chunks.extend((packet[-5:-3], packet[-3:]))
    return chunks
