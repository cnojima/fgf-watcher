"""Locate a game window and grab screenshots of it (or regions within it)."""
import ctypes
from dataclasses import dataclass

import mss
import win32gui
from PIL import Image

# Must happen before any win32gui coordinate queries or mss capture: without it,
# this process is DPI-unaware and win32gui returns coordinates in a virtualized
# logical-pixel space that doesn't match the physical pixels mss/SetCursorPos use
# on a scaled display (e.g. 125%), silently misaligning every capture and click.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
except (AttributeError, OSError):
    ctypes.windll.user32.SetProcessDPIAware()  # fallback for pre-8.1 Windows


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


def find_window(title_substring: str) -> int:
    """Return the hwnd of the first visible window whose title contains title_substring."""
    matches: list[tuple[int, str]] = []

    def _callback(hwnd: int, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if title_substring.lower() in title.lower():
            matches.append((hwnd, title))

    win32gui.EnumWindows(_callback, None)

    if not matches:
        raise RuntimeError(f"No visible window found matching {title_substring!r}")
    hwnd, title = matches[0]
    return hwnd


def list_windows() -> list[str]:
    """List titles of all visible top-level windows with non-empty titles. Useful for discovering the exact title to target."""
    titles: list[str] = []

    def _callback(hwnd: int, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title.strip():
                titles.append(title)

    win32gui.EnumWindows(_callback, None)
    return titles


def get_window_rect(hwnd: int) -> WindowRect:
    """Client-area rect (excludes title bar/borders) in screen coordinates."""
    left, top, right, bottom = win32gui.GetClientRect(hwnd)
    left, top = win32gui.ClientToScreen(hwnd, (left, top))
    right, bottom = win32gui.ClientToScreen(hwnd, (right, bottom))
    return WindowRect(left, top, right, bottom)


def screenshot_window(hwnd: int) -> Image.Image:
    """Screenshot the client area of hwnd.

    mss captures a screen *region* at hwnd's coordinates, not hwnd's content
    directly - if another window is on top of that region (alt-tabbed away,
    covered by a browser, etc.) this would silently capture the wrong thing.
    So this refuses to shoot unless hwnd is actually the foreground window,
    rather than return a screenshot of whatever's covering it.
    """
    if win32gui.GetForegroundWindow() != hwnd:
        raise RuntimeError(
            "Target window is not in the foreground (something else is covering it, "
            "or it's minimized/alt-tabbed away) - bring it to front before capturing, "
            "since a screenshot here would silently grab whatever's on top instead."
        )
    rect = get_window_rect(hwnd)
    with mss.mss() as sct:
        monitor = {"left": rect.left, "top": rect.top, "width": rect.width, "height": rect.height}
        raw = sct.grab(monitor)
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


def screenshot_region(hwnd: int, box: tuple[int, int, int, int]) -> Image.Image:
    """box is (left, top, right, bottom) in pixels relative to the window's client area."""
    full = screenshot_window(hwnd)
    return full.crop(box)
