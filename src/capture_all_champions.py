"""Capture champion screens for later, offline OCR replay.

This phase performs navigation and input only. The saved full-window frames
are the source of truth for OCR tuning; replay code can recrop them
repeatedly. Mirrors capture_all_flagships.py's structure and frame/manifest
conventions - see replay_all_champions.py for the offline half.
"""
import argparse
import logging
import sys
import time
from pathlib import Path

import paddle_ocr
from capture import find_window, screenshot_region, screenshot_window
from capture_run import CaptureRun
from champion_ability import ABILITY_SLOTS
from champion_weapon import BONUS_SLOTS, close_weapon_page, has_weapon_equipped
from champions import check_last_row_after_scroll, close_card, enumerate_grid, goto_champion_grid, on_grid, open_card, recover_to_grid
from input_control import click, focus_window
from logging_setup import configure_logging
from nav import back
from profiles.champion_layout import get_champion_layout, require_field
from profiles.fingerprints import current_screen
from profiles.notifications import dismiss_if_present
from scroll_stitch import capture_scroll_sequence

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "champion_captures"


def _save(run, hwnd, name, kind, champion_index, sequence=0):
    relative = f"champion-{champion_index:03d}/{name}-{sequence:03d}.png"
    return run.save_image(
        screenshot_window(hwnd), relative, kind=kind,
        ship_index=champion_index, sequence=sequence,
    )


def _capture_weapon(run, hwnd, layout, champion_index):
    """Assumes the champion's Info tab is showing and has_weapon_equipped()
    already confirmed a weapon is equipped (the "+" no-weapon placeholder
    must never be clicked into - see champion_weapon.has_weapon_equipped).
    Opens the weapon page, saves its frame plus the scroll-stitched stats
    frames and (if calibrated) each bonus-badge toggle, then closes back
    to Info.

    Known gap vs. the live champion_weapon.read_weapon(): that function
    retries its name/badge OCR once if the text looks like a banner slid
    across the box mid-capture (see its docstring - confirmed live, not
    hypothetical). Retrying here would mean deciding from the OCR'd value
    itself, which is exactly the data-OCR-during-capture this phase split
    is meant to avoid - dismiss_if_present(hwnd) below is the same primary
    defense the live path has, just without that belt-and-suspenders
    retry. A "weapon" frame that came out corrupted this way is still
    visible directly in the saved PNG, unlike a live run where it silently
    became part of the JSON output."""
    click(hwnd, *layout.weapon_badge_click)
    time.sleep(0.8)
    dismiss_if_present(hwnd)
    _save(run, hwnd, "weapon", "weapon", champion_index)

    capture_scroll_sequence(
        lambda sequence: _save(run, hwnd, "weapon-stats", "weapon-stats", champion_index, sequence),
        hwnd, require_field(layout.weapon_stats_box, "weapon_stats_box"),
        require_field(layout.weapon_stats_drag_from, "weapon_stats_drag_from"),
        require_field(layout.weapon_stats_drag_to, "weapon_stats_drag_to"),
        layout.weapon_stats_expected_scroll_offset, max_scrolls=10,
    )

    if layout.weapon_bonus_info_box is not None:
        icons = require_field(layout.weapon_bonus_icons, "weapon_bonus_icons")
        for slot, (x, y) in zip(BONUS_SLOTS, icons):
            click(hwnd, x, y)
            time.sleep(0.4)
            _save(run, hwnd, f"weapon-bonus-{slot}", f"weapon-bonus-{slot}", champion_index)
            click(hwnd, x, y)  # close it again before the next one
            time.sleep(0.3)

    # close_weapon_page's variant detection (plain back-arrow vs. "Select
    # Weapon" browse's X button) is a live-only navigation decision with no
    # data replay needs - reuse it directly rather than duplicating it here.
    close_weapon_page(hwnd, layout)


def _capture_ability_frames(run, hwnd, layout, champion_index):
    for slot, (x, y) in zip(ABILITY_SLOTS, layout.ability_icons):
        click(hwnd, x, y)
        time.sleep(0.4)
        kind = f"ability-{slot}"
        capture_scroll_sequence(
            lambda sequence: _save(run, hwnd, kind, kind, champion_index, sequence),
            hwnd, layout.ability_scroll_box, layout.ability_scroll_drag_from, layout.ability_scroll_drag_to,
            layout.ability_expected_scroll_offset, max_scrolls=8,
        )


def _capture_champion(run, hwnd, layout, champion_index):
    """Assumes the champion's detail view just opened, on the Info tab.
    Mirrors collect_all_champions.collect_champion's navigation choreography
    (including its guardrails against known live failure modes - e.g.
    close_weapon_page's browse-variant close silently failing, see its
    docstring) so capture and the live collector behave identically; the
    only OCR here is the transient name_box read used as a liveness check
    (never persisted - replay re-derives the real name from the saved
    "info" frame)."""
    dismiss_if_present(hwnd)
    _save(run, hwnd, "info", "info", champion_index)
    name = paddle_ocr.read_text(screenshot_region(hwnd, layout.name_box))

    click(hwnd, *layout.hamburger_icon)
    time.sleep(0.6)
    _save(run, hwnd, "attribute-space", "attribute-space", champion_index)
    click(hwnd, *layout.ground_combat_tab)
    time.sleep(0.4)
    _save(run, hwnd, "attribute-ground", "attribute-ground", champion_index)
    click(hwnd, *layout.attribute_modal_close)
    time.sleep(0.4)

    if name and has_weapon_equipped(hwnd, layout):
        _capture_weapon(run, hwnd, layout, champion_index)
        back_name = paddle_ocr.read_text(screenshot_region(hwnd, layout.name_box))
        if back_name != name:
            log.error(
                "Champion %d: expected to be back on Info tab after weapon capture, "
                "but name_box reads %r (was %r) - skipping ability capture for this champion",
                champion_index, back_name, name,
            )
            return

    click(hwnd, *layout.ability_tab)
    time.sleep(0.7)
    _capture_ability_frames(run, hwnd, layout, champion_index)


def capture_all_champions(hwnd, output: Path) -> Path:
    run = CaptureRun(output)
    layout = get_champion_layout(hwnd)
    focus_window(hwnd)

    for _ in range(3):
        if current_screen(hwnd) in ("system_map", "city_view"):
            break
        back(hwnd)
        time.sleep(0.2)

    goto_champion_grid(hwnd)
    positions = enumerate_grid(hwnd, layout)
    log.info("Found %d unlocked champion(s) in the visible grid", len(positions))

    champion_index = 0
    for col, row in positions:
        open_card(hwnd, layout, col, row)
        _capture_champion(run, hwnd, layout, champion_index)
        champion_index += 1
        close_card(hwnd)
        if not on_grid(hwnd, layout):
            recover_to_grid(hwnd, layout)

    # A real champion in the grid's last row can have its status text
    # render below the visible window even though the card itself is fully
    # visible (confirmed live - see champions.py's module docstring), which
    # enumerate_grid's unscrolled check can't see. Scroll down once and
    # check that row's remaining columns at their confirmed post-scroll
    # position.
    last_row = len(layout.grid_rows) - 1
    already = {col for col, row in positions if row == last_row}
    for col in check_last_row_after_scroll(hwnd, layout, already):
        open_card(hwnd, layout, col, last_row, cy_override=layout.grid_scrolled_last_row_y)
        _capture_champion(run, hwnd, layout, champion_index)
        champion_index += 1
        close_card(hwnd)
        if not on_grid(hwnd, layout):
            recover_to_grid(hwnd, layout)

    if not run.frames:
        raise RuntimeError("Capture produced no frames")
    run.write_manifest(
        platform=sys.platform,
        window_size=[run.frames[0]["width"], run.frames[0]["height"]],
    )
    return run.root / "manifest.json"


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Capture every unlocked champion's screens (info, attributes, weapon, "
            "abilities) as full-window PNG frames plus a manifest, for offline OCR "
            "replay via replay_all_champions.py. Navigation and input only - no "
            "data OCR happens during capture."
        ),
    )
    parser.add_argument(
        "output", type=Path, nargs="?", default=None,
        help=f"directory to write the capture run to (default: {DATA_DIR}/<timestamp>)",
    )
    args = parser.parse_args()
    output = args.output or DATA_DIR / time.strftime("%Y%m%d-%H%M%S")
    configure_logging()
    hwnd = find_window()
    start = time.monotonic()
    manifest = capture_all_champions(hwnd, output)
    log.info("Capture manifest: %s (%.1fs)", manifest, time.monotonic() - start)


if __name__ == "__main__":
    main()
