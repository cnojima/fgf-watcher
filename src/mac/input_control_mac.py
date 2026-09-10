"""Building blocks for menu navigation: focus the window, then click/press keys
at coordinates relative to its frame - macOS backend.

Mirrors win/input_control_win.py's public surface exactly, backed by Quartz
CGEvent posting (pyobjc) instead of pydirectinput.
"""
import subprocess
import time

from AppKit import NSRunningApplication, NSWorkspace
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

from mac.capture_mac import _find_window_info, get_window_rect

# Virtual keycodes (US ANSI layout) for the fixed set of keys this repo
# actually uses - see nav.py's OVERLAYS / BASE_VIEW_TOGGLE_KEY. CGEvent
# keyboard events need a raw keycode, not a name string like pydirectinput
# accepts, so add to this table if nav.py ever grows another shortcut.
_KEYCODES = {
    "space": 0x31,
    "enter": 0x24,
    "esc": 0x35,
    "v": 0x09,
    "b": 0x0B,
    "c": 0x08,
    "g": 0x05,
    "r": 0x0F,
}


def _post_mouse(event_type, x: float, y: float) -> None:
    """CGEventPost coordinates are points (global desktop space) - the same
    space get_window_rect() returns on this system (confirmed live: mss and
    CGEventPost agree on points here, despite Retina scaling - see
    capture_mac._backing_scale_factor's docstring), so no pixel/point
    conversion is needed between the two."""
    event = CGEventCreateMouseEvent(None, event_type, (x, y), kCGMouseButtonLeft)
    CGEventPost(kCGHIDEventTap, event)


def focus_window(hwnd: int) -> None:
    info = _find_window_info(hwnd)
    pid = info["kCGWindowOwnerPID"]
    app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
    if app is None:
        raise RuntimeError(f"No running application found for window {hwnd}")

    # NSRunningApplication.activateWithOptions_ (tried first, see git history)
    # can raise the window in the window-server's z-order without macOS ever
    # actually flipping "frontmost application" to it - confirmed live: the
    # app's activationPolicy was Regular (so this wasn't the Accessory/
    # Prohibited case where an app has no menu bar and genuinely can't become
    # frontmost), yet frontmostApplication() stayed on the calling terminal
    # indefinitely. That Cocoa call was made from a bare `python` process
    # with no NSApplication/run loop of its own - a known gap where the
    # app-switch handshake (an asynchronous distributed notification) doesn't
    # reliably complete. Apple Events activation (`osascript ... activate`)
    # goes through Launch Services / the target app's own event handler
    # instead, which doesn't depend on the caller having a run loop - the
    # standard way other process-external tools (Hammerspoon, AppleScript
    # switchers, etc.) bring another app to the front.
    bundle_id = app.bundleIdentifier()
    result = subprocess.run(
        ["osascript", "-e", f'tell application id "{bundle_id}" to activate'],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"osascript failed to activate {app.localizedName()!r} (bundle "
            f"{bundle_id!r}): {result.stderr.strip()}. This is usually a "
            f"denied/missing Automation permission for this terminal - check "
            f"System Settings > Privacy & Security > Automation."
        )

    # Still not instantaneous - poll for it actually completing rather than
    # guessing a fixed delay, and fail loudly if it never does instead of
    # silently proceeding with the wrong window focused.
    deadline = time.time() + 2.0
    while time.time() < deadline:
        frontmost = NSWorkspace.sharedWorkspace().frontmostApplication()
        if frontmost is not None and frontmost.processIdentifier() == pid:
            return
        time.sleep(0.05)

    frontmost = NSWorkspace.sharedWorkspace().frontmostApplication()
    still_frontmost = frontmost.localizedName() if frontmost else None
    raise RuntimeError(
        f"Sent 'activate' to {app.localizedName()!r} (pid {pid}, bundle "
        f"{bundle_id!r}) via osascript but it never became the frontmost "
        f"application - still {still_frontmost!r}. Check Automation "
        f"permission for this terminal (System Settings > Privacy & Security "
        f"> Automation) - the first run should have prompted to allow "
        f"controlling {app.localizedName()!r}; if that was denied, re-enable "
        f"it there."
    )


def click(hwnd: int, x: int, y: int) -> None:
    """x, y are points relative to the window's frame (same frame as calibrate.py)."""
    focus_window(hwnd)
    rect = get_window_rect(hwnd)
    px, py = rect.left + x, rect.top + y
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
    point coords). Mirrors win/input_control_win.py's drag() exactly: move through
    intermediate points, then hold at the end point before releasing, so this
    game's momentum-scrolling lists read it as a deliberate stop rather than a
    flick (see win/input_control_win.py's docstring for why that matters)."""
    focus_window(hwnd)
    rect = get_window_rect(hwnd)
    sx, sy = rect.left + start_x, rect.top + start_y
    ex, ey = rect.left + end_x, rect.top + end_y

    _post_mouse(kCGEventMouseMoved, sx, sy)
    _post_mouse(kCGEventLeftMouseDown, sx, sy)
    for i in range(1, steps + 1):
        t = i / steps
        _post_mouse(kCGEventLeftMouseDragged, sx + (ex - sx) * t, sy + (ey - sy) * t)
        time.sleep(duration / steps)
    time.sleep(hold)
    _post_mouse(kCGEventLeftMouseUp, ex, ey)
