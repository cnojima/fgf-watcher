"""Navigate to and enumerate the Champion collection grid.

Reached from a base view (system_map/city_view) by clicking the "Champion"
icon in the bottom bar - NOT nav.py's "c" overlay shortcut, which failed to
open this screen live in testing (landed back on system_map instead,
likely a focus issue - possibly chat input capturing the keystroke).
champion_layout.champion_grid_icon is a direct, reliable click instead.

The grid is 5 columns wide and N rows tall, card order left-to-right,
top-to-bottom. Each cell is one of three states, told apart by OCRing its
bottom status-text region (see ChampionLayout.card_status_offset):
  - "empty": no digits at all - no card in this cell (past the end of the
    roster for this row).
  - "locked": digits with a "/" - an unrecruited card showing progress
    (e.g. "0/40"), not a real champion yet.
  - "unlocked": digits with no "/" - a real champion (the OCR itself is
    noisy, catching star-pip glyphs alongside the level number, but
    presence/absence of "/" is all that's needed here).

Scrolling beyond one viewport is NOT implemented - this account's roster
(17 champions, 4 rows) fit entirely within the confirmed grid_rows. A
larger roster would need the same pixel-content-diff scroll measurement
attribute_details.py uses (never trust the requested drag distance), driven
row-by-row rather than stitched into one composite, since cards need to be
clicked, not just read as text. Left as a documented gap rather than
untested code, consistent with CLAUDE.md's evidence-first approach.
"""
import logging
import time

from capture import screenshot_region
from input_control import click
from nav import back
from ocr import preprocess, pytesseract
from profiles.champion_layout import ChampionLayout, get_champion_layout, require_field

log = logging.getLogger(__name__)


def goto_champion_grid(hwnd) -> None:
    layout = get_champion_layout(hwnd)
    click(hwnd, *layout.champion_grid_icon)
    time.sleep(0.8)


def _card_state(hwnd, layout: ChampionLayout, col: int, row: int) -> str:
    """Returns "unlocked", "locked", or "empty" - the last one covers both
    a genuinely blank grid cell and a card OCR couldn't read any digits
    from at all (e.g. a teaser/locked slot with no visible "N/NN" progress
    text, confirmed live on one card - a muted, ion-icon portrait with no
    status text anywhere in its body). Both get treated as "not a real
    champion to open" - a false negative here just skips one card, which is
    far cheaper than mis-clicking a non-champion slot.

    OCR on this small mixed digits+star-pips region was confirmed flaky at
    a fixed upscale - a crop showing plainly readable "110" text came back
    completely empty at upscale 3 despite the box itself being correctly
    positioned (confirmed by saving and inspecting the crop directly, not
    guessed). Retrying at a couple of different upscale factors recovers
    real content without needing a single "right" preprocessing setting."""
    cx, cy = layout.grid_columns[col], layout.grid_rows[row]
    l, t, r, b = require_field(layout.card_status_offset, "card_status_offset")
    box = (cx + l, cy + t, cx + r, cy + b)
    img = screenshot_region(hwnd, box)
    for upscale in (3, 6, 8):
        text = pytesseract.image_to_string(
            preprocess(img, upscale=upscale), config="--psm 7 -c tessedit_char_whitelist=0123456789/"
        ).strip()
        if text:
            return "locked" if "/" in text else "unlocked"
    return "empty"


def enumerate_grid(hwnd, layout: ChampionLayout) -> list[tuple[int, int]]:
    """Returns (col, row) positions of unlocked champions in the current
    viewport, in reading order, without scrolling (see module docstring)."""
    positions = []
    for row in range(len(layout.grid_rows)):
        for col in range(len(layout.grid_columns)):
            state = _card_state(hwnd, layout, col, row)
            log.debug("Grid (%d,%d): %s", col, row, state)
            if state == "unlocked":
                positions.append((col, row))
    return positions


def open_card(hwnd, layout: ChampionLayout, col: int, row: int) -> None:
    click(hwnd, layout.grid_columns[col], layout.grid_rows[row])
    time.sleep(0.9)


def close_card(hwnd) -> None:
    """Returns from a champion's detail view to the grid."""
    back(hwnd)
    time.sleep(0.5)
