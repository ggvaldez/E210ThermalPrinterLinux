#!/usr/bin/env python3
"""CUPS raster filter for the E210 thermal printer.

Converts application/vnd.cups-raster or image/pwg-raster into E210 binary commands.
Usage by CUPS scheduler:
    rastertoe210 <job-id> <user> <title> <copies> <options> [<filename>]
"""

import ctypes
import ctypes.util
import math
import os
import shlex
import struct
import sys
from pathlib import Path
from PIL import Image, ImageOps

# Validated printable width: 48 mm = 384 dots (8 dots/mm).
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


def resolve_media_type(opts, page_size_name, header_media_type=""):
    """Resolve media type code: continuous=0, gap=2, black-mark=3."""
    if not opts.get("mediatype") and header_media_type:
        opts = dict(opts, mediatype=header_media_type)
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

    def __init__(self, width, height, bpp, bytes_per_line, colorspace, endian, data, page_name,
                 resolution=(203.2, 203.2), page_size=(0, 0), media_type=""):
        self.width = width
        self.height = height
        self.bpp = bpp
        self.bytes_per_line = bytes_per_line
        self.colorspace = colorspace
        self.endian = endian
        self.data = data
        self.page_name = page_name
        self.resolution = resolution
        self.page_size = page_size
        self.media_type = media_type

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
    """Use libcups to decode compressed v2/PWG and uncompressed v1/v3 safely."""
    library = ctypes.util.find_library('cups')
    if not library:
        raise ValueError('libcups is required to decode CUPS/PWG Raster')
    cups = ctypes.CDLL(library)
    callback_type = ctypes.CFUNCTYPE(ctypes.c_ssize_t, ctypes.c_void_p,
                                    ctypes.POINTER(ctypes.c_ubyte), ctypes.c_size_t)
    errors = []

    @callback_type
    def read_data(context, buffer, length):
        try:
            data = stream.read(length)
            ctypes.memmove(buffer, data, len(data))
            return len(data)
        except Exception as exc:
            errors.append(exc)
            return -1

    cups.cupsRasterOpenIO.argtypes = [callback_type, ctypes.c_void_p, ctypes.c_int]
    cups.cupsRasterOpenIO.restype = ctypes.c_void_p
    cups.cupsRasterReadHeader2.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    cups.cupsRasterReadHeader2.restype = ctypes.c_uint
    cups.cupsRasterReadPixels.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
    cups.cupsRasterReadPixels.restype = ctypes.c_uint
    cups.cupsRasterClose.argtypes = [ctypes.c_void_p]
    cups.cupsRasterErrorString.restype = ctypes.c_char_p
    raster = cups.cupsRasterOpenIO(read_data, None, 0)
    if not raster:
        message = cups.cupsRasterErrorString()
        raise ValueError(message.decode(errors='replace') if message else 'Invalid raster stream')
    # cups_page_header2_t has a fixed 1796-byte ABI. libcups returns host byte order.
    try:
        while True:
            header = ctypes.create_string_buffer(1796)
            if not cups.cupsRasterReadHeader2(raster, header):
                if errors:
                    raise ValueError(f'Unable to read raster: {errors[0]}')
                message = cups.cupsRasterErrorString()
                if message:
                    raise ValueError(message.decode(errors='replace'))
                break
            raw = header.raw
            width, height = struct.unpack_from('=II', raw, 372)
            bpp, stride, order, space = struct.unpack_from('=IIII', raw, 388)
            if not width or not height or bpp not in (1, 8, 24, 32) or order != 0:
                raise ValueError('Unsupported raster dimensions, bit depth or planar color order')
            if stride < (width * bpp + 7) // 8 or stride * height > 256 * 1024 * 1024:
                raise ValueError('Invalid or oversized raster page')
            data = bytearray()
            row = ctypes.create_string_buffer(stride)
            for _ in range(height):
                if cups.cupsRasterReadPixels(raster, row, stride) != stride:
                    raise ValueError('Truncated raster pixel data')
                data.extend(row.raw)
            resolution = struct.unpack_from('=II', raw, 276)
            page_size = struct.unpack_from('=ff', raw, 428)
            if not all(page_size):
                page_size = struct.unpack_from('=II', raw, 352)
            name = raw[1732:1796].split(b'\0', 1)[0].decode('latin1')
            media_type = raw[128:192].split(b'\0', 1)[0].decode('latin1')
            yield CupsRasterPage(width, height, bpp, stride, space, '=', bytes(data), name,
                                 resolution, page_size, media_type)
    finally:
        cups.cupsRasterClose(raster)


def convert_page_to_e210_chunks(page, density=6, media_type=0, dither='floydsteinberg',
                                target_width=PRINTER_WIDTH_DOTS, scaling='fitcontent'):
    """Fit artwork to the head, or preserve CUPS physical scale when requested.

    Continuous jobs trim white page padding. Sensor labels keep physical height.
    """
    gray_img = page.to_pil_image()
    bbox = ImageOps.invert(gray_img).getbbox()
    if bbox is None:
        return []  # A blank CUPS page must not feed a whole roll page.
    dpi_x, dpi_y = page.resolution
    dpi_x = dpi_x or 203.2
    dpi_y = dpi_y or dpi_x
    page_width_mm = page.page_size[0] * 25.4 / 72 if page.page_size[0] else page.width * 25.4 / dpi_x
    page_height_mm = page.page_size[1] * 25.4 / 72 if page.page_size[1] else page.height * 25.4 / dpi_y
    # Native CUPS pages have physical dimensions. Synthetic pages can omit them.
    printable_mm = page_width_mm - 2 if page.page_size[0] else page_width_mm
    active_width = min(target_width, max(1, round(printable_mm * DOTS_PER_MM)))
    label_height = max(1, round(page_height_mm * DOTS_PER_MM))
    if scaling.lower() == 'fitcontent':
        content = gray_img.crop(bbox)
        # Removing lateral white margins can make artwork much taller than the
        # selected page if fitted by width alone. Bound both axes on roll media too.
        factor = min(active_width / content.width, label_height / content.height)
        content = content.resize((max(1, round(content.width * factor)),
                                  max(1, round(content.height * factor))), Image.Resampling.LANCZOS)
        output_height = content.height if media_type == 0 else label_height
        full_page = Image.new('L', (target_width, output_height), 255)
        full_page.paste(content, (target_width - content.width,
                                  0 if media_type == 0 else (output_height - content.height) // 2))
    else:
        # Convert resolution to 8 dots/mm without shrinking the physical page to 48 mm.
        size = (max(1, round(page.width * 203.2 / dpi_x)),
                max(1, round(page.height * 203.2 / dpi_y)))
        resized = gray_img.resize(size, Image.Resampling.LANCZOS)
        full_page = Image.new('L', (target_width, size[1]), 255)
        x = (target_width - resized.width if resized.width < target_width
             else (target_width - resized.width) // 2)
        full_page.paste(resized, (x, 0))
        if media_type == 0:
            ink = ImageOps.invert(full_page).getbbox()
            if ink is None:
                return []
            full_page = full_page.crop((0, ink[1], target_width, ink[3]))
    scaled_h = full_page.height
    if scaled_h + 1 > 65535 or math.ceil(scaled_h * 10 / DOTS_PER_MM) > 65535:
        raise ValueError('Raster exceeds E210 page length limits')
    sys.stderr.write(f'DEBUG: E210 source={page.width}x{page.height} dpi={dpi_x}x{dpi_y} '
                     f'content={bbox} scaling={scaling} output={target_width}x{scaled_h} '
                     f'media={media_type}\n')

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
            media_type = resolve_media_type(opts, page.page_name, page.media_type)
            page_chunks = convert_page_to_e210_chunks(
                page, density=density, media_type=media_type, dither=dither,
                scaling=str(opts.get('e210scaling', 'fitcontent')).lower()
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
