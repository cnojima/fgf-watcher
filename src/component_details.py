"""Read a ship's equipped components (up to 5): name, rarity, level, stat
block (Power/HP/INT/Command Points/Crit Resistance - not every component has
every stat), and set-bonus text if socketed into a set.

Reached from a ship's detail view: click the "COMPONENT" tab, then one of the
up to 5 equipped-component thumbnails at the bottom of the panel opens that
component's detail without navigating away - the other thumbnails stay
clickable in the same panel, so reading all 5 never needs to back out.
"""
import logging
import re
import time
from pathlib import Path

import paddle_ocr
import paddle_ocr_blocks
from capture import screenshot_region, screenshot_window
from input_control import click
from profiles.ui_layout import get_layout, require_field

DEBUG_DIR = Path(__file__).resolve().parent.parent / "data"
log = logging.getLogger(__name__)

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
_COMPOUND_STAT_TOKENS = frozenset({"HP", "ATTACK", "INT", "DEF"})


def _clean_leading_noise(line: str) -> str:
    return re.sub(r"^[^A-Za-z]+", "", line.strip())


def _read_multiline(hwnd, box: tuple[int, int, int, int]) -> str:
    img = screenshot_region(hwnd, box)
    return paddle_ocr_blocks.read_text_block(img)


def _read_stats(hwnd, layout) -> dict[str, str]:
    stats_box = require_field(layout.component_stats_box, "component_stats_box")
    stats = {}
    for line in _read_multiline(hwnd, stats_box).splitlines():
        m = _STAT_LINE.match(_clean_leading_noise(line))
        if m:
            label = m.group(1).strip()
            value = m.group(2)
            tokens = label.split()
            if len(tokens) > 1 and all(token in _COMPOUND_STAT_TOKENS for token in tokens):
                stats.update({token: value for token in tokens})
            else:
                stats[label] = value
    return stats


def _normalize_name(name: str) -> str:
    # Component names are plain ASCII, "<Base> - <Part>" (e.g. "Thor Gen6 -
    # Control Cube"), using a regular hyphen. OCR occasionally injects a
    # stray non-ASCII glyph that isn't part of the real text - either glued
    # onto a word (e.g. "Gen6é - Control Cube": the "-" itself already
    # read correctly, "é" is pure extra noise, confirmed against a live
    # screenshot of this exact component showing plain "Thor Gen6 - Control
    # Cube") or trailing alone from a small icon at the box's right edge
    # (e.g. "Name —"). Deleting stray non-ASCII characters outright
    # recovers the correct text in both cases.
    name = re.sub(r"[^\x00-\x7F]", "", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip(" -")


def read_component(hwnd, layout) -> dict:
    name_box = require_field(layout.component_name_box, "component_name_box")
    rarity_box = require_field(layout.component_rarity_box, "component_rarity_box")
    level_box = require_field(layout.component_level_box, "component_level_box")
    set_bonus_box = require_field(layout.component_set_bonus_box, "component_set_bonus_box")
    name = _normalize_name(paddle_ocr.read_text(screenshot_region(hwnd, name_box)))
    rarity = paddle_ocr.read_text(screenshot_region(hwnd, rarity_box)).rstrip(" _")
    level = paddle_ocr.read_text(screenshot_region(hwnd, level_box))
    log.debug("Component: name=%r rarity=%r level=%r", name, rarity, level)
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
    log.info("%s: collecting Component Details", name)
    layout = get_layout(hwnd)

    # Debug evidence, not a guess: if this tab switch isn't landing, look at
    # what was actually on screen the instant before the click fired (e.g.
    # still showing the previous overlay mid-close) rather than re-guessing
    # the coordinate blind - see CLAUDE.md.
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    screenshot_window(hwnd).save(DEBUG_DIR / "_debug_before_component_tab_click.png")

    click(hwnd, *layout.component_tab)
    time.sleep(0.2)
    screenshot_window(hwnd).save(DEBUG_DIR / "_debug_after_component_tab_click.png")
    click(hwnd, *require_field(layout.first_grid_icon, "first_grid_icon"))  # enter the detail view for the first time
    time.sleep(0.2)

    components = []
    for position in require_field(layout.thumbnail_positions, "thumbnail_positions"):
        click(hwnd, *position)
        time.sleep(0.2)
        components.append(read_component(hwnd, layout))
    log.info("%s: read %d component(s)", name, len(components))
    return components
