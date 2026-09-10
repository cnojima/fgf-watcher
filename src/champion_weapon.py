"""Read a champion's equipped weapon (name, element, type, level, stats)
from the weapon detail page.

Reached by clicking the weapon badge on the champion's Info tab
(champion_layout.weapon_badge_click) - NOT the top-right icon (that one
always opens the champion's lore/bio page, "<Name>'s past experience",
confirmed live on two different champions; an earlier reading mistook it
for a weapon shortcut because one test happened to land on the weapon badge
instead due to a stale click coordinate).

A champion with no weapon equipped shows a "+" placeholder in the badge's
slot instead (confirmed live: Lucius Pullo). Per explicit instruction, that
placeholder must never be clicked into at all - has_weapon_equipped() checks
a pixel fingerprint (see ChampionLayout.weapon_badge_empty_fingerprint) to
detect this BEFORE clicking weapon_badge_click, not by clicking and reading
an empty result afterward.

Unlike the Info tab's icon-only element/type badges, this page's badges are
plain text ("KINETIC", "ATTACK") - OCR'd directly, no icon_match needed.
Element is one of the same three known values as icons/elements/
(kinetic/beam/ion); type is one of the four the user confirmed weapons
share with champions (attack/defense/support/healing) - confirmed live
across the first full roster collection that a weapon's type does NOT
always match its champion's own type (e.g. Doug Rockwell reads as an
Attack-type champion but was equipped with a Healing-type weapon), so
these are read independently and never cross-checked against
champion_info's type. Matched by fuzzy word search rather than a fixed
substring/position, since this text is often heavily garbled (e.g. "G
KINETIC {@) DEFENSE", or total noise like "Se cae a" for a badly-timed
capture) - a word that doesn't resemble either vocabulary closely enough
is dropped rather than forced to the nearest (possibly wrong) guess.
"""
import difflib
import logging
import re
import time

from capture import screenshot_region, screenshot_window
from input_control import click
from nav import back
from ocr import preprocess, pytesseract, read_text
from profiles.champion_layout import ChampionLayout
from scroll_stitch import stitch_scrolled_region

log = logging.getLogger(__name__)

_STAT_LINE = re.compile(r"^([A-Za-z][A-Za-z ]*)\s+([\d,\.]+%?)")

_ELEMENTS = ("kinetic", "beam", "ion")
_TYPES = ("attack", "defense", "support", "healing")

_FINGERPRINT_TOLERANCE = 25


def has_weapon_equipped(hwnd, layout: ChampionLayout) -> bool:
    """Assumes the champion's Info tab is currently showing. Checks the
    weapon badge's pixel fingerprint WITHOUT clicking it - the "+"
    no-weapon placeholder must never be clicked into (per explicit
    instruction), so this is checked before weapon_badge_click, not
    inferred after the fact from an empty read."""
    img = screenshot_window(hwnd)
    for x, y, expected in layout.weapon_badge_empty_fingerprint:
        actual = img.getpixel((x, y))
        if any(abs(actual[i] - expected[i]) > _FINGERPRINT_TOLERANCE for i in range(3)):
            return True
    return False


def _find_keyword(text: str, vocabulary: tuple[str, ...]) -> str | None:
    for word in re.findall(r"[A-Za-z]+", text.upper()):
        match = difflib.get_close_matches(word, [v.upper() for v in vocabulary], n=1, cutoff=0.7)
        if match:
            return match[0].lower()
    return None


def _read_int(hwnd, layout: ChampionLayout, box_attr: str) -> int | None:
    box = getattr(layout, box_attr)
    text = read_text(screenshot_region(hwnd, box), upscale=3)
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def _clean_leading_noise(line: str) -> str:
    return re.sub(r"^[^A-Za-z]+", "", line.strip())


def _join_wrapped_lines(text: str) -> list[str]:
    # A label too long to fit one line wraps (e.g. "Kinetic DMG Advantage"
    # / "Boost 0%"), splitting the label from its value across two OCR'd
    # lines - same wrapped-header problem attribute_details.py solved for
    # the ship attribute table (see its _join_wrapped_lines). Any line with
    # no trailing number is a continuation of the next line, not its own row.
    joined: list[str] = []
    buffer = ""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        buffer = f"{buffer} {line}".strip() if buffer else line
        if re.search(r"[\d,\.]+%?\s*$", buffer):
            joined.append(buffer)
            buffer = ""
    if buffer:
        joined.append(buffer)
    return joined


def _read_stats(hwnd, layout: ChampionLayout) -> dict[str, str]:
    # The stats list (9 rows: POWER, Kinetic DMG Advantage Boost, 3x
    # Formation bonuses, 4x Champion stats) doesn't fit in
    # weapon_stats_box's visible height (~5 rows) and is drag-scrollable -
    # confirmed live. Scrolled and stitched the same way as the ship
    # attribute table (see scroll_stitch.py) rather than OCR'd once, which
    # was silently dropping the last 2-4 rows before this.
    composite = stitch_scrolled_region(
        hwnd, layout.weapon_stats_box, layout.weapon_stats_drag_from, layout.weapon_stats_drag_to,
        layout.weapon_stats_expected_scroll_offset, max_scrolls=10,
    )
    text = pytesseract.image_to_string(preprocess(composite, upscale=2), config="--psm 6").strip()
    stats = {}
    for line in _join_wrapped_lines(text):
        m = _STAT_LINE.match(_clean_leading_noise(line))
        if m:
            stats[m.group(1).strip()] = m.group(2)
    return stats


_BONUS_SLOTS = ("space_combat", "ground_combat")


def _read_bonuses(hwnd, layout: ChampionLayout) -> dict[str, str]:
    """Reads the two "Lvl N" bonus badges (space combat, ground combat) -
    each an independent toggle (see ChampionLayout.weapon_bonus_icons), so
    each is opened, read, and closed again before touching the other one."""
    bonuses = {}
    for slot, (x, y) in zip(_BONUS_SLOTS, layout.weapon_bonus_icons):
        click(hwnd, x, y)
        time.sleep(0.4)
        img = screenshot_region(hwnd, layout.weapon_bonus_info_box)
        bonuses[slot] = pytesseract.image_to_string(preprocess(img, upscale=2), config="--psm 6").strip()
        click(hwnd, x, y)  # close it again before the next one
        time.sleep(0.3)
    return bonuses


def read_weapon(hwnd, layout: ChampionLayout) -> dict | None:
    """Assumes the weapon detail page is currently showing (caller clicks
    weapon_badge_click first). Returns None if no weapon is equipped."""
    name = read_text(screenshot_region(hwnd, layout.weapon_name_box), upscale=3)
    if not name:
        log.info("No weapon equipped")
        return None

    badge_text = read_text(screenshot_region(hwnd, layout.weapon_element_type_box), upscale=3)
    element = _find_keyword(badge_text, _ELEMENTS)
    weapon_type = _find_keyword(badge_text, _TYPES)
    level = _read_int(hwnd, layout, "weapon_level_box")

    result = {
        "name": name,
        "element": element,
        "type": weapon_type,
        "level": level,
        "stats": _read_stats(hwnd, layout),
        "bonuses": _read_bonuses(hwnd, layout),
    }
    log.info("Weapon: %s (element=%s type=%s level=%s)", name, element, weapon_type, level)
    return result


def close_weapon_page(hwnd, layout: ChampionLayout) -> None:
    """Closes the weapon detail page back to the champion's Info tab.

    This page has two variants with identical name/badge/level/stats field
    positions (read_weapon works unchanged on both) but different close
    controls: a plain single-weapon preview (back-arrow, same as the rest
    of the champion detail view) and a "Select Weapon" browse variant
    (multiple owned weapons, an EQUIP button) that closes via an X button
    at a completely different position instead. Confirmed live the hard
    way: calling back() on the browse variant silently failed to close it,
    and every subsequent grid click in a batch run landed on whatever
    weapon was left on screen instead of the next champion - cascading
    garbage data across the rest of that run. Checking which variant is
    actually showing before deciding how to close it is the fix."""
    label_text = read_text(screenshot_region(hwnd, layout.weapon_select_list_label_box), upscale=3)
    if "select" in label_text.lower():
        log.debug("Weapon page is the 'Select Weapon' browse variant - closing via its X button")
        click(hwnd, *layout.weapon_select_list_close)
    else:
        back(hwnd)
    time.sleep(0.5)
