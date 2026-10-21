#!/usr/bin/env python3
"""CUPS raster filter for the E210 Bluetooth thermal printer.

Converts application/vnd.cups-raster or image/pwg-raster into E210 binary commands.
Usage by CUPS scheduler:
    rastertoe210 <job-id> <user> <title> <copies> <options> [<filename>]
"""

import math
import os
import shlex
import struct
import sys
from pathlib import Path
from PIL import Image, ImageOps

# Maximum physical printable width is 48 mm = 384 dots @ 203 DPI (8 dots/mm)
PRINTER_WIDTH_DOTS = 384
DOTS_PER_MM = 8


def encode_rows(raster, width, height):
    """Encode binary rows using the E210 run-length/offset protocol (1B 19 01 ...)."""
    stride = (width + 7) // 8
    if not 1 <= stride <= 254 or height < 1 or len(raster) != stride * height:
        raise ValueError('Invalid raster dimensions or size')
    result = bytearray()
    for y in range(height):
        row = raster[y * stride:(y + 1) * stride]
        offset = len(row) - len(row.lstrip(b'\0'))
        payload = row[offset:].rstrip(b'\0')
        result.extend(bytes((0x1b, 0x19, 1, len(payload) + 1, offset)))
        result.extend(payload)
    return bytes(result)


def parse_cups_options(options_str):
    """Parse CUPS command-line options string into a normalized dictionary."""
    opts = {}
    if not options_str:
        return opts
    try:
        parts = shlex.split(options_str)
    except Exception:
        parts = options_str.split()
    for part in parts:
        if '=' in part:
            k, v = part.split('=', 1)
            opts[k.lower()] = v
        else:
            opts[part.lower()] = True
    return opts


def resolve_density(opts):
    """Determine thermal print density (default: 6, practical max: 10)."""
    val = opts.get('darkness') or opts.get('density')
    if val is None:
        return 6
    if isinstance(val, str):
        val_lower = val.lower()
        if 'draft' in val_lower or 'light' in val_lower:
            return 4
        if 'normal' in val_lower:
            return 6
        if 'dark' in val_lower and 'very' not in val_lower:
            return 8
        if 'very' in val_lower or 'max' in val_lower:
            return 10
        try:
            val = int(val)
        except ValueError:
            return 6
    if isinstance(val, int):
        return max(0, min(16, val))
    return 6


def resolve_media_type(opts, page_size_name):
    """Resolve media type code: continuous=0, gap=2, black-mark=3."""
    m = opts.get('mediatype') or opts.get('media')
    if m:
        m_lower = str(m).lower()
        if 'gap' in m_lower or 'label' in m_lower:
            return 2
        if 'black' in m_lower or 'mark' in m_lower:
            return 3
        if 'continuous' in m_lower or 'roll' in m_lower:
            return 0
    if page_size_name:
        ps_lower = page_size_name.lower()
        if 'gap' in ps_lower or 'label' in ps_lower:
            return 2
        if 'black' in ps_lower or 'mark' in ps_lower:
            return 3
    return 0


class CupsRasterPage:
    """Represents a single parsed page from a CUPS raster stream."""

    def __init__(self, width, height, bpp, bytes_per_line, colorspace, endian, data, page_name):
        self.width = width
        self.height = height
        self.bpp = bpp
        self.bytes_per_line = bytes_per_line
        self.colorspace = colorspace
        self.endian = endian
        self.data = data
        self.page_name = page_name

    def to_pil_image(self):
        """Convert page raster data into a PIL Grayscale image ('L')."""
        if self.bpp == 1:
            # 1-bit monochrome
            img = Image.frombytes('1', (self.width, self.height), self.data, 'raw', '1;I', self.bytes_per_line)
            # In CUPS raster, colorspace 3 (K) has 1=black, while colorspace 0 (W) has 0=black.
            if self.colorspace != 3:
                img = ImageOps.invert(img.convert('L'))
            else:
                img = img.convert('L')
            return img
        elif self.bpp == 8:
            img = Image.frombytes('L', (self.width, self.height), self.data, 'raw', 'L', self.bytes_per_line)
            if self.colorspace == 3:  # K (black ink)
                img = ImageOps.invert(img)
            return img
        elif self.bpp == 24:
            return Image.frombytes('RGB', (self.width, self.height), self.data, 'raw', 'RGB', self.bytes_per_line).convert('L')
        elif self.bpp == 32:
            if self.colorspace == 6:  # CMYK
                return Image.frombytes('CMYK', (self.width, self.height), self.data, 'raw', 'CMYK', self.bytes_per_line).convert('L')
            return Image.frombytes('RGBA', (self.width, self.height), self.data, 'raw', 'RGBA', self.bytes_per_line).convert('L')
        else:
            raise ValueError(f'Unsupported CUPS raster bit depth: {self.bpp}')


def read_cups_raster_stream(stream):
    """Generator reading all pages from a CUPS or PWG raster stream."""
    magic = stream.read(4)
    if not magic or len(magic) < 4:
        return

    # Check magic synchronization string
    if magic in (b'RaSt', b'RaS2', b'RaS3'):
        endian = '>'
    elif magic in (b'tSaR', b'2SaR', b'3SaR'):
        endian = '<'
    else:
        raise ValueError(f'Invalid CUPS raster magic: {magic!r}')

    # Version 2 header is 1796 bytes; Version 1 is 432 bytes
    is_v2 = magic in (b'RaS2', b'RaS3', b'2SaR', b'3SaR')
    header_size = 1796 if is_v2 else 432

    while True:
        header_bytes = stream.read(header_size)
        if not header_bytes:
            break
        if len(header_bytes) < header_size:
            break

        # Header offsets (constant across v1 and v2 for essential fields):
        # cupsWidth at offset 372
        # cupsHeight at offset 376
        # cupsBitsPerPixel at offset 388
        # cupsBytesPerLine at offset 392
        # cupsColorSpace at offset 400
        cups_width = struct.unpack_from(endian + 'I', header_bytes, 372)[0]
        cups_height = struct.unpack_from(endian + 'I', header_bytes, 376)[0]
        cups_bpp = struct.unpack_from(endian + 'I', header_bytes, 388)[0]
        cups_bytes_per_line = struct.unpack_from(endian + 'I', header_bytes, 392)[0]
        cups_cspace = struct.unpack_from(endian + 'I', header_bytes, 400)[0]

        page_name = ''
        if is_v2:
            # cupsPageSizeName at offset 1732 (64 bytes string)
            name_bytes = header_bytes[1732:1796].split(b'\0', 1)[0]
            page_name = name_bytes.decode('latin1', 'replace')

        data_size = cups_bytes_per_line * cups_height
        data = stream.read(data_size)
        if len(data) < data_size:
            break

        yield CupsRasterPage(cups_width, cups_height, cups_bpp, cups_bytes_per_line,
                             cups_cspace, endian, data, page_name)


def convert_page_to_e210_chunks(page, density=6, media_type=0, dither='floydsteinberg',
                                target_width=PRINTER_WIDTH_DOTS):
    """Convert a CupsRasterPage into a list of E210 command chunks."""
    gray_img = page.to_pil_image()

    # Determine scaling:
    # If the image matches 50mm paper (or full printhead), scale to 384 dots width.
    # If smaller (e.g., 40mm or 30mm labels), center within 384 dots.
    src_w, src_h = gray_img.size
    aspect = src_h / max(1, src_w)

    # Calculate physical width ratio if page name indicates size:
    active_width = target_width
    offset_x = 0
    if '40x' in page.page_name.lower():
        active_width = 304  # 38 mm @ 8 dots/mm
        offset_x = (target_width - active_width) // 2
    elif '30x' in page.page_name.lower():
        active_width = 224  # 28 mm @ 8 dots/mm
        offset_x = (target_width - active_width) // 2

    scaled_h = max(1, round(active_width * aspect))
    resized = gray_img.resize((active_width, scaled_h), Image.Resampling.LANCZOS)

    # Composite onto full 384-width white background
    full_page = Image.new('L', (target_width, scaled_h), 255)
    full_page.paste(resized, (offset_x, 0))

    # Convert to 1-bit monochrome
    if dither.lower() == 'threshold':
        mono = full_page.point(lambda p: 255 if p >= 128 else 0, mode='1')
    else:
        mono = full_page.convert('1', dither=Image.Dither.FLOYDSTEINBERG)

    # Invert polarity: Pillow 1=white; E210 1=black
    raster = bytes(b ^ 255 for b in mono.tobytes())
    encoded = encode_rows(raster, target_width, scaled_h)

    length_tenths = math.ceil(scaled_h * 10 / DOTS_PER_MM)

    # Command chunks for this page
    chunks = [
        bytes.fromhex('1c21') + bytes([density]),
        bytes.fromhex('1b350000'),  # h-offset 0
        bytes.fromhex('1b340000'),  # v-offset 0
        bytes.fromhex('1c25') + bytes([media_type]),
        bytes.fromhex('1b33'),      # standard mode
        bytes.fromhex('1b29') + struct.pack('<HHHB', scaled_h + 1, 500, length_tenths, 0),
    ]

    # Encoded image rows
    start = 0
    for _ in range(scaled_h):
        end = start + encoded[start + 3] + 4
        chunks.append(encoded[start:end])
        start = end

    # Ending commands: 1B 69 followed by 1B 4A 00
    chunks.extend([bytes.fromhex('1b69'), bytes.fromhex('1b4a00')])
    return chunks


def main():
    if len(sys.argv) < 6:
        sys.stderr.write(f'Usage: {sys.argv[0]} job-id user title copies options [filename]\n')
        return 1

    job_id = sys.argv[1]
    user = sys.argv[2]
    title = sys.argv[3]
    try:
        copies = max(1, int(sys.argv[4]))
    except ValueError:
        copies = 1
    options_str = sys.argv[5]

    opts = parse_cups_options(options_str)
    density = resolve_density(opts)
    dither = opts.get('dither', 'floydsteinberg')

    # Input file or stdin
    if len(sys.argv) >= 7 and sys.argv[6]:
        input_stream = open(sys.argv[6], 'rb')
    else:
        input_stream = sys.stdin.buffer

    page_count = 0
    job_chunks = []

    try:
        for page in read_cups_raster_stream(input_stream):
            page_count += 1
            sys.stderr.write(f'PAGE: {page_count} {copies}\n')
            media_type = resolve_media_type(opts, page.page_name)
            page_chunks = convert_page_to_e210_chunks(
                page, density=density, media_type=media_type, dither=dither
            )
            job_chunks.extend(page_chunks * copies)
    finally:
        if input_stream is not sys.stdin.buffer:
            input_stream.close()

    if page_count == 0:
        sys.stderr.write('DEBUG: No raster pages found in input stream.\n')
        return 0

    # Write generated E210 binary commands to stdout for CUPS backend
    output = sys.stdout.buffer
    for chunk in job_chunks:
        output.write(chunk)
    output.flush()

    sys.stderr.write(f'INFO: Processed {page_count} page(s), {len(job_chunks)} chunks.\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
