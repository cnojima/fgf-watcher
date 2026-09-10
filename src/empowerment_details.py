"""Read a ship's Empowerment level (0-21) from its Overview tab - a small
diamond icon followed by "+N" text, directly below the element badge (see
overview_details.py).
"""
import logging
import re

import pytesseract

from capture import screenshot_region
from ocr import preprocess
from profiles.ui_layout import require_field

log = logging.getLogger(__name__)

_VALUE_RE = re.compile(r"\d{1,2}")


def read_empowerment(hwnd, layout) -> int | None:
    """Assumes the ship detail view's Overview tab is currently showing.
    Returns None if the crop didn't OCR to a recognizable number, rather
    than guessing."""
    box = require_field(layout.empowerment_box, "empowerment_box")
    img = screenshot_region(hwnd, box)
    config = "--psm 7 -c tessedit_char_whitelist=0123456789"
    text = pytesseract.image_to_string(preprocess(img, upscale=3), config=config).strip()

    m = _VALUE_RE.search(text)
    if not m:
        log.warning("Empowerment OCR %r didn't contain a recognizable number", text)
        return None
    level = int(m.group())
    log.info("Empowerment: %d", level)
    return level
