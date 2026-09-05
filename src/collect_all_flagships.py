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
import re
import time
from pathlib import Path

from capture import find_window, screenshot_region
from fingerprints import current_screen
from input_control import click
from nav import goto, back
from ocr import preprocess, pytesseract
from attribute_details import read_attribute_details, validate_sections
from component_details import OVERVIEW_TAB, read_all_components
from promotion_details import read_promotion
from flagships import FIRST_CARD_CLICK, RIGHT_ARROW, NAME_BOX, MAX_SHIPS
import ocr_easy

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "attributes"
ATTRIBUTE_CLOSE_BUTTON = (1275, 230)  # X button on the Attribute Details modal
# The "Level NN" badge under the ship model on its Overview tab. Same visual
# metaphor used throughout this game's UI: a locked/not-yet-unlocked item is
# still viewable, just rendered without the labels an unlocked one gets -
# confirmed by the user directly, with this badge specifically named as the
# reliable "is this ship real" signal for the flagship section.
LEVEL_BADGE_BOX = (1230, 1055, 1360, 1180)


def _read_ship_name(hwnd) -> str:
    img = screenshot_region(hwnd, NAME_BOX)
    return ocr_easy.read_text(img)


def _is_ship_unlocked(hwnd) -> bool:
    """Cheap check done *before* the expensive attribute scroll-read: an
    unlocked ship's Overview tab shows a "Level NN" badge; a locked slot's
    preview doesn't. psm 11 (sparse text) is what actually reads the digits
    here - psm 6 (the usual multi-line default) came back empty on this
    badge in testing despite the crop being visibly correct, for reasons
    not fully understood; 11 is confirmed to work. Only the digits matter -
    the word "Level" itself doesn't reliably come through even on a real
    ship, so this checks for any digit rather than requiring the word."""
    img = screenshot_region(hwnd, LEVEL_BADGE_BOX)
    text = pytesseract.image_to_string(preprocess(img, upscale=2), config="--psm 11").strip()
    return bool(re.search(r"\d", text))


def collect_all_flagships(hwnd) -> dict[str, dict]:
    # Reset to *a* main view - either base view is a fine starting point for
    # opening the fleet list, so this no longer forces system_map specifically
    # (both are now fingerprinted in fingerprints.py; city_view wasn't when
    # this was first written, which caused its own bug - see below).
    #
    # Still needs a back()-loop rather than a single check: current_screen()
    # only recognizes screens with a catalogued fingerprint - a ship detail
    # view, or an Attribute Details overlay left open from a previous run,
    # reads back as None, not as "some overlay to close". A few blind back()
    # calls, verifying after each, are harmless no-ops once already on a base
    # view but reliably escape however many unrecognized overlays are
    # stacked up.
    #
    # The 0.6s pause after each back() also covers the base views' own
    # render delay: their fingerprint pixels (menu icons, top-left) take a
    # moment to paint in on a fresh transition, so checking immediately after
    # arriving can read a false "not there yet" - confirmed directly. This
    # loop already re-checks on each iteration rather than failing fast, so
    # that delay gets absorbed rather than causing a wrong result.
    for _ in range(5):
        if current_screen(hwnd) in ("system_map", "city_view"):
            break
        back(hwnd)
        time.sleep(0.6)

    goto(hwnd, "fleet_list")
    click(hwnd, *FIRST_CARD_CLICK)
    time.sleep(0.6)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict] = {}

    for _ in range(MAX_SHIPS):
        name = _read_ship_name(hwnd)
        if not name:
            # The detail view's entrance animation may not have finished
            # rendering the name yet - confirmed on a live run where a real
            # ship's name came back empty right after arriving. One retry
            # after a bit more time is enough.
            time.sleep(0.5)
            name = _read_ship_name(hwnd)

        if not name or name in results:
            break  # wrapped back around to a ship we've already seen

        # Paging to a ship with the side arrows leaves whichever tab
        # (Overview/Component/Promote) was active for the *previous* ship
        # still active - it doesn't reset to Overview on its own. Confirmed
        # live. So every iteration explicitly selects Overview before
        # reading attributes, rather than assuming we're already there (true
        # for ship 1, via FIRST_CARD_CLICK, but not for ship 2+).
        click(hwnd, *OVERVIEW_TAB)
        time.sleep(0.6)

        if not _is_ship_unlocked(hwnd):
            # No "Level NN" badge - a locked, not-yet-unlocked ship
            # placeholder, not a real ship (confirmed directly: an
            # unrevealed slot can still show a name preview, garbled or
            # not, alongside the rest of its Overview tab). Only the first
            # ship slot (Gram) is guaranteed active on any account - every
            # slot after that may or may not be unlocked. Check this before
            # the expensive attribute scroll-read, not after, so a locked
            # slot costs one cheap OCR call instead of a full failed scan.
            break

        data = read_attribute_details(hwnd)
        validation = validate_sections(data)
        results[name] = data

        click(hwnd, *ATTRIBUTE_CLOSE_BUTTON)  # close the attribute overlay
        time.sleep(0.6)

        components = read_all_components(hwnd)  # leaves the last component's detail view open

        # One back() from a component's detail view returns to the Component
        # tab's own grid-of-5-icons view (not Overview, not the fleet list) -
        # confirmed live. read_promotion() then switches to the Promote tab
        # directly (a top-level tab switch, not a nested sub-view, so no
        # back() is needed first) to read the level badge.
        back(hwnd)
        time.sleep(0.6)
        promotion = read_promotion(hwnd)

        out_path = DATA_DIR / f"{name}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "ship": name, "attributes": data, "validation": validation,
                    "components": components, "promotion": promotion,
                },
                f, indent=2,
            )

        click(hwnd, *RIGHT_ARROW)  # page to the next ship, still on the Promote tab
        time.sleep(0.6)

    # Loop exits with the view on the wrapped-around ship's Promote tab (see
    # the note above) - one back() from there reaches the fleet list.
    back(hwnd)
    return results


if __name__ == "__main__":
    hwnd = find_window("Foundation Galactic Frontier")
    collected = collect_all_flagships(hwnd)
    print(f"Collected {len(collected)} ship(s): {list(collected)}")
