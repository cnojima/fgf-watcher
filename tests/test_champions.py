import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from champions import classify_card_state


class ClassifyCardStateTests(unittest.TestCase):
    def test_real_champion_status_reads_unlocked(self):
        self.assertEqual(classify_card_state("165"), "unlocked")

    def test_locked_progress_readout_reads_locked(self):
        self.assertEqual(classify_card_state("0/40"), "locked")

    def test_blank_cell_reads_empty(self):
        self.assertEqual(classify_card_state(""), "empty")

    def test_garbage_ocr_with_no_digits_reads_empty(self):
        # Real OCR output captured against an actual grid screenshot: a
        # locked/teaser slot with no status bar at all ("-"), and a
        # genuinely empty cell in a partially-filled last row whose status
        # box overlapped the RECRUIT button below it ("-DECRI"/"T"/"F",
        # fragments of "RECRUIT" itself). None of these are a real
        # level/progress readout - regression test for a bug where they
        # were misclassified "unlocked", causing capture to try opening
        # several nonexistent cards past the true end of the roster.
        for garbage in ("-", "-DECRI", "T", "F"):
            self.assertEqual(classify_card_state(garbage), "empty", garbage)


if __name__ == "__main__":
    unittest.main()
