import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PIL import Image

from replay_all_champions import _stitch_ability_body_frames, _stitch_weapon_stats_frames


class StitchFullWindowFramesTests(unittest.TestCase):
    def test_weapon_stats_frames_are_cropped_to_box_before_stitching(self):
        # Captured frames are full-window screenshots (see
        # capture_all_champions.py's _save); weapon_stats_box is a strict
        # sub-region of the window. A single-frame composite should come
        # back at weapon_stats_box's size, not the window's - regression
        # test for the same crop-before-stitch bug found and fixed in
        # replay_all_flagships._stitch_attribute_frames.
        layout = types.SimpleNamespace(
            weapon_stats_box=(20, 10, 80, 90),  # 60x80 sub-region of the 100x100 window
            weapon_stats_expected_scroll_offset=10,
        )
        window_frame = Image.new("RGB", (100, 100), (0, 0, 0))
        composite = _stitch_weapon_stats_frames([window_frame], layout)
        self.assertEqual(composite.size, (60, 80))

    def test_ability_body_frames_are_cropped_to_box_before_stitching(self):
        layout = types.SimpleNamespace(
            ability_scroll_box=(15, 20, 75, 95),  # 60x75 sub-region of the 100x100 window
            ability_expected_scroll_offset=10,
        )
        window_frame = Image.new("RGB", (100, 100), (0, 0, 0))
        composite = _stitch_ability_body_frames([window_frame], layout)
        self.assertEqual(composite.size, (60, 75))


if __name__ == "__main__":
    unittest.main()
