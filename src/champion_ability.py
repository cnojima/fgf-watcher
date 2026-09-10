"""Read a champion's 7 abilities (3 Space Combat, 1 Ultimate, 3 Ground
Combat) from the Ability tab's icon selector.

Clicking each of the 7 icons updates an info card below it: a fixed header
(name, tag like "[Space: Active Ability]", "LEVEL N/N") plus a description
that routinely doesn't fit in one capture (confirmed live: "Missile count
increases to 11" and an entire "Signature Weapon" section were silently cut
off before this scrolled) - scrolled and stitched the same way as the
weapon stats list (see scroll_stitch.py; ability_header_box and
ability_scroll_box were split out by diffing before/after-scroll
screenshots pixel-by-pixel to find exactly which band actually scrolls).
Read as one multi-line OCR blob rather than parsed into fixed fields, since
ability names/descriptions are different for every champion (confirmed by
the user directly) and there's no shared vocabulary to anchor a stricter
parse against, unlike e.g. attribute_details.py's closed set of sub-row
labels.

The Ultimate ability (center icon) is locked until the champion's star
level is maxed (30) - confirmed live via a visible lock glyph over it on a
level-17 champion. Reading a locked ability's info box will just capture
whatever placeholder text the game shows for it; not specially handled
here since that placeholder text is itself useful signal (distinguishes
"not yet unlocked" from a real ability's content) for a caller that wants
one.
"""
import logging
import time

from capture import screenshot_region
from input_control import click
from ocr import preprocess, pytesseract
from profiles.champion_layout import ChampionLayout
from scroll_stitch import stitch_scrolled_region

log = logging.getLogger(__name__)

_ABILITY_SLOTS = ("space_1", "space_2", "space_3", "ultimate", "ground_1", "ground_2", "ground_3")


def _ocr_multiline(img) -> str:
    return pytesseract.image_to_string(preprocess(img, upscale=2), config="--psm 6").strip()


def _read_ability_card(hwnd, layout: ChampionLayout) -> str:
    header = _ocr_multiline(screenshot_region(hwnd, layout.ability_header_box))
    composite = stitch_scrolled_region(
        hwnd, layout.ability_scroll_box, layout.ability_scroll_drag_from, layout.ability_scroll_drag_to,
        layout.ability_expected_scroll_offset, max_scrolls=8,
    )
    return f"{header}\n{_ocr_multiline(composite)}"


def read_abilities(hwnd, layout: ChampionLayout) -> dict[str, str]:
    """Assumes the champion's Ability tab is currently showing. Clicks each
    of the 7 ability icons in turn and returns {slot_name: full_card_text}."""
    abilities = {}
    for slot, (x, y) in zip(_ABILITY_SLOTS, layout.ability_icons):
        click(hwnd, x, y)
        time.sleep(0.4)
        abilities[slot] = _read_ability_card(hwnd, layout)
    log.info("Read %d abilities", len(abilities))
    return abilities
