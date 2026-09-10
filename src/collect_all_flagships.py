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
import logging
import re
import time
from pathlib import Path

from capture import find_window, screenshot_region
from profiles.fingerprints import current_screen
from input_control import click, focus_window, press_key
from logging_setup import configure_logging
from nav import goto, back
from ocr import preprocess, pytesseract
from attribute_details import read_attribute_details, validate_sections
from component_details import read_all_components
from empowerment_details import read_empowerment
from overview_details import read_ship_element
from promotion_details import read_promotion
from flagships import MAX_SHIPS
from profiles.ui_layout import get_layout
import ocr_easy

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "attributes"
log = logging.getLogger(__name__)


def _read_ship_name(hwnd, layout) -> str:
    img = screenshot_region(hwnd, layout.name_box)
    return ocr_easy.read_text(img)


def _is_ship_unlocked(hwnd, layout) -> bool:
    """Cheap check done *before* the expensive attribute scroll-read: an
    unlocked ship's Overview tab shows a "Level NN" badge; a locked slot's
    preview doesn't. psm 11 (sparse text) is what actually reads the digits
    here - psm 6 (the usual multi-line default) came back empty on this
    badge in testing despite the crop being visibly correct, for reasons
    not fully understood; 11 is confirmed to work. Only the digits matter -
    the word "Level" itself doesn't reliably come through even on a real
    ship, so this checks for any digit rather than requiring the word."""
    img = screenshot_region(hwnd, layout.level_badge_box)
    text = pytesseract.image_to_string(preprocess(img, upscale=2), config="--psm 11").strip()
    unlocked = bool(re.search(r"\d", text))
    log.debug("Level badge OCR: %r -> unlocked=%s", text, unlocked)
    return unlocked


def collect_all_flagships(hwnd) -> dict[str, dict]:
    log.info("Starting flagship collection")
    layout = get_layout(hwnd)

    # screenshot_window() (used by current_screen() below, and transitively by
    # goto()) refuses to capture unless hwnd is already the foreground window -
    # click()/press_key() focus it themselves before acting, but the very
    # first thing this function does is a current_screen() check with no
    # click/press before it, so focus explicitly here first.
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
        time.sleep(0.6)

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
            time.sleep(0.3)
            name = _read_ship_name(hwnd, layout)

        if not name or name in results:
            log.debug("Ship name %r empty or already seen - wrapped around fleet list", name)
            break  # wrapped back around to a ship we've already seen

        log.info("%s: starting collection", name)

        # Paging to a ship with the side arrows leaves whichever tab
        # (Overview/Component/Promote) was active for the *previous* ship
        # still active - it doesn't reset to Overview on its own. Confirmed
        # live. So every iteration explicitly selects Overview before
        # reading attributes, rather than assuming we're already there (true
        # for ship 1, via FIRST_CARD_CLICK, but not for ship 2+).
        click(hwnd, *layout.overview_tab)
        time.sleep(0.6)

        if not _is_ship_unlocked(hwnd, layout):
            # No "Level NN" badge - a locked, not-yet-unlocked ship
            # placeholder, not a real ship (confirmed directly: an
            # unrevealed slot can still show a name preview, garbled or
            # not, alongside the rest of its Overview tab). Only the first
            # ship slot (Gram) is guaranteed active on any account - every
            # slot after that may or may not be unlocked. Check this before
            # the expensive attribute scroll-read, not after, so a locked
            # slot costs one cheap OCR call instead of a full failed scan.
            log.info("%s: no Level badge found - locked slot, stopping", name)
            break

        element = read_ship_element(hwnd, layout)
        empowerment = read_empowerment(hwnd, layout)
        data = read_attribute_details(hwnd, name)
        validation = validate_sections(data)
        invalid = [s for s, r in validation.items() if not r["valid"]]
        if invalid:
            log.warning("%s: %d section(s) failed validation: %s", name, len(invalid), invalid)
        results[name] = data

        # Deliberately overrides nav.py's "never use ESC" rule (it's normally
        # "Quit game" from a base view and, per a known game bug, can even
        # trigger a full quit from certain overlays instead of closing just
        # that overlay) - confirmed by the user this overlay specifically
        # closes safely with it. layout.attribute_close_button is kept
        # unused as a rollback if that turns out to be wrong on a wider test.
        press_key(hwnd, "esc")  # close the attribute overlay
        time.sleep(0.2)

        components = read_all_components(hwnd, name)  # leaves the last component's detail view open

        # One back() from a component's detail view returns to the Component
        # tab's own grid-of-5-icons view (not Overview, not the fleet list) -
        # confirmed live. read_promotion() then switches to the Promote tab
        # directly (a top-level tab switch, not a nested sub-view, so no
        # back() is needed first) to read the level badge.
        back(hwnd)
        time.sleep(0.2)
        promotion = read_promotion(hwnd)
        log.info("%s: promotion level %s, %d component(s) read", name, promotion["level"], len(components))

        out_path = DATA_DIR / f"{name}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "ship": name, "element": element, "empowerment": empowerment,
                    "attributes": data, "validation": validation,
                    "components": components, "promotion": promotion,
                },
                f, indent=2,
            )
        log.info("%s: saved to %s", name, out_path)

        click(hwnd, *layout.right_arrow)  # page to the next ship, still on the Promote tab
        time.sleep(0.2)

    # Loop exits with the view on the wrapped-around ship's Promote tab (see
    # the note above) - one back() from there reaches the fleet list.
    back(hwnd)
    log.info("Finished flagship collection: %d ship(s)", len(results))
    return results


if __name__ == "__main__":
    configure_logging()
    # "Foundation Galactic Frontier" (no colon) doesn't substring-match the
    # game's real window title "Foundation: Galactic Frontier" - confirmed
    # live via capture.list_windows(), not a guess.
    hwnd = find_window("Galactic Frontier")
    collected = collect_all_flagships(hwnd)
    log.info("Collected %d ship(s): %s", len(collected), list(collected))
