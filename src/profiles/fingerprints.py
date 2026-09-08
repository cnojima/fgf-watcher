"""Pixel-color fingerprints for detecting which screen is currently showing.

More robust than OCR for this purpose: several of this game's UI elements use
stylized/decorative fonts (e.g. the "FLAGSHIP" title) or sit over translucent
watermark graphics (e.g. "Trader Era") that defeat text recognition entirely.
But a single pixel inside a known letter stroke or background patch is
reliably the same color whenever that screen is showing, regardless of how
hard the text itself is to OCR. Points were picked by sampling the same pixel
coordinates across reference screenshots of different screens and choosing
ones with a large color delta (see git history of this file / dev notes for
the sampling script if new points are ever needed).

Keyed by (platform, window content size) - see display_profiles.py - since a
fingerprint calibrated at one window size lands on the wrong pixel entirely at
another, confirmed live: this file's system_map fingerprint missed completely
against a differently-sized macOS window.
"""
from dataclasses import dataclass

from capture import screenshot_window
from display_profiles import ProfileKey, select_profile

RGB = tuple[int, int, int]


@dataclass
class Fingerprint:
    # each point is (x, y, expected_rgb) in the window's client-area coordinates
    points: list[tuple[int, int, RGB]]
    tolerance: int = 30


_FINGERPRINT_PROFILES: dict[ProfileKey, dict[str, Fingerprint]] = {
    # Legacy default: this calibration's exact window size was never recorded
    # (see display_profiles.py) - used whenever no exact-size Windows profile matches.
    ("win32", (0, 0)): {
        "system_map": Fingerprint(points=[
            (112, 240, (209, 197, 195)),  # inside "Trader Era" letter stroke
            (120, 235, (209, 199, 199)),
        ]),
        "fleet_list": Fingerprint(points=[
            (1220, 40, (237, 241, 211)),  # inside "FLAGSHIP" title letter stroke
            (1210, 30, (75, 147, 132)),
        ]),
    },
    ("darwin", (1280, 828)): {
        # Confirmed via calibrate.py zoom + direct pixel sampling of
        # data/calibration_raw.png (not eyeballed) - both points sampled
        # solid across multiple adjacent rows, inside the "T"/"r" stems of
        # "Trader Era", not on an anti-aliased edge.
        "system_map": Fingerprint(points=[
            (43, 153, (100, 65, 68)),  # inside "T" stem of "Trader"
            (49, 154, (87, 50, 53)),  # inside "r" stem of "Trader"
        ]),
        # Confirmed via calibrate.py zoom + direct pixel sampling of
        # data/calibration_raw.png (not eyeballed) - both points sampled
        # solid across multiple adjacent rows/columns, inside the "FLAGSHIP"
        # title's "F" outline stroke and "L" fill, not on an anti-aliased edge.
        "fleet_list": Fingerprint(points=[
            (607, 55, (75, 147, 131)),  # inside "F" outline stroke of "FLAGSHIP"
            (631, 55, (237, 241, 211)),  # inside "L" fill of "FLAGSHIP"
        ]),
    },
    # Add a ("darwin", (width, height)): {...} entry per Mac window size calibrated.
}


def _close(a: RGB, b: RGB, tol: int) -> bool:
    return all(abs(a[i] - b[i]) <= tol for i in range(3))


def current_screen(hwnd) -> str | None:
    """Returns the name of the first matching known screen, or None if no
    fingerprint matches (e.g. mid-transition animation, or an uncatalogued screen)."""
    fingerprints = select_profile(hwnd, _FINGERPRINT_PROFILES, "screen fingerprints")
    img = screenshot_window(hwnd)
    for name, fp in fingerprints.items():
        if all(_close(img.getpixel((x, y)), rgb, fp.tolerance) for x, y, rgb in fp.points):
            return name
    return None


def has_fingerprint(hwnd, name: str) -> bool:
    """Whether the current platform/window-size profile has a catalogued
    fingerprint for screen `name` at all - nav.py uses this to decide whether
    it can verify arrival at a screen."""
    fingerprints = select_profile(hwnd, _FINGERPRINT_PROFILES, "screen fingerprints")
    return name in fingerprints


def at_screen(hwnd, name: str) -> bool:
    return current_screen(hwnd) == name
