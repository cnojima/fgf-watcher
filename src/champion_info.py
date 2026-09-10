"""Read a champion's Info tab: name, title, quality, element, champion
type, level, and power.

Quality ("LEGENDARY"/"EPIC") is plain OCR-able text - no icon matching
needed, unlike element and type which are icon-only badges here (their
plain-text equivalents only show up on the weapon detail page - see
champion_weapon.py).

Element reuses the same icons/elements/ library built for flagships -
confirmed live that champions render the identical kinetic/beam/ion badge
art.

Champion type is a new icons/champion_types/ library, self-derived from
live captures rather than hand-supplied: the weapon detail page happens to
show the same icon next to a plain-text label ("ATTACK"), so a crop from
that page could be paired with ground truth directly. Only "attack" is
confirmed this way so far; a second icon (a green gear/cog glyph, seen on
an unweaponed champion with no text label available to confirm it) is
saved as "support_unconfirmed.png" - a guess, not a confirmed reading, per
the same "don't invent unconfirmed data" precedent as
attribute_details.py's KNOWN_SUBROW_LABELS "Construction" entry. Expect
icon_match to return None (logged as a warning) for any other type until
more reference icons are added.
"""
import logging
import re

import ocr_easy
from capture import screenshot_region
from icon_match import match_icon
from ocr import read_text
from profiles.champion_layout import ChampionLayout

log = logging.getLogger(__name__)

# Maps common EasyOCR letter/digit confusions back to digits - only safe to
# apply to a field known to be purely numeric (like a level number).
_DIGIT_CONFUSION = str.maketrans({
    "I": "1", "l": "1", "i": "1", "O": "0", "o": "0",
    "S": "5", "s": "5", "Z": "2", "z": "2", "B": "8", "g": "9",
})


def _read_level(hwnd, layout: ChampionLayout) -> int | None:
    # Tesseract reads this octagon-badge level number as pure garbage under
    # every PSM mode and threshold tried, despite a visibly clean, correctly
    # bounded crop - the same "genuine font limitation" pattern CLAUDE.md
    # documents for the ship "FLAGSHIP" title. EasyOCR reads it far closer
    # (e.g. "Izi" for "121") but with predictable letter/digit confusion;
    # since this field is always purely numeric, translating those specific
    # confusions back to digits recovers the correct value.
    text = ocr_easy.read_text(screenshot_region(hwnd, layout.level_box))
    digits = re.sub(r"[^\d]", "", text.translate(_DIGIT_CONFUSION))
    return int(digits) if digits else None


def _clean_leading_noise(text: str) -> str:
    return re.sub(r"^[^A-Za-z0-9]*[A-Za-z]{0,2}\s+(?=[A-Z0-9])", "", text.strip())


def read_info(hwnd, layout: ChampionLayout) -> dict:
    """Assumes the champion's Info tab is currently showing."""
    name = read_text(screenshot_region(hwnd, layout.name_box), upscale=3)
    title = read_text(screenshot_region(hwnd, layout.title_box), upscale=3)
    quality = _clean_leading_noise(read_text(screenshot_region(hwnd, layout.quality_box), upscale=3))
    element = match_icon(screenshot_region(hwnd, layout.element_icon_box), "elements")
    champion_type = match_icon(screenshot_region(hwnd, layout.type_icon_box), "champion_types")
    level = _read_level(hwnd, layout)
    power = _clean_leading_noise(read_text(screenshot_region(hwnd, layout.power_box), upscale=3))

    log.info(
        "%s (%s): quality=%s element=%s type=%s level=%s power=%s",
        name, title, quality, element, champion_type, level, power,
    )
    return {
        "name": name,
        "title": title,
        "quality": quality,
        "element": element,
        "type": champion_type,
        "level": level,
        "power": power,
    }
