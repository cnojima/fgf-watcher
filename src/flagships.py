"""Read the names of all flagships (1-4) the player currently owns, by
opening the fleet list and paging through the ship detail view with the
</>  arrows. Uses ocr_easy (not ocr.py's Tesseract) for the name text - see
ocr_easy.py docstring for why.
"""
import time

from capture import screenshot_region
from input_control import click
from nav import back, goto
import ocr_easy

FIRST_CARD_CLICK = (1000, 210)
# Bottom was originally 65, which clipped descenders (p/y/g) and was the
# actual cause of several OCR misreads (e.g. "Opportunity" -> "Opportunitv"),
# not an OCR engine limitation - confirmed by inspecting the crop directly.
NAME_BOX = (845, 5, 1090, 80)
RIGHT_ARROW = (1825, 1010)
MAX_SHIPS = 4


def read_owned_flagships(hwnd) -> list[str]:
    goto(hwnd, "fleet_list")
    click(hwnd, *FIRST_CARD_CLICK)
    time.sleep(0.6)

    names: list[str] = []
    for _ in range(MAX_SHIPS):
        name_img = screenshot_region(hwnd, NAME_BOX)
        name = ocr_easy.read_text(name_img)
        if not name or name in names:
            break  # wrapped back around to a ship we've already seen
        names.append(name)
        click(hwnd, *RIGHT_ARROW)
        time.sleep(0.6)

    back(hwnd)  # close detail view, back to fleet_list
    return names
