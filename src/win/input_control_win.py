"""Building blocks for menu navigation: focus the window, then click/press keys
at coordinates relative to its client area. Uses pydirectinput instead of
pyautogui because many games only respond to DirectInput-style events.
"""
import logging
import time

import pydirectinput
import win32gui

from win.capture_win import get_window_rect

log = logging.getLogger(__name__)

pydirectinput.PAUSE = 0.05


def focus_window(hwnd: int) -> None:
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.1)  # let the OS finish the focus switch before sending input


def click(hwnd: int, x: int, y: int) -> None:
    """x, y are pixels relative to the window's client area (same frame as calibrate.py)."""
    log.debug("click(%d, %d)", x, y)
    focus_window(hwnd)
    rect = get_window_rect(hwnd)
    pydirectinput.moveTo(rect.left + x, rect.top + y)
    pydirectinput.click()


def press_key(hwnd: int, key: str) -> None:
    log.debug("press_key(%r)", key)
    focus_window(hwnd)
    pydirectinput.press(key)


def drag(hwnd: int, start_x: int, start_y: int, end_x: int, end_y: int,
         duration: float = 0.3, steps: int = 12, hold: float = 0.2) -> None:
    """Click-and-drag from (start_x, start_y) to (end_x, end_y) (window client-area
    coords), moving through intermediate points rather than jumping straight there.

    This game has no scroll wheel or key support for scrollable lists - pydirectinput
    doesn't even expose a scroll() (it has no MOUSEEVENTF_WHEEL wrapper), and the UI
    is a touch-style interface anyway. To scroll a list down (reveal lower content),
    drag from a lower point to a higher one, same as a touchscreen swipe-up.

    The list has scroll inertia/momentum, so releasing the instant the cursor
    reaches end_x/end_y reads as a flick and keeps coasting afterward -
    momentum that isn't accounted for by the requested drag distance, making
    the actual resulting scroll amount inconsistent between calls. Holding
    the button down at the end point for `hold` seconds before releasing
    reads as a deliberate stop instead, same as holding a touchscreen swipe
    in place before lifting off.
    """
    log.debug("drag((%d, %d) -> (%d, %d))", start_x, start_y, end_x, end_y)
    focus_window(hwnd)
    rect = get_window_rect(hwnd)
    sx, sy = rect.left + start_x, rect.top + start_y
    ex, ey = rect.left + end_x, rect.top + end_y

    pydirectinput.moveTo(sx, sy)
    pydirectinput.mouseDown()
    for i in range(1, steps + 1):
        t = i / steps
        pydirectinput.moveTo(int(sx + (ex - sx) * t), int(sy + (ey - sy) * t))
        time.sleep(duration / steps)
    time.sleep(hold)
    pydirectinput.mouseUp()
