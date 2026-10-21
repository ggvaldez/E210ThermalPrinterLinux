import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from density_test import BLOCK_HEIGHT, WIDTH, build_density_job, generate_density_block


class DensityTestTests(unittest.TestCase):
    def test_single_block_dimensions(self):
        img = generate_density_block(5)
        self.assertEqual(img.size, (WIDTH, BLOCK_HEIGHT))

    def test_density_job_chunk_structure(self):
        chunks, preview = build_density_job(min_density=1, max_density=3)
        self.assertEqual(preview.size, (WIDTH, BLOCK_HEIGHT * 3))
        # Each block has 6 header chunks + 72 row chunks + 2 ending chunks = 80 chunks
        self.assertEqual(len(chunks), 3 * (6 + 72 + 2))
        # Check density bytes for each block
        self.assertEqual(chunks[0], bytes.fromhex('1c2101'))
        self.assertEqual(chunks[80], bytes.fromhex('1c2102'))
        self.assertEqual(chunks[160], bytes.fromhex('1c2103'))
        # Each block ends with 1B 69 and 1B 4A 00
        self.assertEqual(chunks[78:80], [bytes.fromhex('1b69'), bytes.fromhex('1b4a00')])


if __name__ == '__main__':
    unittest.main()
