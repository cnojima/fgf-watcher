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
from pathlib import Path

from capture import screenshot_region, screenshot_window
from input_control import click
from ocr import preprocess, pytesseract, read_text
from profiles.ui_layout import get_layout, require_field

DEBUG_DIR = Path(__file__).resolve().parent.parent / "data"

# The Component tab has two distinct layouts: right after clicking
# component_tab it shows a grid of 5 icons arranged around the ship (with a
# "QUICK EQUIP" button below) and no detail panel; clicking any one of those
# icons opens the detail view (name/rarity/stats/set-bonus) with a *different*
# row of 5 small thumbnails at the bottom - that's what layout.thumbnail_positions
# is calibrated against. Confirmed by a live run: going straight from
# component_tab to a thumbnail-position click (skipping this) landed those
# clicks on empty grid-view background/the tab bar instead, reading garbage.

# Matches "POWER 167,414" or "Command Points 3" etc. Doesn't anchor a leading
# icon glyph OCR sometimes reads as a stray character (e.g. "\4 POWER...") -
# that gets stripped by _clean_leading_noise before this ever sees the line.
_STAT_LINE = re.compile(r"^([A-Za-z][A-Za-z ]*)\s+([\d,\.]+%?)")


def _clean_leading_noise(line: str) -> str:
    return re.sub(r"^[^A-Za-z]+", "", line.strip())


def _read_multiline(hwnd, box: tuple[int, int, int, int]) -> str:
    img = screenshot_region(hwnd, box)
    return pytesseract.image_to_string(preprocess(img, upscale=2), config="--psm 6").strip()


def _read_stats(hwnd, layout) -> dict[str, str]:
    stats_box = require_field(layout.component_stats_box, "component_stats_box")
    stats = {}
    for line in _read_multiline(hwnd, stats_box).splitlines():
        m = _STAT_LINE.match(_clean_leading_noise(line))
        if m:
            stats[m.group(1).strip()] = m.group(2)
    return stats


def read_component(hwnd, layout) -> dict:
    # Trailing "—" (em dash) on some reads is noise from a small lock/lvl-max
    # icon at the box's right edge, not part of the name - strip it.
    name_box = require_field(layout.component_name_box, "component_name_box")
    rarity_box = require_field(layout.component_rarity_box, "component_rarity_box")
    level_box = require_field(layout.component_level_box, "component_level_box")
    set_bonus_box = require_field(layout.component_set_bonus_box, "component_set_bonus_box")
    name = read_text(screenshot_region(hwnd, name_box), upscale=3).rstrip(" —")
    rarity = read_text(screenshot_region(hwnd, rarity_box), upscale=3).rstrip(" _")
    level = read_text(screenshot_region(hwnd, level_box), upscale=3)
    return {
        "name": name,
        "rarity": rarity,
        "level": level,
        "stats": _read_stats(hwnd, layout),
        "set_bonus": _read_multiline(hwnd, set_bonus_box),
    }


def read_all_components(hwnd, name) -> list[dict]:
    """Assumes the ship's Overview tab is currently showing (i.e. same entry
    point as attribute_details.read_attribute_details)."""
    print(f"{name}: collecting Component Details")
    layout = get_layout(hwnd)

    # Debug evidence, not a guess: if this tab switch isn't landing, look at
    # what was actually on screen the instant before the click fired (e.g.
    # still showing the previous overlay mid-close) rather than re-guessing
    # the coordinate blind - see CLAUDE.md.
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    screenshot_window(hwnd).save(DEBUG_DIR / "_debug_before_component_tab_click.png")

    click(hwnd, *layout.component_tab)
    time.sleep(0.6)
    screenshot_window(hwnd).save(DEBUG_DIR / "_debug_after_component_tab_click.png")
    click(hwnd, *require_field(layout.first_grid_icon, "first_grid_icon"))  # enter the detail view for the first time
    time.sleep(0.6)

    components = []
    for position in require_field(layout.thumbnail_positions, "thumbnail_positions"):
        click(hwnd, *position)
        time.sleep(0.6)
        components.append(read_component(hwnd, layout))
    return components
