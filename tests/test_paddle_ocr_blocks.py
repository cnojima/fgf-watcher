import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from paddle_ocr_blocks import _group_into_rows


class GroupIntoRowsTests(unittest.TestCase):
    def test_tightly_packed_rows_dont_merge_on_boundary_noise(self):
        # Real detection boxes from a captured component's stats block
        # (Atlas MK2-Railgun): a bold value glyph's box (e.g. "4,405") sits
        # a couple pixels taller than its own row and dips 1-2px into the
        # next row's label box ("DEF" at y0=22, inside "4,405"'s y0=0..24).
        # Regression test for a bug where that boundary noise transitively
        # chain-merged all four rows into one garbled line.
        boxes = [
            (0, 1, 61, 22),      # ATTACK
            (318, 0, 367, 24),   # 4,405
            (0, 22, 34, 49),     # DEF
            (317, 23, 367, 49),  # 3,303
            (0, 49, 31, 73),     # INT
            (316, 47, 369, 75),  # 1,116
            (0, 77, 125, 97),    # Command Points
            (339, 74, 368, 98),  # 12
            (0, 101, 66, 122),   # Crit Rate
            (304, 99, 367, 123),  # 25.00%
            (0, 124, 114, 146),  # Damage Bonus
            (312, 124, 367, 148),  # 2.50%
        ]
        texts = [
            "ATTACK", "4,405", "DEF", "3,303", "INT", "1,116",
            "Command Points", "12", "Crit Rate", "25.00%", "Damage Bonus", "2.50%",
        ]
        rows = _group_into_rows(boxes, texts)
        self.assertEqual(rows, [
            "ATTACK 4,405",
            "DEF 3,303",
            "INT 1,116",
            "Command Points 12",
            "Crit Rate 25.00%",
            "Damage Bonus 2.50%",
        ])


if __name__ == "__main__":
    unittest.main()
