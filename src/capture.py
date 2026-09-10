"""Platform dispatch: re-exports the Windows or macOS capture backend.

Everything else in this repo imports from here (`from capture import
find_window, ...`) rather than from mac.capture_mac/win.capture_win directly,
so downstream modules need no platform-specific code at all.
"""
import sys

if sys.platform == "darwin":
    from mac.capture_mac import (
        WindowRect,
        describe_display_scale,
        find_window as _find_window,
        get_window_rect,
        list_windows,
        screenshot_region,
        screenshot_window,
    )
else:
    from win.capture_win import (
        WindowRect,
        describe_display_scale,
        find_window as _find_window,
        get_window_rect,
        list_windows,
        screenshot_region,
        screenshot_window,
    )

# The game's window title differs by platform - macOS keeps the colon
# ("Foundation: Galactic Frontier"), Windows drops it ("Foundation Galactic
# Frontier") - confirmed live via list_windows() on both (see
# collect_all_flagships.py's git history for the mac confirmation). Trying
# both here means callers don't need to know which title format applies.
GAME_WINDOW_TITLES = ("Foundation: Galactic Frontier", "Foundation Galactic Frontier")


def find_window(title_substring: str | None = None) -> int:
    """Return the window handle matching title_substring. With no argument,
    auto-detects the game window by trying each of GAME_WINDOW_TITLES in turn."""
    if title_substring is not None:
        return _find_window(title_substring)
    errors = []
    for title in GAME_WINDOW_TITLES:
        try:
            return _find_window(title)
        except RuntimeError as e:
            errors.append(str(e))
    raise RuntimeError("No game window found. Tried: " + "; ".join(errors))


__all__ = [
    "WindowRect",
    "describe_display_scale",
    "find_window",
    "get_window_rect",
    "list_windows",
    "screenshot_region",
    "screenshot_window",
]
