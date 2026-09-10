"""Scroll through a drag-scrollable region and stitch the captures into one
seamless composite image, for reading more content than fits in one screenshot.

Originally built for the ship Attribute Details table (see
attribute_details.py's module docstring for the full history of why this
approach - image stitching, not cross-capture text merging - was needed
there), then extracted here once the champion weapon stats list needed the
exact same scroll-and-stitch mechanics: drag scrolling never lands exactly
on the requested distance (touch-scroll physics doesn't guarantee it), so
the actual movement is measured from pixel content instead of trusted, and
each capture's genuinely-new bottom slice is spliced onto one growing
composite - never merging text across captures - so cross-capture
misattribution isn't possible by construction, regardless of what's actually
in the scrolled content (nested sections, a flat list, anything else).
"""
import logging
import time

import numpy as np
from PIL import Image

from input_control import drag

log = logging.getLogger(__name__)


def content_offset(prev_img: Image.Image, curr_img: Image.Image, static_header_height: int,
                    expected: int, margin: int = 150) -> int:
    """How far curr_img's content has scrolled down relative to prev_img, in
    pixels - found by matching actual pixel content (a thin strip against a
    sliding window of prev_img) rather than trusting the drag gesture.
    Searches a margin around the requested drag distance rather than the
    whole image, since the true answer is always close to it.

    The strip is sampled starting at static_header_height, not the very top
    of the crop: any fixed UI chrome at the top of the capture region (e.g.
    a tab bar) never scrolls, and comparing that against itself always
    scores a perfect match at offset=0 regardless of how far the actual
    content below it moved - pass 0 here if the capture region has no such
    chrome (confirmed live: this exact bug made scrolling look completely
    broken when a tab bar was included unmasked)."""
    prev = np.asarray(prev_img.convert("L"), dtype=np.int32)
    curr = np.asarray(curr_img.convert("L"), dtype=np.int32)
    strip_h = 80
    curr_strip = curr[static_header_height:static_header_height + strip_h, :]

    # Always search from 0, not expected-margin: at the true scroll-bottom
    # the frames are identical and the real answer is 0, which a window
    # centered on `expected` would never even consider.
    lo = 0
    hi = min(prev.shape[0] - static_header_height - strip_h, expected + margin)
    best_offset, best_score = expected, None
    for offset in range(lo, hi + 1):
        start = static_header_height + offset
        score = np.sum((prev[start:start + strip_h, :] - curr_strip) ** 2)
        if best_score is None or score < best_score:
            best_score = score
            best_offset = offset
    return best_offset


def stitch_scrolled_region(
    hwnd, box: tuple[int, int, int, int], drag_from: tuple[int, int], drag_to: tuple[int, int],
    expected_offset: int, static_header_height: int = 0, max_scrolls: int = 45, settle_time: float = 0.7,
) -> Image.Image:
    """Scrolls `box` via drag(drag_from -> drag_to) up to max_scrolls times,
    splicing only the genuinely new bottom slice of each capture (per
    content_offset) onto one growing composite, until scrolling stalls
    (content stops moving - assumed to mean the true bottom was reached)."""
    from capture import screenshot_region

    frame = screenshot_region(hwnd, box)
    parts = [frame]

    for i in range(max_scrolls):
        drag(hwnd, *drag_from, *drag_to)
        time.sleep(settle_time)  # let scroll momentum/animation fully settle before capturing
        next_frame = screenshot_region(hwnd, box)
        offset = content_offset(frame, next_frame, static_header_height, expected_offset)
        log.debug("Scroll %d/%d: offset=%dpx", i + 1, max_scrolls, offset)
        if offset <= 5:
            log.debug("Reached scroll bottom after %d scroll(s)", i + 1)
            break
        parts.append(next_frame.crop((0, frame.height - offset, next_frame.width, next_frame.height)))
        frame = next_frame
    else:
        log.warning("Hit max_scrolls (%d) without detecting a stall - composite may be incomplete", max_scrolls)

    composite = Image.new("RGB", (frame.width, sum(p.height for p in parts)))
    y = 0
    for part in parts:
        composite.paste(part, (0, y))
        y += part.height
    return composite
