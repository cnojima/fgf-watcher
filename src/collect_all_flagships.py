"""Collect the full attribute-details stat breakdown for every owned
flagship, saving each ship's data as its own JSON file.

Originally specified as: select each ship from the fleet list, read it, close
back to the list, select the next card. Built that way first, but the fleet
list's card-click positions turned out to be unreliable on a live run - one
card needed a manual +10px correction, and re-entering the list and clicking
a different card's position twice both times reopened a ship already seen
instead of a new one (looked like some kind of sticky "last selected" state,
never fully root-caused). Switched to the paging mechanism flagships.py
already uses reliably instead: stay in the ship detail view the whole time
and move between ships with the left/right arrows, never re-entering the
list at all. Confirmed clean across repeated runs earlier this session.
"""
import json
import time
from pathlib import Path

from capture import find_window, screenshot_region
from fingerprints import current_screen
from input_control import click
from nav import goto, back
from attribute_details import read_attribute_details, validate_sections
from flagships import MAX_SHIPS
from ui_layout import get_layout
import ocr_easy

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "attributes"


def _read_ship_name(hwnd, layout) -> str:
    img = screenshot_region(hwnd, layout.name_box)
    return ocr_easy.read_text(img)


def collect_all_flagships(hwnd) -> dict[str, dict]:
    layout = get_layout(hwnd)

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
        time.sleep(0.6)

    goto(hwnd, "system_map")
    goto(hwnd, "fleet_list")
    click(hwnd, *layout.first_card_click)
    time.sleep(0.6)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict] = {}

    for _ in range(MAX_SHIPS):
        name = _read_ship_name(hwnd, layout)
        if not name:
            # The detail view's entrance animation may not have finished
            # rendering the name yet - confirmed on a live run where a real
            # ship's name came back empty right after arriving. One retry
            # after a bit more time is enough.
            time.sleep(0.5)
            name = _read_ship_name(hwnd, layout)

        if not name or name in results:
            break  # wrapped back around to a ship we've already seen

        data = read_attribute_details(hwnd)
        validation = validate_sections(data)
        results[name] = data

        out_path = DATA_DIR / f"{name}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"ship": name, "attributes": data, "validation": validation}, f, indent=2)

        click(hwnd, *layout.attribute_close_button)  # close the attribute overlay
        time.sleep(0.6)
        click(hwnd, *layout.right_arrow)  # page to the next ship, still in detail view
        time.sleep(0.6)

    back(hwnd)  # close the ship detail view, back to the fleet list
    return results


if __name__ == "__main__":
    # "Foundation Galactic Frontier" (no colon) doesn't substring-match the
    # game's real window title "Foundation: Galactic Frontier" - confirmed
    # live via capture.list_windows(), not a guess.
    hwnd = find_window("Galactic Frontier")
    collected = collect_all_flagships(hwnd)
    print(f"Collected {len(collected)} ship(s): {list(collected)}")
