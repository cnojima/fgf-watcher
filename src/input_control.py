"""Building blocks for menu navigation: focus the window, then click/press keys
at coordinates relative to its client area. Uses pydirectinput instead of
pyautogui because many games only respond to DirectInput-style events.
"""
import time

import pydirectinput
import win32gui

from capture import get_window_rect

pydirectinput.PAUSE = 0.05


def focus_window(hwnd: int) -> None:
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.1)  # let the OS finish the focus switch before sending input


def click(hwnd: int, x: int, y: int) -> None:
    """x, y are pixels relative to the window's client area (same frame as calibrate.py)."""
    focus_window(hwnd)
    rect = get_window_rect(hwnd)
    pydirectinput.moveTo(rect.left + x, rect.top + y)
    pydirectinput.click()


def press_key(hwnd: int, key: str) -> None:
    focus_window(hwnd)
    pydirectinput.press(key)
