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
"""
from dataclasses import dataclass

from capture import screenshot_window

RGB = tuple[int, int, int]


@dataclass
class Fingerprint:
    # each point is (x, y, expected_rgb) in the window's client-area coordinates
    points: list[tuple[int, int, RGB]]
    tolerance: int = 30


FINGERPRINTS: dict[str, Fingerprint] = {
    "system_map": Fingerprint(points=[
        (112, 240, (209, 197, 195)),  # inside "Trader Era" letter stroke
        (120, 235, (209, 199, 199)),
    ]),
    "flagship": Fingerprint(points=[
        (1220, 40, (237, 241, 211)),  # inside "FLAGSHIP" title letter stroke
        (1210, 30, (75, 147, 132)),
    ]),
}


def _close(a: RGB, b: RGB, tol: int) -> bool:
    return all(abs(a[i] - b[i]) <= tol for i in range(3))


def current_screen(hwnd) -> str | None:
    """Returns the name of the first matching known screen, or None if no
    fingerprint matches (e.g. mid-transition animation, or an uncatalogued screen)."""
    img = screenshot_window(hwnd)
    for name, fp in FINGERPRINTS.items():
        if all(_close(img.getpixel((x, y)), rgb, fp.tolerance) for x, y, rgb in fp.points):
            return name
    return None


def at_screen(hwnd, name: str) -> bool:
    return current_screen(hwnd) == name
