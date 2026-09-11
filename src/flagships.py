"""Read the names of all flagships (1-4) the player currently owns, by
opening the fleet list and paging through the ship detail view with the
</>  arrows. Uses paddle_ocr (not ocr.py's Tesseract) for the name text -
this stylized font is the same one champion_info.py's name/title fields
needed PaddleOCR for (see the OCR-consolidation plan).
"""
import logging
import time

import paddle_ocr
from capture import screenshot_region
from input_control import click
from nav import back, goto
from profiles.ui_layout import get_layout

log = logging.getLogger(__name__)

MAX_SHIPS = 4


def read_owned_flagships(hwnd) -> list[str]:
    layout = get_layout(hwnd)
    goto(hwnd, "fleet_list")
    click(hwnd, *layout.first_card_click)
    time.sleep(0.6)

    names: list[str] = []
    for _ in range(MAX_SHIPS):
        name_img = screenshot_region(hwnd, layout.name_box)
        name = paddle_ocr.read_text(name_img)
        if not name or name in names:
            break  # wrapped back around to a ship we've already seen
        names.append(name)
        click(hwnd, *layout.right_arrow)
        time.sleep(0.6)

    back(hwnd)  # close detail view, back to fleet_list
    log.info("Read %d owned flagship(s): %s", len(names), names)
    return names
