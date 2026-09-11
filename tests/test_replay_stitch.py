import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PIL import Image

from replay_all_flagships import _stitch_attribute_frames


class StitchAttributeFramesTests(unittest.TestCase):
    def test_crops_full_window_frames_to_table_box_before_stitching(self):
        # Captured frames are full-window screenshots (see capture_all_flagships.py's
        # _save); table_box is a strict sub-region of the window. A single-frame
        # composite should come back at table_box's size, not the window's -
        # regression test for a bug where the first stitched slice was the raw
        # full-window frame instead of a table_box crop.
        layout = types.SimpleNamespace(
            table_box=(20, 10, 80, 90),  # 60x80 sub-region of the 100x100 window
            table_tab_bar_height=0,
            expected_scroll_offset=10,
        )
        window_frame = Image.new("RGB", (100, 100), (0, 0, 0))
        composite = _stitch_attribute_frames([window_frame], layout)
        self.assertEqual(composite.size, (60, 80))


if __name__ == "__main__":
    unittest.main()
