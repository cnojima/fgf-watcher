import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PIL import Image

from champions import _card_state

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "champion_grid_row3_scrolled.png"
_FIXTURE_Y_ORIGIN = 690  # this fixture was cropped starting at absolute y=690


class GridScrolledLastRowTests(unittest.TestCase):
    """Regression test for a bug where the grid's last row (a real
    champion with card art fully visible but its status bar rendered below
    the visible window) was misclassified because the general
    content-diff scroll measurement (102px) did NOT predict where that
    row's status text actually ended up after scrolling (58px, found by
    direct search) - the grid snaps the last row to a fixed resting
    position rather than uniformly translating all content. Uses a real
    screenshot crop (not synthetic data), captured after scrolling the
    actual grid to the bottom."""

    def test_real_champion_and_empty_columns_classify_correctly_at_confirmed_position(self):
        fixture = Image.open(_FIXTURE).convert("RGB")

        def fake_screenshot_region(hwnd, box):
            x0, y0, x1, y1 = box
            return fixture.crop((x0, y0 - _FIXTURE_Y_ORIGIN, x1, y1 - _FIXTURE_Y_ORIGIN))

        layout = types.SimpleNamespace(
            grid_columns=(433, 537, 640, 743, 845),
            card_status_offset=(-45, 63, 47, 83),
        )
        expected = {0: "unlocked", 1: "empty", 2: "empty", 3: "empty", 4: "empty"}  # only col 0 (Phade) is real

        with patch("champions.screenshot_region", side_effect=fake_screenshot_region):
            for col, want in expected.items():
                got = _card_state(None, layout, col, row=0, cy_override=637)
                self.assertEqual(got, want, f"col={col}")


if __name__ == "__main__":
    unittest.main()
