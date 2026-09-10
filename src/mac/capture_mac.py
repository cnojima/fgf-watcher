"""Locate a game window and grab screenshots of it (or regions within it) - macOS backend.

Mirrors win/capture_win.py's public surface exactly, backed by Quartz/AppKit
(pyobjc) instead of win32gui.
"""
import logging
from dataclasses import dataclass

import mss
from AppKit import NSScreen, NSWorkspace
from PIL import Image
from Quartz import (
    CGWindowListCopyWindowInfo,
    kCGNullWindowID,
    kCGWindowListOptionOnScreenOnly,
)

log = logging.getLogger(__name__)


@dataclass
class WindowRect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


def _backing_scale_factor() -> float:
    """Points-to-pixels scale factor for the main screen (2.0 on Retina) -
    used only for describe_display_scale()'s human-readable diagnostic below,
    NOT for coordinate math.

    Confirmed live (see git history / session notes): despite this being a
    Retina display, this mss version's sct.monitors reports the screen in
    POINTS (matching NSScreen.frame() 1:1), and sct.grab() expects/returns
    coordinates in that same points space - not physical pixels. An earlier
    version of this file multiplied window bounds by this scale factor before
    handing them to mss, assuming mss wanted physical pixels (mirroring the
    Windows DPI-awareness pattern) - that assumption was wrong here and
    produced a capture region ~2x too large/offset, which mss silently
    padded with white wherever the request fell outside its real (points)
    screen bounds. Confirmed by direct comparison: capturing with raw,
    unscaled kCGWindowBounds points produced a perfect, full capture;
    doubling them did not. get_window_rect() below must stay in points.
    """
    screen = NSScreen.mainScreen()
    return float(screen.backingScaleFactor()) if screen else 1.0


def _list_window_infos() -> list[dict]:
    infos = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
    return list(infos) if infos else []


def find_window(title_substring: str) -> int:
    """Return the CGWindowID of the first on-screen window whose title contains
    title_substring (matched the same way as win/capture_win.py: substring,
    case-insensitive, against the window's own title).

    Uses kCGWindowListOptionOnScreenOnly, which - confirmed live - cannot see
    a window that macOS native fullscreen has moved to its own Space, even
    though the process is still running. That failure mode is indistinguishable
    here from "game isn't running"/"wrong title", so the error below covers
    both rather than claiming a diagnosis this check can't actually make.
    """
    needle = title_substring.lower()
    for info in _list_window_infos():
        if info.get("kCGWindowLayer", 0) != 0:
            continue  # skip menu bar, desktop, etc. - normal app windows are layer 0
        name = info.get("kCGWindowName", "") or ""
        if needle in name.lower():
            log.debug("Found window %r matching %r", name, title_substring)
            return int(info["kCGWindowNumber"])
    raise RuntimeError(
        f"No game window matching {title_substring!r} found. No game running, or in "
        "fullscreen mode (not supported) - switch to windowed mode."
    )


def list_windows() -> list[str]:
    """List titles of all visible top-level windows with non-empty titles."""
    titles: list[str] = []
    for info in _list_window_infos():
        if info.get("kCGWindowLayer", 0) != 0:
            continue
        name = info.get("kCGWindowName", "") or ""
        if name.strip():
            titles.append(name)
    return titles


def _find_window_info(hwnd: int) -> dict:
    for info in _list_window_infos():
        if int(info["kCGWindowNumber"]) == hwnd:
            return info
    raise RuntimeError(f"Window {hwnd} is no longer on screen")


def get_window_rect(hwnd: int) -> WindowRect:
    """Whole-window frame (title bar included - macOS has no cheap client-rect-only
    query for another app's window) in POINT screen coordinates - the same
    space mss.grab() and CGEventPost operate in on this system (see
    _backing_scale_factor's docstring for why this is points, not pixels)."""
    info = _find_window_info(hwnd)
    bounds = info["kCGWindowBounds"]
    left = round(bounds["X"])
    top = round(bounds["Y"])
    width = round(bounds["Width"])
    height = round(bounds["Height"])
    return WindowRect(left, top, left + width, top + height)


def screenshot_window(hwnd: int) -> Image.Image:
    """Screenshot the frame of hwnd.

    mss captures a screen *region* at hwnd's coordinates, not hwnd's content
    directly - if another window is on top of that region this would silently
    capture the wrong thing. So this refuses to shoot unless hwnd's owning
    app is actually frontmost, rather than return a screenshot of whatever's
    covering it (same contract as win/capture_win.py).
    """
    info = _find_window_info(hwnd)
    owner_pid = info.get("kCGWindowOwnerPID")
    frontmost = NSWorkspace.sharedWorkspace().frontmostApplication()
    if frontmost is None or frontmost.processIdentifier() != owner_pid:
        log.warning("Refusing screenshot: window %d is not foreground", hwnd)
        raise RuntimeError(
            "Target window is not in the foreground (something else is covering it, "
            "or it's minimized/switched away from) - bring it to front before capturing, "
            "since a screenshot here would silently grab whatever's on top instead."
        )
    rect = get_window_rect(hwnd)
    with mss.MSS() as sct:
        monitor = {"left": rect.left, "top": rect.top, "width": rect.width, "height": rect.height}
        raw = sct.grab(monitor)
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


def screenshot_region(hwnd: int, box: tuple[int, int, int, int]) -> Image.Image:
    """box is (left, top, right, bottom) in points relative to the window frame."""
    full = screenshot_window(hwnd)
    return full.crop(box)


def describe_display_scale(hwnd: int) -> str:
    """Human-readable Retina-scale diagnostic for display_profiles.py's error
    messages - not used for any coordinate math."""
    scale = _backing_scale_factor()
    screen = NSScreen.mainScreen()
    if screen is None:
        return f"macOS backing scale {scale}x, display info unavailable"
    frame = screen.frame()
    return (
        f"macOS backing scale {scale}x, display set to "
        f"{int(frame.size.width)}x{int(frame.size.height)}pt"
    )
