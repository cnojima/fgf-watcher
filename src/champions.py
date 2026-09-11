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

Scrolling beyond one viewport was originally not implemented at all (this
account's roster used to fit entirely within one screen) - confirmed live to
matter once the roster grew past that: the grid's last row can render its
card fully but with its status-text bar below the visible window's own
bottom edge, entirely unreadable by _card_state - not a "locked/no status"
card (that misclassification was tried and rejected - see git history), a
genuinely real champion just clipped by the viewport.

check_last_row_after_scroll handles exactly that one case. Confirmed live
via two saved before/after screenshots that dragging the grid does NOT
uniformly translate all content by a fixed pixel amount: a general
content-diff measurement (content_offset) over the whole grid measured a
consistent 102px shift, but the last row's actual status-bar position after
scrolling landed nowhere near "unscrolled position minus 102" (reading
garbage) - it only read correctly at a position 58px up from its unscrolled
spot, found by direct search. This looks like the grid "snapping" the last
row to a fixed, fully-revealed resting position once you scroll into it,
rather than a plain proportional scroll - so ChampionLayout.grid_scrolled_last_row_y
is calibrated as that confirmed absolute resting position directly, not
derived from any measured scroll offset. _scroll_grid_down's own
content-diff measurement is only used to confirm scrolling actually moved
something (vs. already being at the bottom), not to compute a position.

NOT yet generalized to a roster needing more than one extra row beyond what
fits in one viewport - that would need a second, similarly-confirmed resting
position, not assumed to be a simple multiple of this one. Left as a
documented gap rather than untested code, consistent with CLAUDE.md's
evidence-first approach.
"""
import logging
import time

import paddle_ocr
from capture import screenshot_region
from input_control import click, drag
from nav import back
from profiles.champion_layout import ChampionLayout, get_champion_layout, require_field
from scroll_stitch import content_offset

log = logging.getLogger(__name__)


def goto_champion_grid(hwnd) -> None:
    layout = get_champion_layout(hwnd)
    click(hwnd, *layout.champion_grid_icon)
    time.sleep(0.8)


def on_grid(hwnd, layout: ChampionLayout) -> bool:
    # ChampionLayout.grid_title_box: the grid screen's fixed "CHAMPION"
    # title - used as a sync-check after closing a card, so a failure to
    # fully close (confirmed possible live - see
    # champion_weapon.close_weapon_page's docstring for how one such
    # failure cascaded into misreading unrelated screens for several
    # subsequent champions in a batch run before this check existed) is
    # caught and recovered from immediately, rather than silently
    # corrupting every champion collected afterward.
    box = require_field(layout.grid_title_box, "grid_title_box")
    return "champion" in paddle_ocr.read_text(screenshot_region(hwnd, box)).lower()


def recover_to_grid(hwnd, layout: ChampionLayout) -> None:
    """Best-effort recovery when we're not where we expect to be - press
    back() a bounded number of times, then fall back to re-navigating from
    the grid icon directly (works regardless of how deep the stuck state
    is, since it doesn't depend on back() actually working from there)."""
    log.warning("Not on the grid screen where expected - attempting recovery")
    for _ in range(4):
        if on_grid(hwnd, layout):
            return
        back(hwnd)
        time.sleep(0.5)
    goto_champion_grid(hwnd)
    if not on_grid(hwnd, layout):
        raise RuntimeError("Could not recover to the champion grid after a navigation failure")


def classify_card_state(text: str) -> str:
    """Pure classification of a grid card's status-text OCR - see
    _card_state below for what each outcome means.

    Requires at least one digit to call a cell "locked"/"unlocked" at all -
    confirmed live this box isn't reliably blank for a non-champion cell:
    a locked/teaser slot with no status bar at all read as a stray "-", and
    a genuinely empty cell in a partially-filled last grid row overlapped
    the RECRUIT button below it, reading fragments like "-DECRI"/"T"/"F"
    (from "RECRUIT" itself). None of that is a real level/progress readout
    (always digits, e.g. "165" or "0/40"), but the previous check - "empty"
    only for a literal empty string, "unlocked" for anything else without a
    "/" - treated all of that garbage as a real champion, causing capture
    to open several nonexistent cards after the true end of the roster."""
    if not any(char.isdigit() for char in text):
        return "empty"
    return "locked" if "/" in text else "unlocked"


def _card_state(hwnd, layout: ChampionLayout, col: int, row: int, cy_override: int | None = None) -> str:
    """Returns "unlocked", "locked", or "empty" - the last one covers both
    a genuinely blank grid cell and a card OCR couldn't read any digits
    from at all (e.g. a teaser/locked slot with no visible "N/NN" progress
    text, confirmed live on one card - a muted, ion-icon portrait with no
    status text anywhere in its body). Both get treated as "not a real
    champion to open" - a false negative here just skips one card, which is
    far cheaper than mis-clicking a non-champion slot.

    OCR on this small mixed digits+star-pips region was confirmed flaky
    under Tesseract at a fixed upscale - a crop showing plainly readable
    "110" text came back completely empty at upscale 3 despite the box
    itself being correctly positioned (confirmed by saving and inspecting
    the crop directly, not guessed) - retrying at a couple of different
    upscale factors recovered real content. Migrated to paddle_ocr (see the
    OCR-consolidation plan): confirmed live against real card crops (three
    unlocked cards, "121"/"120"/"120" mixed with star-pip and quality-badge
    icons) reading cleanly on the first call, so the multi-upscale retry
    loop is no longer needed.

    cy_override: replaces the row's calibrated y-position entirely (not a
    relative adjustment to it) - see check_last_row_after_scroll, which
    passes grid_scrolled_last_row_y's confirmed absolute position here."""
    cx = layout.grid_columns[col]
    cy = layout.grid_rows[row] if cy_override is None else cy_override
    l, t, r, b = require_field(layout.card_status_offset, "card_status_offset")
    box = (cx + l, cy + t, cx + r, cy + b)
    img = screenshot_region(hwnd, box)
    return classify_card_state(paddle_ocr.read_text(img))


def enumerate_grid(hwnd, layout: ChampionLayout) -> list[tuple[int, int]]:
    """Returns (col, row) positions of unlocked champions in the current
    (unscrolled) viewport, in reading order. See check_last_row_after_scroll
    for the one additional case this doesn't cover: a real champion in the
    last row whose status text renders below the visible window."""
    positions = []
    for row in range(len(layout.grid_rows)):
        for col in range(len(layout.grid_columns)):
            state = _card_state(hwnd, layout, col, row)
            log.debug("Grid (%d,%d): %s", col, row, state)
            if state == "unlocked":
                positions.append((col, row))
    return positions


def _scroll_grid_down(hwnd, layout: ChampionLayout) -> bool:
    """Drags the grid down by one gesture, measuring actual pixel movement
    (never trusting the requested drag distance - same content_offset
    technique scroll_stitch.py uses elsewhere) purely to confirm scrolling
    had *some* effect. Returns False if nothing moved (already at the
    bottom) - the measured amount itself isn't used for anything further;
    see module docstring for why (it doesn't predict where the last row's
    content actually ends up)."""
    box = require_field(layout.grid_scroll_measure_box, "grid_scroll_measure_box")
    drag_from = require_field(layout.grid_scroll_drag_from, "grid_scroll_drag_from")
    drag_to = require_field(layout.grid_scroll_drag_to, "grid_scroll_drag_to")
    before = screenshot_region(hwnd, box)
    drag(hwnd, *drag_from, *drag_to)
    time.sleep(0.7)
    after = screenshot_region(hwnd, box)
    offset = content_offset(before, after, static_header_height=0, expected=layout.grid_scroll_expected_offset)
    log.debug("Grid scroll: measured offset=%dpx", offset)
    return offset > 5


def check_last_row_after_scroll(hwnd, layout: ChampionLayout, already_found_cols: set[int]) -> list[int]:
    """Scrolls the grid down once and re-checks the last row's columns not
    already in already_found_cols, at grid_scrolled_last_row_y's confirmed
    resting position, to catch a real champion there whose status text was
    hidden below the visible window (see module docstring - confirmed live,
    not a locked/empty slot). Returns the newly-confirmed unlocked columns -
    the caller must open/read them via open_card/_card_state's cy_override
    set to grid_scrolled_last_row_y, not the row's normal position.

    Only performs one scroll step - confirmed sufficient for one clipped
    extra row, not yet validated for a roster needing more (see module
    docstring)."""
    if not _scroll_grid_down(hwnd, layout):
        return []
    last_row = len(layout.grid_rows) - 1
    cy = require_field(layout.grid_scrolled_last_row_y, "grid_scrolled_last_row_y")
    found = []
    for col in range(len(layout.grid_columns)):
        if col in already_found_cols:
            continue
        state = _card_state(hwnd, layout, col, last_row, cy_override=cy)
        log.debug("Grid (%d,%d) after scroll: %s", col, last_row, state)
        if state == "unlocked":
            found.append(col)
    return found


def open_card(hwnd, layout: ChampionLayout, col: int, row: int, cy_override: int | None = None) -> None:
    cy = layout.grid_rows[row] if cy_override is None else cy_override
    click(hwnd, layout.grid_columns[col], cy)
    time.sleep(0.9)


def close_card(hwnd) -> None:
    """Returns from a champion's detail view to the grid."""
    back(hwnd)
    time.sleep(0.5)
