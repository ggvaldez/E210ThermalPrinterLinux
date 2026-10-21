#!/usr/bin/env python3
"""Print a thermal density calibration test from level 1 to 16 on the E210.

Generates 16 calibration blocks, each printed with its corresponding hardware
density command (1C 21 <d>). Every block contains both:
1. Black-on-white: black border, black label number, and fine lines.
2. White-on-black: solid black box with inverted white label number and fine lines.
"""

import argparse
import math
import re
import struct
import sys

from PIL import Image, ImageDraw, ImageFont

from e210_raster import encode_rows
from print_png import discover_address
from probe_bluez import Profile, run_connection

WIDTH = 384
BLOCK_HEIGHT = 72
DOTS_PER_MM = 8


def generate_density_block(density):
    """Render a single 384x72 monochrome bitmap for a specific density level."""
    img = Image.new('1', (WIDTH, BLOCK_HEIGHT), 1)
    draw = ImageDraw.Draw(img)
    font_lg = ImageFont.load_default(size=18)
    font_sm = ImageFont.load_default(size=11)

    # 1. Left side: Black on White (x: 4..186)
    draw.rectangle([4, 4, 186, BLOCK_HEIGHT - 5], outline=0, width=2)
    draw.text((12, 10), f'DENSITY {density:02d}', font=font_lg, fill=0)
    for i in range(12):
        x = 12 + i * 4
        draw.line([x, 38, x, BLOCK_HEIGHT - 12], fill=0, width=1 + (i % 3))
    draw.text((70, 42), 'BLACK / WHITE', font=font_sm, fill=0)

    # 2. Right side: White on Black (x: 196..380)
    draw.rectangle([196, 4, 380, BLOCK_HEIGHT - 5], fill=0)
    draw.text((204, 10), f'DENSITY {density:02d}', font=font_lg, fill=1)
    for i in range(12):
        x = 204 + i * 4
        draw.line([x, 38, x, BLOCK_HEIGHT - 12], fill=1, width=1 + (i % 3))
    draw.text((262, 42), 'WHITE / BLACK', font=font_sm, fill=1)

    return img


def build_density_job(min_density=1, max_density=16):
    """Build the command stream and composite preview for the calibration strip."""
    full_preview = Image.new('1', (WIDTH, BLOCK_HEIGHT * (max_density - min_density + 1)), 1)
    job_chunks = []
    length_tenths = math.ceil(BLOCK_HEIGHT * 10 / DOTS_PER_MM)

    for idx, d in enumerate(range(min_density, max_density + 1)):
        block_img = generate_density_block(d)
        full_preview.paste(block_img, (0, idx * BLOCK_HEIGHT))

        # Pillow: white=1, black=0; E210: black=1, white=0
        raster = bytes(b ^ 255 for b in block_img.tobytes())
        encoded = encode_rows(raster, WIDTH, BLOCK_HEIGHT)

        # Header with specific density d
        block_chunks = [
            bytes.fromhex('1c21') + bytes([d]),
            bytes.fromhex('1b350000'),
            bytes.fromhex('1b340000'),
            bytes.fromhex('1c2500'),  # continuous media
            bytes.fromhex('1b33'),
            bytes.fromhex('1b29') + struct.pack('<HHHB', BLOCK_HEIGHT + 1, 500, length_tenths, 0),
        ]

        # Encoded image rows
        start = 0
        for _ in range(BLOCK_HEIGHT):
            end = start + encoded[start + 3] + 4
            block_chunks.append(encoded[start:end])
            start = end

        # Page ending pair
        block_chunks.extend([bytes.fromhex('1b69'), bytes.fromhex('1b4a00')])
        job_chunks.extend(block_chunks)

    return job_chunks, full_preview


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--address', help='Bluetooth address; if omitted, automatically discovers registered E210')
    parser.add_argument('--adapter', default='hci0')
    parser.add_argument('--preview', help='Save the full calibration test image as PNG')
    parser.add_argument('--dry-run', action='store_true', help='Generate test data without connecting or printing')
    parser.add_argument('--min-density', type=int, default=1, help='Lowest density level to test (default: 1)')
    parser.add_argument('--max-density', type=int, default=16, help='Highest density level to test (default: 16)')
    args = parser.parse_args()

    if not 0 <= args.min_density <= 16 or not 0 <= args.max_density <= 16:
        parser.error('Density levels must be between 0 and 16')
    if args.min_density > args.max_density:
        parser.error('min-density cannot be greater than max-density')
    if args.address and not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', args.address):
        parser.error('Invalid Bluetooth address')

    chunks, preview = build_density_job(args.min_density, args.max_density)
    total_bytes = sum(len(c) for c in chunks)
    print(f'Generated calibration strip: levels {args.min_density} to {args.max_density} '
          f'({preview.width} × {preview.height} px, {total_bytes} bytes).', flush=True)

    if args.preview:
        preview.save(args.preview, format='PNG')
        print(f'Preview saved to {args.preview}', flush=True)

    if args.dry_run:
        return 0

    if not args.address:
        import dbus
        try:
            args.address = discover_address(args.adapter)
        except (dbus.DBusException, ValueError) as exc:
            parser.exit(1, f'Discovery error: {exc}\n')
        except KeyboardInterrupt:
            parser.exit(1, 'Discovery interrupted.\n')

    timeout = 30 + (args.max_density - args.min_density + 1) * 2
    result = run_connection(args.address, args.adapter, timeout,
                            lambda bus, loop: Profile(bus, loop, None, paced=False, job=chunks))
    if result == 0:
        print('Calibration test sent successfully. Inspect the physical printout to find the optimal density.')
    return result


if __name__ == '__main__':
    sys.exit(main())
