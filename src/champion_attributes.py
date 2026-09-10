"""Read a champion's Space Combat / Ground Combat attribute breakdown from
the "ATTRIBUTE DETAILS" modal (hamburger icon on the Info tab).

Unlike the ship version (attribute_details.py), both tabs here are short
flat lists (5-6 rows) with no nested sections and no scrolling - confirmed
live on Zora (6 Space Combat rows, 5 Ground Combat rows, both fitting
entirely within the modal with empty space left over). No stitch/scroll
logic is needed at all.
"""
import logging
import re
import time

from capture import screenshot_region
from input_control import click
from ocr import preprocess, pytesseract
from profiles.champion_layout import ChampionLayout

log = logging.getLogger(__name__)

_ROW_LINE = re.compile(r"^(.+?)\s+([+\-]?[\d][\d,\.]*%?)$")


def _read_flat_list(hwnd, layout: ChampionLayout) -> dict[str, str]:
    img = screenshot_region(hwnd, layout.attribute_modal_box)
    text = pytesseract.image_to_string(preprocess(img, upscale=2), config="--psm 6").strip()
    rows = {}
    for line in text.splitlines():
        m = _ROW_LINE.match(line.strip())
        if m:
            rows[m.group(1).strip()] = m.group(2)
    return rows


def read_attributes(hwnd, layout: ChampionLayout) -> dict[str, dict[str, str]]:
    """Assumes the champion's Info tab is currently showing. Opens the
    Attribute Details modal, reads both tabs, and closes it before
    returning."""
    click(hwnd, *layout.hamburger_icon)
    time.sleep(0.6)

    space_combat = _read_flat_list(hwnd, layout)

    click(hwnd, *layout.ground_combat_tab)
    time.sleep(0.4)
    ground_combat = _read_flat_list(hwnd, layout)

    click(hwnd, *layout.attribute_modal_close)
    time.sleep(0.4)

    log.info("Attributes: %d space combat, %d ground combat", len(space_combat), len(ground_combat))
    return {"space_combat": space_combat, "ground_combat": ground_combat}
