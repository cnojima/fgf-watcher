"""Read the ship's element-type badge from its Overview tab (top-left icon,
directly under the ship name) - a pictographic icon with no text in it at
all, so OCR can't read it (a different failure mode than ocr_easy.py's
stylized-font case - there's no font to fall back to reading here). Matched
by pixel comparison against a small reference library instead - see
icon_match.py.
"""
import logging

from capture import screenshot_region
from icon_match import match_icon
from profiles.ui_layout import require_field

log = logging.getLogger(__name__)


def read_ship_element(hwnd, layout) -> str | None:
    """Assumes the ship detail view's Overview tab is currently showing.
    Returns None if the badge doesn't confidently match any known element
    (see icon_match.match_icon) rather than guessing."""
    box = require_field(layout.element_icon_box, "element_icon_box")
    element = match_icon(screenshot_region(hwnd, box), "elements")
    log.info("Ship element: %s", element)
    return element
