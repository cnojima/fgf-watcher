"""Collect Info/Attributes/Weapon/Ability/Star Level for every unlocked
champion in the collection grid, saving each as its own JSON file.

Mirrors collect_all_flagships.py's structure: navigate to the grid, get the
list of unlocked (col, row) positions, open each in turn, read every tab,
close back to the grid, move to the next.
"""
import json
import logging
import time
from pathlib import Path

import paddle_ocr
from capture import find_window, screenshot_region
from champion_ability import read_abilities
from champion_attributes import read_attributes
from champion_info import read_info
from champion_star_level import read_star_level
from champion_weapon import close_weapon_page, has_weapon_equipped, read_weapon
from champions import check_last_row_after_scroll, close_card, enumerate_grid, goto_champion_grid, on_grid, open_card, recover_to_grid
from input_control import click, focus_window
from logging_setup import configure_logging
from nav import back
from profiles.champion_layout import get_champion_layout
from profiles.fingerprints import current_screen

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "champions"


def collect_champion(hwnd, layout) -> dict:
    """Assumes the champion's detail view just opened, on the Info tab."""
    info = read_info(hwnd, layout)
    star_level = read_star_level(hwnd, layout)  # header pip strip - visible on Info tab already
    attributes = read_attributes(hwnd, layout)  # opens/closes the hamburger modal itself

    weapon = None
    if info["name"] and has_weapon_equipped(hwnd, layout):
        click(hwnd, *layout.weapon_badge_click)
        time.sleep(0.8)
        weapon = read_weapon(hwnd, layout)
        close_weapon_page(hwnd, layout)

        # Confirmed live: close_weapon_page's variant detection can still
        # get it wrong on a layout not seen yet - verify we're actually
        # back on this champion's own Info tab (not stuck on the weapon
        # page or dumped somewhere else entirely) before touching the
        # Ability tab, rather than assuming the close worked.
        back_name = paddle_ocr.read_text(screenshot_region(hwnd, layout.name_box))
        if back_name != info["name"]:
            log.error(
                "%s: expected to be back on Info tab after reading weapon, but name_box "
                "reads %r - aborting this champion's remaining fields", info["name"], back_name,
            )
            return {
                "info": info, "star_level": star_level, "attributes": attributes,
                "weapon": weapon, "abilities": None, "error": "lost navigation state after weapon read",
            }

    click(hwnd, *layout.ability_tab)
    time.sleep(0.7)
    abilities = read_abilities(hwnd, layout)

    return {
        "info": info,
        "star_level": star_level,
        "attributes": attributes,
        "weapon": weapon,
        "abilities": abilities,
    }


def collect_all_champions(hwnd) -> dict[str, dict]:
    log.info("Starting champion collection")
    focus_window(hwnd)

    # goto() for a base view refuses if an overlay is currently open (it only
    # knows how to toggle system_map/city_view, not close an arbitrary
    # overlay on top of one) - close whatever might already be open first so
    # this works regardless of where the game happened to be when called.
    # current_screen() only recognizes screens with a catalogued fingerprint
    # (currently just system_map/fleet_list) - a ship detail view, or an
    # Attribute Details overlay left open from a previous run, reads back as
    # None, not as "some overlay to close". A single back() call then gets
    # skipped entirely and goto() fails outright (confirmed on a live run:
    # starting from a ship detail view, goto("system_map") pressed SPACE from
    # the wrong screen and never landed on system_map). Press back() blindly
    # a few times instead, verifying after each - harmless no-ops once
    # already on a base view, but reliably escapes however many unrecognized
    # overlays are stacked up, not just the ones we happen to have a
    # fingerprint for.
    for _ in range(3):
        if current_screen(hwnd) in ("system_map", "city_view"):
            break
        back(hwnd)
        time.sleep(0.2)

    layout = get_champion_layout(hwnd)

    goto_champion_grid(hwnd)
    positions = enumerate_grid(hwnd, layout)
    log.info("Found %d unlocked champion(s) in the visible grid", len(positions))

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict] = {}

    def _process(col: int, row: int, cy_override: int | None = None) -> None:
        open_card(hwnd, layout, col, row, cy_override=cy_override)
        data = collect_champion(hwnd, layout)
        name = data["info"]["name"] or f"unknown_{col}_{row}"

        out_path = DATA_DIR / f"{name}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        log.info("%s: saved to %s", name, out_path)
        results[name] = data

        close_card(hwnd)
        if not on_grid(hwnd, layout):
            recover_to_grid(hwnd, layout)

    for col, row in positions:
        _process(col, row)

    # A real champion in the grid's last row can have its status text
    # render below the visible window even though the card itself is fully
    # visible (confirmed live - see champions.py's module docstring), which
    # enumerate_grid's unscrolled check can't see. Scroll down once and
    # check that row's remaining columns at their confirmed post-scroll
    # position.
    last_row = len(layout.grid_rows) - 1
    already = {col for col, row in positions if row == last_row}
    for col in check_last_row_after_scroll(hwnd, layout, already):
        _process(col, last_row, cy_override=layout.grid_scrolled_last_row_y)

    log.info("Finished champion collection: %d champion(s)", len(results))
    return results


if __name__ == "__main__":
    configure_logging()
    hwnd = find_window("Galactic Frontier")
    collected = collect_all_champions(hwnd)
    log.info("Collected %d champion(s): %s", len(collected), list(collected))
