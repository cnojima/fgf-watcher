"""Read a ship's equipped components (up to 5): name, rarity, level, stat
block (Power/HP/INT/Command Points/Crit Resistance - not every component has
every stat), and set-bonus text if socketed into a set.

Reached from a ship's detail view: click the "COMPONENT" tab, then one of the
up to 5 equipped-component thumbnails at the bottom of the panel opens that
component's detail without navigating away - the other thumbnails stay
clickable in the same panel, so reading all 5 never needs to back out.
"""
import re
import time

from capture import screenshot_region
from input_control import click
from ocr import preprocess, pytesseract, read_text

# Confirmed via a direct, ungridded crop of the tab bar - not calibrate.py's
# zoom overlay, whose densely-packed ruler labels at this zoom level were
# genuinely hard to read correctly and gave a wrong x=785 for OVERVIEW_TAB
# the first time (785 apparently hit nothing, leaving the previous tab
# active, and the following clicks meant for Overview landed on unrelated
# elements and drifted to the Promote tab instead).
OVERVIEW_TAB = (1007, 1550)
COMPONENT_TAB = (1280, 1550)
PROMOTE_TAB = (1542, 1550)
# The Component tab has two distinct layouts: right after clicking
# COMPONENT_TAB it shows a grid of 5 icons arranged around the ship (with a
# "QUICK EQUIP" button below) and no detail panel; clicking any one of those
# icons opens the detail view (name/rarity/stats/set-bonus) with a *different*
# row of 5 small thumbnails at the bottom - that's what THUMBNAIL_POSITIONS
# below is calibrated against. Confirmed by a live run: going straight from
# COMPONENT_TAB to a THUMBNAIL_POSITIONS click (skipping this) landed those
# clicks on empty grid-view background/the tab bar instead, reading garbage.
FIRST_GRID_ICON = (980, 490)
# Thumbnail centers, confirmed via calibrate.py zoom against a live screenshot
# (a first attempt at these was calibrated against a stale/wrong source image
# and was off by 150-450px on every box in this module - re-derived from
# scratch against a fresh shot). Evenly spaced ~160px.
THUMBNAIL_POSITIONS = [(950, 1500), (1110, 1500), (1270, 1500), (1425, 1500), (1585, 1500)]

NAME_BOX = (1040, 540, 1700, 595)
RARITY_BOX = (1040, 595, 1700, 645)
# The "/30" max-level half of this text renders in a much lower-contrast grey
# than "Level 30" and Tesseract drops it entirely regardless of upscale (3x
# and 5x both tried) - not a box-size problem, a genuine low-contrast render.
# Accepting "Level N" without the max for now.
LEVEL_BOX = (1040, 650, 1400, 715)
STATS_BOX = (900, 760, 1700, 1030)
# Left edge of 960 was tuned empirically: narrower clipped real letters off
# *every* line ("Kinetic units" -> "netic units"), not just an icon
# overlapping the header - 960 fixes the description lines completely and
# leaves only minor icon-noise on the header's first couple characters
# ("Legendary" -> "Sk gendary"), which is an acceptable tradeoff since the
# header repeats the same known set name across every component anyway.
SET_BONUS_BOX = (960, 1055, 1700, 1230)

# Matches "POWER 167,414" or "Command Points 3" etc. Doesn't anchor a leading
# icon glyph OCR sometimes reads as a stray character (e.g. "\4 POWER...") -
# that gets stripped by _clean_leading_noise before this ever sees the line.
_STAT_LINE = re.compile(r"^([A-Za-z][A-Za-z ]*)\s+([\d,\.]+%?)")


def _clean_leading_noise(line: str) -> str:
    return re.sub(r"^[^A-Za-z]+", "", line.strip())


def _read_multiline(hwnd, box: tuple[int, int, int, int]) -> str:
    img = screenshot_region(hwnd, box)
    return pytesseract.image_to_string(preprocess(img, upscale=2), config="--psm 6").strip()


def _read_stats(hwnd) -> dict[str, str]:
    stats = {}
    for line in _read_multiline(hwnd, STATS_BOX).splitlines():
        m = _STAT_LINE.match(_clean_leading_noise(line))
        if m:
            stats[m.group(1).strip()] = m.group(2)
    return stats


def read_component(hwnd) -> dict:
    # Trailing "—" (em dash) on some reads is noise from a small lock/lvl-max
    # icon at the box's right edge, not part of the name - strip it.
    name = read_text(screenshot_region(hwnd, NAME_BOX), upscale=3).rstrip(" —")
    rarity = read_text(screenshot_region(hwnd, RARITY_BOX), upscale=3).rstrip(" _")
    level = read_text(screenshot_region(hwnd, LEVEL_BOX), upscale=3)
    return {
        "name": name,
        "rarity": rarity,
        "level": level,
        "stats": _read_stats(hwnd),
        "set_bonus": _read_multiline(hwnd, SET_BONUS_BOX),
    }


def read_all_components(hwnd) -> list[dict]:
    """Assumes the ship's Overview tab is currently showing (i.e. same entry
    point as attribute_details.read_attribute_details)."""
    click(hwnd, *COMPONENT_TAB)
    time.sleep(0.6)
    click(hwnd, *FIRST_GRID_ICON)  # enter the detail view for the first time
    time.sleep(0.6)

    components = []
    for position in THUMBNAIL_POSITIONS:
        click(hwnd, *position)
        time.sleep(0.6)
        components.append(read_component(hwnd))
    return components
