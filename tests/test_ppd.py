import re
import shutil
import subprocess
import unittest
from pathlib import Path


PPD = Path(__file__).resolve().parents[1] / 'ppd' / 'e210.ppd'


class PpdTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cupstestppd'), 'CUPS PPD validator is not installed')
    def test_cups_validation_has_no_warnings(self):
        # Source-tree validation should not depend on a root-owned installed filter.
        result = subprocess.run(['cupstestppd', '-I', 'filters', str(PPD)],
                                capture_output=True, text=True)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertNotIn('WARN', output)
        self.assertNotIn('FAIL', output)

    def test_standard_names_match_exact_physical_dimensions(self):
        text = PPD.read_text()
        sizes = re.findall(r'^\*PaperDimension (\S+)/[^:]+: "([\d.]+) ([\d.]+)"', text, re.M)
        self.assertEqual(len(sizes), 10)
        for name, width, height in sizes:
            match = re.fullmatch(r'(\d+)x(\d+)mm(Rotated)?', name)
            self.assertIsNotNone(match, name)
            dimensions = [float(match[1]), float(match[2])]
            if match[3]:
                dimensions.reverse()
            self.assertAlmostEqual(float(width) * 25.4 / 72, dimensions[0], places=5)
            self.assertAlmostEqual(float(height) * 25.4 / 72, dimensions[1], places=5)
            for keyword in ('PageSize', 'PageRegion', 'ImageableArea'):
                self.assertRegex(text, rf'(?m)^\*{keyword} {re.escape(name)}/')
        self.assertIn('*DefaultPageSize: 50x100mm', text)


if __name__ == '__main__':
    unittest.main()
