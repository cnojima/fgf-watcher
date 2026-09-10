"""Read a ship's current promotion level (0-6) from its Promote tab.

Reached from a ship's detail view: click the Promote tab. For a ship that can
still be promoted further (levels 0-5), the current level renders as a
stylized triangle badge in a "current -> next" comparison row (current
badge, a green chevron, the next level's badge in a brighter/gold style,
plus a small reward-unlock icon) - a Roman numeral (I-V) for levels 1-5, or
a muted star/cross glyph (no numeral) for level 0. Confirmed via live
screenshots of a level-I ship (Gram) and a level-0 ship (Demerzel) - both
share the same panel layout, just a different badge in the same slot.

A maxed ship (level 6) uses a *different* panel layout entirely: no
progress row, no chevron, no reward preview - just a gold-framed header
with a bright teal/gold star badge (in a different position than the
level-0/1-5 badge slot, since removing the progress row shifts everything
below it up), followed by the stat table and a disabled "PROMOTED" button
where an unmaxed ship shows an enabled "PROMOTE" button. Confirmed via a
live screenshot of a maxed Gram. Because the badge itself moves between
these two layouts, level 6 is *not* detected by classifying a badge image -
it's detected by OCRing the PROMOTE/PROMOTED button, which stays in the
same place across every promotion state and gives a clean text signal
("PROMOTED" vs "PROMOTE") instead of an unverified icon/shape comparison.
"""
import time

from capture import screenshot_region
from input_control import click
from ocr import preprocess, pytesseract, read_text
from profiles.ui_layout import get_layout, require_field

_ROMAN_TO_LEVEL = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}


def _read_badge_text(hwnd, layout) -> str:
    # Tightly bounds the triangle badge in the "current level" slot of the
    # progress row a level-0/1-5 ship shows. Not meaningful for a maxed ship
    # (see module docstring) - only used to detect levels 0-5.
    box = require_field(layout.promotion_badge_box, "promotion_badge_box")
    img = screenshot_region(hwnd, box)
    config = "--psm 10 -c tessedit_char_whitelist=IV"
    return pytesseract.image_to_string(preprocess(img, upscale=3), config=config).strip()


def _is_maxed(hwnd, layout) -> bool:
    # Bounds the PROMOTE/PROMOTED button, which sits at this same position
    # regardless of promotion state (unlike the badge above, this panel
    # element doesn't move between the two layouts). OCR picks up stray
    # decorative bracket glyphs on either side of the button text (e.g. "L
    # PROMOTED ;" in testing) - check by substring rather than an exact match.
    box = require_field(layout.promote_button_box, "promote_button_box")
    text = read_text(screenshot_region(hwnd, box))
    return "PROMOTED" in text.upper()


def read_promotion_level(hwnd, layout) -> int:
    """Returns 0-6. Checks the level-0/1-5 badge first; an unrecognized
    badge (which also covers a maxed ship, whose badge has moved out of
    this box - see module docstring) falls back to the PROMOTE/PROMOTED
    button text to tell level 0 apart from max (6)."""
    text = _read_badge_text(hwnd, layout)
    if text in _ROMAN_TO_LEVEL:
        return _ROMAN_TO_LEVEL[text]

    return 6 if _is_maxed(hwnd, layout) else 0


def read_promotion(hwnd) -> dict:
    """Assumes the ship's detail view is currently showing, any tab active
    (same entry point convention as attribute_details/component_details)."""
    layout = get_layout(hwnd)
    click(hwnd, *layout.promote_tab)
    time.sleep(0.6)
    return {"level": read_promotion_level(hwnd, layout)}
