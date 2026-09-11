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

import orange_kid_ocr
import paddle_ocr
import paddle_ocr_blocks
from capture import screenshot_region, screenshot_window
from input_control import click
from nav import back
from profiles.champion_layout import ChampionLayout, require_field
from profiles.notifications import dismiss_if_present
from scroll_stitch import stitch_scrolled_region

log = logging.getLogger(__name__)

_STAT_LINE = re.compile(r"^([A-Za-z][A-Za-z ]*)\s+([\d,\.]+%?)")

_ELEMENTS = ("kinetic", "beam", "ion")
_TYPES = ("attack", "defense", "support", "healing")

# A weapon name is letters/spaces/apostrophes/hyphens only (e.g. "Endless
# Whisper", "Widow's Kiss") - used to catch a badly-timed capture without
# needing to know what a *correct* name looks like. Confirmed live: an
# in-game notification banner ("Congratulations to [Guild]Name on
# becoming...") sliding across this exact box at the moment of capture
# corrupted a real weapon's name to "be (}" - non-empty, so the existing
# "if not name" check let it through silently. Both this pattern check and
# the element/type "total fuzzy-match failure" case below are the same
# underlying banner-timing issue as this module's own docstring already
# describes for badge_text ("Se cae a" for a badly-timed capture) - not
# fixed by re-positioning any box, since the banner is transient, not
# mispositioned content.
_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z\s'-]*$")

_FINGERPRINT_TOLERANCE = 25


def has_weapon_equipped(hwnd, layout: ChampionLayout) -> bool:
    """Assumes the champion's Info tab is currently showing. Checks the
    weapon badge's pixel fingerprint WITHOUT clicking it - the "+"
    no-weapon placeholder must never be clicked into (per explicit
    instruction), so this is checked before weapon_badge_click, not
    inferred after the fact from an empty read.

    weapon_badge_empty_fingerprint is a tuple of VARIANTS (each its own
    tuple of (x, y, expected_rgb) points), not one fixed fingerprint -
    confirmed live the empty placeholder's ring is a translucent overlay
    that picks up the page's own quality-tier background color rather than
    a single universal tint (Doug Rockwell, LEGENDARY/warm-gold background,
    read a completely different color at these exact points than Klara,
    EPIC/teal background - a ~60-point swing on the red channel alone, far
    past any tolerance that would still safely exclude a real equipped
    weapon's badge art). Equipped is "no variant fully matched", not "any
    single point differed" - a badge only reads as empty if ALL points of
    at least one known variant line up."""
    img = screenshot_window(hwnd)
    variants = require_field(layout.weapon_badge_empty_fingerprint, "weapon_badge_empty_fingerprint")
    for variant in variants:
        if all(
            all(abs(img.getpixel((x, y))[i] - expected[i]) <= _FINGERPRINT_TOLERANCE for i in range(3))
            for x, y, expected in variant
        ):
            return False
    return True


def is_weapon_maxed(hwnd, layout: ChampionLayout) -> bool:
    """Assumes the weapon detail page is currently showing. Checks the
    "MAX-LEVEL PREVIEW" button's pixel fingerprint (see
    ChampionLayout.weapon_maxed_fingerprint) to tell the maxed-weapon
    variant of this page apart from the plain single-weapon preview and
    "Select Weapon" browse variants documented in close_weapon_page - same
    "one screen, two layouts" pattern as promotion_details.py's maxed-ship
    badge (see CLAUDE.md). Unlike has_weapon_equipped's "any point differs"
    check, this is an "all points match" check, same style as
    profiles/fingerprints.py's current_screen()."""
    img = screenshot_window(hwnd)
    fingerprint = require_field(layout.weapon_maxed_fingerprint, "weapon_maxed_fingerprint")
    return all(
        all(abs(img.getpixel((x, y))[i] - expected[i]) <= _FINGERPRINT_TOLERANCE for i in range(3))
        for x, y, expected in fingerprint
    )


def _find_keyword(text: str, vocabulary: tuple[str, ...]) -> str | None:
    upper = text.upper()
    for word in re.findall(r"[A-Za-z]+", upper):
        match = difflib.get_close_matches(word, [v.upper() for v in vocabulary], n=1, cutoff=0.7)
        if match:
            return match[0].lower()
    # A clean OCR read (PaddleOCR) can merge two adjacent badge words with
    # no space between them ("KINETICATTACK") where Tesseract's garbled
    # output happened to keep them apart - substring match catches that;
    # skipped above since fuzzy-matching the merged blob against a whole
    # vocabulary word almost never clears the 0.7 cutoff.
    for v in vocabulary:
        if v.upper() in upper:
            return v.lower()
    return None


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
        hwnd, require_field(layout.weapon_stats_box, "weapon_stats_box"),
        require_field(layout.weapon_stats_drag_from, "weapon_stats_drag_from"),
        require_field(layout.weapon_stats_drag_to, "weapon_stats_drag_to"),
        layout.weapon_stats_expected_scroll_offset, max_scrolls=10,
    )
    text = paddle_ocr_blocks.read_text_block(composite)
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
    each is opened, read, and closed again before touching the other one.

    weapon_bonus_info_box being uncalibrated is treated as "this weapon page
    variant doesn't support the toggle" rather than require_field's usual
    "coordinate unknown" - confirmed live on a maxed Signature Weapon page
    (Zora Domini's "Endless Whisper"): clicking weapon_bonus_icons produced
    a strict zero-diff screenshot comparison (no overlay, no highlight,
    nothing), unlike every other click in this codebase which visibly
    changes something. Not yet confirmed whether a regular, non-signature
    weapon behaves differently - if one does support the toggle, calibrate
    weapon_bonus_info_box for it and this early-return stops applying."""
    if layout.weapon_bonus_info_box is None:
        log.debug("weapon_bonus_info_box not calibrated - skipping bonus read for this weapon")
        return {}

    bonuses = {}
    icons = require_field(layout.weapon_bonus_icons, "weapon_bonus_icons")
    info_box = layout.weapon_bonus_info_box
    for slot, (x, y) in zip(_BONUS_SLOTS, icons):
        click(hwnd, x, y)
        time.sleep(0.4)
        img = screenshot_region(hwnd, info_box)
        bonuses[slot] = paddle_ocr_blocks.read_text_block(img)
        click(hwnd, x, y)  # close it again before the next one
        time.sleep(0.3)
    return bonuses


def read_weapon(hwnd, layout: ChampionLayout) -> dict:
    """Assumes the weapon detail page is currently showing (caller clicks
    weapon_badge_click first, only once has_weapon_equipped() confirmed one
    is - so an empty/garbled read here is a bad capture, not a real "no
    weapon" case)."""
    # The global notification banner (see profiles/notifications.py) can be
    # covering name_box/weapon_element_type_box right as this page opens -
    # dismiss it upfront rather than relying solely on the retries below,
    # which only catch it after the fact.
    dismiss_if_present(hwnd)

    name_box = require_field(layout.weapon_name_box, "weapon_name_box")
    name = paddle_ocr.read_text(screenshot_region(hwnd, name_box))
    if not name or not _NAME_PATTERN.match(name):
        # Still-uncaught overlay (banner slid in after the check above, or
        # some other render-timing miss) - one retry after a brief pause,
        # same "wait it out" fix used elsewhere in this codebase (e.g.
        # collect_all_flagships._read_ship_name).
        time.sleep(0.5)
        name = paddle_ocr.read_text(screenshot_region(hwnd, name_box))
    if not name:
        log.warning("weapon_name_box read empty even after retry - proceeding with an empty name")

    badge_box = require_field(layout.weapon_element_type_box, "weapon_element_type_box")
    badge_text = paddle_ocr.read_text(screenshot_region(hwnd, badge_box))
    element = _find_keyword(badge_text, _ELEMENTS)
    weapon_type = _find_keyword(badge_text, _TYPES)
    if element is None and weapon_type is None:
        # Total fuzzy-match failure on both vocabularies at once is the
        # signature of a badly-timed capture (see this module's docstring)
        # rather than a genuinely unmatched word - one retry, same reasoning
        # as the name retry above.
        time.sleep(0.5)
        badge_text = paddle_ocr.read_text(screenshot_region(hwnd, badge_box))
        element = _find_keyword(badge_text, _ELEMENTS)
        weapon_type = _find_keyword(badge_text, _TYPES)
    # Same "orange kid" badge font as champion_info.py's level field - see
    # its docstring and ocr_training/ for how this model replaced the old
    # Tesseract/EasyOCR attempts.
    level = orange_kid_ocr.read_level(screenshot_region(hwnd, layout.weapon_level_box))

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
    actually showing before deciding how to close it is the fix.

    weapon_select_list_label_box being uncalibrated means the browse variant
    hasn't been confirmed to exist on this platform yet (every weapon page
    reached so far has been the plain single-weapon preview) - falls back
    to the ordinary back() close rather than require_field's usual error,
    since that's the variant actually seen. If a browse variant does turn
    up, calibrate weapon_select_list_label_box/_close and this bypass stops
    applying."""
    if layout.weapon_select_list_label_box is not None:
        label_text = paddle_ocr.read_text(screenshot_region(hwnd, layout.weapon_select_list_label_box))
        if "select" in label_text.lower():
            log.debug("Weapon page is the 'Select Weapon' browse variant - closing via its X button")
            click(hwnd, *require_field(layout.weapon_select_list_close, "weapon_select_list_close"))
            time.sleep(0.5)
            return
    back(hwnd)
    time.sleep(0.5)
