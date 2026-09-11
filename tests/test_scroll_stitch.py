import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from scroll_stitch import capture_scroll_sequence, content_offset, stitch_frames


def _make_source(height=1000, width=50, seed=42):
    # Each row gets a deterministic pseudo-random intensity (not a clipped
    # ramp, which flattens to a constant past row 255, and not a periodic
    # pattern, which could alias at a wraparound distance within the
    # content_offset search window) - unique enough over this many rows
    # that content_offset's sum-of-squared-differences search has exactly
    # one true alignment to find.
    rows = np.random.RandomState(seed).randint(0, 256, size=height)
    return np.repeat(rows[:, None], width, axis=1).astype(np.uint8)


class CaptureScrollSequenceTests(unittest.TestCase):
    def test_stops_when_content_stabilizes_and_frames_match_live_stitch(self):
        source = _make_source(height=1000, width=50)
        box_height = 200
        offset = 90
        max_top = source.shape[0] - box_height  # 800

        state = {"top": 0}

        def fake_screenshot_region(hwnd, box):
            crop = source[state["top"]:state["top"] + box_height, :]
            return Image.fromarray(crop, mode="L").convert("RGB")

        def fake_drag(hwnd, *args):
            state["top"] = min(state["top"] + offset, max_top)

        saved = []

        with patch("capture.screenshot_region", side_effect=fake_screenshot_region), \
             patch("scroll_stitch.drag", side_effect=fake_drag):
            capture_scroll_sequence(
                lambda sequence: saved.append(sequence),
                hwnd=None, box=(0, 0, 50, box_height), drag_from=(0, 100), drag_to=(0, 10),
                expected_offset=offset, static_header_height=0, max_scrolls=45,
            )

        # 800 / 90 = ~8.9, so content stabilizes after 9 scrolls (top clamps
        # at 800) - one more save_frame call happens for the stabilized
        # frame before the loop notices it stopped moving and breaks.
        self.assertEqual(saved, list(range(10)))

    def test_frames_saved_during_capture_stitch_identically_to_a_live_call(self):
        # Cropped frames captured via capture_scroll_sequence's own
        # screenshot_region calls should stitch (via stitch_frames) to the
        # same composite a live stitch_scrolled_region call would produce
        # from the same underlying content.
        source = _make_source(height=600, width=50)
        box_height = 150
        offset = 60
        max_top = source.shape[0] - box_height  # 450

        state = {"top": 0}

        def fake_screenshot_region(hwnd, box):
            crop = source[state["top"]:state["top"] + box_height, :]
            return Image.fromarray(crop, mode="L").convert("RGB")

        def fake_drag(hwnd, *args):
            state["top"] = min(state["top"] + offset, max_top)

        frames = []
        with patch("capture.screenshot_region", side_effect=fake_screenshot_region), \
             patch("scroll_stitch.drag", side_effect=fake_drag):
            capture_scroll_sequence(
                lambda sequence: frames.append(fake_screenshot_region(None, None)),
                hwnd=None, box=(0, 0, 50, box_height), drag_from=(0, 100), drag_to=(0, 10),
                expected_offset=offset, static_header_height=0, max_scrolls=45,
            )

        composite = stitch_frames(frames, static_header_height=0, expected_offset=offset)
        # The full scrolled range (0..max_top+box_height) should be present,
        # seamlessly, with no gap or duplicate content.
        expected_height = max_top + box_height
        self.assertEqual(composite.height, expected_height)
        column = np.asarray(composite.convert("L"))[:, 0]
        self.assertTrue(np.array_equal(column, source[:expected_height, 0]))


if __name__ == "__main__":
    unittest.main()
