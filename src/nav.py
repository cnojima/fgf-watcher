"""Navigate between game screens.

The game has two kinds of screens:

- Base views: "system_map" (the star map) and "city_view" (the flagship's
  interior room view). Only these two exist, and SPACE toggles between them
  ("Enter/Exit City View" per docs/keyboard-shortcuts.jpg) - there's no key
  that jumps directly to one, only a toggle relative to whichever is current.

- Overlays: panels like the fleet list (V), Storage (B), Champion (C),
  Guild (G), Prime Radiant (R), Chat (ENTER) that open on top of whichever
  base view is active. Each has a direct keyboard shortcut to open it.

ESC is deliberately never used here for closing an overlay or resetting
state. It's mapped to "Quit game" when pressed from a base view, and per a
known game bug it can also trigger a full quit when pressed from certain
overlays instead of closing just that overlay - unsafe as a generic
navigation action. Overlays are closed with the on-screen back-arrow click
instead, which has no such failure mode.
"""
import time
from dataclasses import dataclass

from profiles.fingerprints import at_screen, current_screen, has_fingerprint
from input_control import click, press_key
from profiles.ui_layout import get_layout

BASE_VIEWS = {"system_map", "city_view"}
BASE_VIEW_TOGGLE_KEY = "space"


@dataclass
class Screen:
    name: str
    key: str | None = None  # keyboard shortcut that opens this overlay directly


OVERLAYS: dict[str, Screen] = {
    "fleet_list": Screen("fleet_list", key="v"),
    "storage": Screen("storage", key="b"),
    "champion": Screen("champion", key="c"),
    "guild": Screen("guild", key="g"),
    "radiant": Screen("radiant", key="r"),
    "chat": Screen("chat", key="enter"),
}


def goto(hwnd, screen_name: str, verify: bool = True, timeout: float = 2.0) -> None:
    """Navigate to screen_name. Verifies arrival via pixel fingerprint when one
    is catalogued for that screen (see fingerprints.py); otherwise fires the
    action and returns without checking.

    For a base view, call back() first if an overlay is currently open -
    goto() only handles the system_map/city_view toggle itself, and doesn't
    know how to close an arbitrary overlay on top of it."""
    if screen_name in BASE_VIEWS:
        current = current_screen(hwnd)
        if current == screen_name:
            return
        if current is not None and current not in BASE_VIEWS:
            raise RuntimeError(
                f"Currently on overlay {current!r}; call back(hwnd) to close it "
                f"before toggling base views"
            )
        press_key(hwnd, BASE_VIEW_TOGGLE_KEY)
    else:
        screen = OVERLAYS[screen_name]
        press_key(hwnd, screen.key)

    if verify and has_fingerprint(hwnd, screen_name):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if at_screen(hwnd, screen_name):
                return
            time.sleep(0.2)
        raise RuntimeError(f"Sent navigation action for {screen_name!r} but never landed on it")


def back(hwnd) -> None:
    """Click the on-screen back arrow to close the current overlay and return
    to whichever base view was active. Never uses ESC (see module docstring)."""
    click(hwnd, *get_layout(hwnd).back_arrow)
