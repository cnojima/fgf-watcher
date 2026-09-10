"""Key calibrated pixel data (region boxes, screen fingerprints, click/drag
coordinates) by the exact window content size it was calibrated against.

Confirmed empirically (see README/CLAUDE.md): a fingerprint or click
coordinate calibrated at one window size lands on the wrong pixel entirely at
a different size, even when the "resolution" setting or aspect ratio is
nominally the same. Windows DPI scaling varies per-monitor the same way
(100/125/150/175%, auto-selected by the OS - no single default). Pixel-exact
calibration only transfers across an *exact* window content size match, so
that's the key - not resolution name, aspect ratio, or DPI% alone (those are
contributing factors, but the final captured pixel size is what calibrated
data actually depends on).
"""
import logging
import sys
from typing import TypeVar

from capture import describe_display_scale, get_window_rect

log = logging.getLogger(__name__)

T = TypeVar("T")

ProfileKey = tuple[str, tuple[int, int]]  # (sys.platform, (width, height))


def select_profile(hwnd, profiles: dict[ProfileKey, T], data_name: str) -> T:
    """Exact match on (sys.platform, current window content size). Falls back
    to a (platform, (0, 0)) sentinel entry if one is registered - today's
    Windows-only case, where the original calibration's exact window size was
    never recorded, so it can't be given a real key. Anything else (including
    every macOS profile) must match exactly, or this raises with enough
    detail to add a new profile rather than silently using the wrong one."""
    rect = get_window_rect(hwnd)
    size = (rect.width, rect.height)
    key: ProfileKey = (sys.platform, size)
    if key in profiles:
        log.debug("Selected %s profile for exact match %s", data_name, key)
        return profiles[key]

    fallback: ProfileKey = (sys.platform, (0, 0))
    if fallback in profiles:
        log.debug("Selected %s profile via fallback (no exact match for %s)", data_name, key)
        return profiles[fallback]

    known = ", ".join(f"{plat} {w}x{h}" for plat, (w, h) in profiles) or "(none)"
    log.error("No calibrated %s for window size %s", data_name, size)
    raise RuntimeError(
        f"No calibrated {data_name} for this window - detected {sys.platform} at "
        f"{size[0]}x{size[1]} ({describe_display_scale(hwnd)}).\n"
        f"Known profiles: {known}\n"
        "Calibrate this exact size with calibrate.py and add a profile for it."
    )
