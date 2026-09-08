"""Read the names of all flagships (1-4) the player currently owns, by
opening the fleet list and paging through the ship detail view with the
</>  arrows. Uses ocr_easy (not ocr.py's Tesseract) for the name text - see
ocr_easy.py docstring for why.
"""
import time

from capture import screenshot_region
from input_control import click
from nav import back, goto
from profiles.ui_layout import get_layout
import ocr_easy

MAX_SHIPS = 4


def read_owned_flagships(hwnd) -> list[str]:
    layout = get_layout(hwnd)
    goto(hwnd, "fleet_list")
    click(hwnd, *layout.first_card_click)
    time.sleep(0.6)

    names: list[str] = []
    for _ in range(MAX_SHIPS):
        name_img = screenshot_region(hwnd, layout.name_box)
        name = ocr_easy.read_text(name_img)
        if not name or name in names:
            break  # wrapped back around to a ship we've already seen
        names.append(name)
        click(hwnd, *layout.right_arrow)
        time.sleep(0.6)

    back(hwnd)  # close detail view, back to fleet_list
    return names
