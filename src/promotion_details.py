"""Read a ship's current promotion level (0-6) from its Promote tab.

Reached from a ship's detail view: click the Promote tab. The current level
renders as a badge in `promotion_badge_box` regardless of promotion state -
a Roman numeral (I-V) for levels 1-5, a muted star/cross glyph (no numeral)
for level 0, or a bright teal/cyan star badge for a maxed (level 6) ship.
Confirmed via live screenshots of a level-I ship (Gram), a level-0 ship
(Demerzel), and a maxed Gram - the box position is the same in all three;
only the icon inside it changes.

The maxed badge is *not* classified directly: under the `--psm 10 -c
tessedit_char_whitelist=IV` OCR used for the Roman-numeral badges, its
bright pointed shape has been misread as "V" (reporting level 5 instead of
6) - confirmed against a real maxed-ship calibration screenshot showing the
badge sitting inside `promotion_badge_box`. So level 6 is detected first,
before ever OCRing that box, by checking the PROMOTE/PROMOTED button text
instead ("PROMOTED" vs "PROMOTE") - a clean, unambiguous text signal that
stays in the same place across every promotion state.
"""
import logging
import time

import paddle_ocr
import promotion_badge_ocr
from capture import screenshot_region
from input_control import click
from profiles.ui_layout import get_layout, require_field

log = logging.getLogger(__name__)

_ROMAN_TO_LEVEL = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}


def _read_badge_text(hwnd, layout) -> str:
    # Tightly bounds the current-level badge slot. Only called after
    # _is_maxed() has ruled out level 6 - on a maxed ship this same box
    # holds a bright star badge that gets OCR'd as a stray "V" under the old
    # Tesseract whitelist instead of coming back empty (see module
    # docstring) - not re-verified against the model below, since this
    # level-6 case is never actually reached (checked first, unconditionally).
    #
    # Uses a dedicated fine-tuned model (promotion_badge_ocr.py), not
    # paddle_ocr's general stock recognizer - tested live this session and
    # stock PaddleOCR misread this exact badge (a level-I ship, "Gram") as a
    # bare "A" consistently across 1x-4x upscaling, a real failure on this
    # icon shape, not a resolution issue. See
    # ocr_training/generate_promotion_badge_data.py and
    # promotion_badge_ocr.py's docstring for how that model was trained and
    # its own known level-0 blind spot.
    box = require_field(layout.promotion_badge_box, "promotion_badge_box")
    img = screenshot_region(hwnd, box)
    return promotion_badge_ocr.read_promotion_badge(img)


def _is_maxed(hwnd, layout) -> bool:
    # Bounds the PROMOTE/PROMOTED button, a clean text signal unlike the
    # badge box above (whose maxed-state icon is ambiguous under OCR). OCR
    # picks up stray decorative bracket glyphs on either side of the button
    # text (e.g. "L PROMOTED ;" in testing) - check by substring rather than
    # an exact match.
    box = require_field(layout.promote_button_box, "promote_button_box")
    text = paddle_ocr.read_text(screenshot_region(hwnd, box))
    maxed = "PROMOTED" in text.upper()
    log.debug("Promote button OCR: %r -> maxed=%s", text, maxed)
    return maxed


def read_promotion_level(hwnd, layout) -> int:
    """Returns 0-6. Checks the PROMOTE/PROMOTED button first: a maxed
    ship's badge (in the same promotion_badge_box slot as every other
    level - see module docstring) has been misread as a stray "V" under
    the Roman-numeral OCR, reporting level 5 instead of 6. Checking maxed
    first avoids ever trusting that box's OCR on a maxed ship."""
    if _is_maxed(hwnd, layout):
        return 6

    text = _read_badge_text(hwnd, layout)
    level = _ROMAN_TO_LEVEL.get(text, 0)
    log.debug("Promotion badge OCR: %r -> level=%d", text, level)
    return level


def read_promotion(hwnd) -> dict:
    """Assumes the ship's detail view is currently showing, any tab active
    (same entry point convention as attribute_details/component_details)."""
    layout = get_layout(hwnd)
    click(hwnd, *layout.promote_tab)
    time.sleep(0.2)
    level = read_promotion_level(hwnd, layout)
    log.info("Promotion level: %d", level)
    return {"level": level}
