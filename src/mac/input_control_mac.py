"""Building blocks for menu navigation: focus the window, then click/press keys
at coordinates relative to its frame - macOS backend.

Mirrors win/input_control_win.py's public surface exactly, backed by Quartz
CGEvent posting (pyobjc) instead of pydirectinput.
"""
import time

from AppKit import NSApplicationActivateIgnoringOtherApps, NSRunningApplication
from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventCreateMouseEvent,
    CGEventPost,
    kCGEventLeftMouseDown,
    kCGEventLeftMouseDragged,
    kCGEventLeftMouseUp,
    kCGEventMouseMoved,
    kCGHIDEventTap,
    kCGMouseButtonLeft,
)

from mac.capture_mac import _backing_scale_factor, _find_window_info, get_window_rect

# Virtual keycodes (US ANSI layout) for the fixed set of keys this repo
# actually uses - see nav.py's OVERLAYS / BASE_VIEW_TOGGLE_KEY. CGEvent
# keyboard events need a raw keycode, not a name string like pydirectinput
# accepts, so add to this table if nav.py ever grows another shortcut.
_KEYCODES = {
    "space": 0x31,
    "enter": 0x24,
    "v": 0x09,
    "b": 0x0B,
    "c": 0x08,
    "g": 0x05,
    "r": 0x0F,
}


def _pixel_to_point(px: int, py: int) -> tuple[float, float]:
    """CGEventPost coordinates are in points (global desktop space), while
    capture_mac works in physical pixels - convert before posting any event,
    using the same scale factor capture_mac uses to go the other way."""
    scale = _backing_scale_factor()
    return px / scale, py / scale


def _post_mouse(event_type, x: float, y: float) -> None:
    event = CGEventCreateMouseEvent(None, event_type, (x, y), kCGMouseButtonLeft)
    CGEventPost(kCGHIDEventTap, event)


def focus_window(hwnd: int) -> None:
    info = _find_window_info(hwnd)
    pid = info["kCGWindowOwnerPID"]
    app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
    if app is None:
        raise RuntimeError(f"No running application found for window {hwnd}")
    app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
    time.sleep(0.1)  # let the OS finish the focus switch before sending input


def click(hwnd: int, x: int, y: int) -> None:
    """x, y are pixels relative to the window's frame (same frame as calibrate.py)."""
    focus_window(hwnd)
    rect = get_window_rect(hwnd)
    px, py = _pixel_to_point(rect.left + x, rect.top + y)
    _post_mouse(kCGEventMouseMoved, px, py)
    _post_mouse(kCGEventLeftMouseDown, px, py)
    _post_mouse(kCGEventLeftMouseUp, px, py)


def press_key(hwnd: int, key: str) -> None:
    focus_window(hwnd)
    try:
        keycode = _KEYCODES[key]
    except KeyError:
        raise KeyError(
            f"No macOS virtual keycode mapped for {key!r} - add it to _KEYCODES "
            f"in input_control_mac.py (known keys: {sorted(_KEYCODES)})"
        ) from None
    down = CGEventCreateKeyboardEvent(None, keycode, True)
    up = CGEventCreateKeyboardEvent(None, keycode, False)
    CGEventPost(kCGHIDEventTap, down)
    CGEventPost(kCGHIDEventTap, up)


def drag(hwnd: int, start_x: int, start_y: int, end_x: int, end_y: int,
         duration: float = 0.3, steps: int = 12, hold: float = 0.2) -> None:
    """Click-and-drag from (start_x, start_y) to (end_x, end_y) (window-frame
    pixel coords). Mirrors win/input_control_win.py's drag() exactly: move through
    intermediate points, then hold at the end point before releasing, so this
    game's momentum-scrolling lists read it as a deliberate stop rather than a
    flick (see win/input_control_win.py's docstring for why that matters)."""
    focus_window(hwnd)
    rect = get_window_rect(hwnd)
    sx, sy = _pixel_to_point(rect.left + start_x, rect.top + start_y)
    ex, ey = _pixel_to_point(rect.left + end_x, rect.top + end_y)

    _post_mouse(kCGEventMouseMoved, sx, sy)
    _post_mouse(kCGEventLeftMouseDown, sx, sy)
    for i in range(1, steps + 1):
        t = i / steps
        _post_mouse(kCGEventLeftMouseDragged, sx + (ex - sx) * t, sy + (ey - sy) * t)
        time.sleep(duration / steps)
    time.sleep(hold)
    _post_mouse(kCGEventLeftMouseUp, ex, ey)
