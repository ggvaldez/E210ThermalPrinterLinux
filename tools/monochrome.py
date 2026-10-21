"""Shared monochrome conversion for the PNG application and CUPS filter."""

from PIL import Image

DEFAULT_DITHER = 'atkinson'
DITHER_METHODS = ('atkinson', 'floydsteinberg', 'bayer', 'threshold')


def to_monochrome(image, method=DEFAULT_DITHER, threshold=None):
    """Convert at final print resolution; an explicit threshold overrides dithering."""
    method = method.lower().replace('-', '')
    if method not in DITHER_METHODS:
        raise ValueError(f'Unknown dithering method: {method}')
    if threshold is not None and not 0 <= threshold <= 255:
        raise ValueError('Threshold must be between 0 and 255')
    gray = image.convert('L')
    if threshold is not None or method == 'threshold':
        cutoff = 128 if threshold is None else threshold
        return gray.point(lambda pixel: 255 if pixel >= cutoff else 0, mode='1')
    if method == 'floydsteinberg':
        return gray.convert('1', dither=Image.Dither.FLOYDSTEINBERG)
    if method == 'bayer':
        # Same 4x4 dispersed-dot map used in the local print comparison.
        matrix = ((1, 9, 3, 11), (13, 5, 15, 7),
                  (4, 12, 2, 10), (16, 8, 14, 6))
        pixels = gray.tobytes()
        output = bytearray(len(pixels))
        for y in range(gray.height):
            thresholds = matrix[y % 4]
            for x in range(gray.width):
                index = y * gray.width + x
                output[index] = 255 if pixels[index] * 17 >= 255 * thresholds[x % 4] else 0
        return Image.frombytes('L', gray.size, bytes(output)).convert('1', dither=Image.Dither.NONE)

    # Atkinson distributes 1/8 of the quantization error to six neighbors.
    # The remaining 1/4 is deliberately discarded by this algorithm.
    width, height = gray.size
    pixels = gray.tobytes()
    rows = [[float(pixel) for pixel in pixels[y * width:(y + 1) * width]]
            for y in range(min(3, height))]
    output = bytearray(width * height)
    for y in range(height):
        for x in range(width):
            index = y * width + x
            quantized = 255 if rows[y % 3][x] >= 128 else 0
            output[index] = quantized
            error = (rows[y % 3][x] - quantized) / 8
            for dx, dy in ((1, 0), (2, 0), (-1, 1), (0, 1), (1, 1), (0, 2)):
                xx, yy = x + dx, y + dy
                if 0 <= xx < width and yy < height:
                    rows[yy % 3][xx] += error
        if y + 3 < height:
            rows[y % 3] = [float(pixel) for pixel in pixels[(y + 3) * width:(y + 4) * width]]
    return Image.frombytes('L', gray.size, bytes(output)).convert('1', dither=Image.Dither.NONE)
