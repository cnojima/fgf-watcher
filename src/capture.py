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
        find_window,
        get_window_rect,
        list_windows,
        screenshot_region,
        screenshot_window,
    )
else:
    from win.capture_win import (
        WindowRect,
        describe_display_scale,
        find_window,
        get_window_rect,
        list_windows,
        screenshot_region,
        screenshot_window,
    )

__all__ = [
    "WindowRect",
    "describe_display_scale",
    "find_window",
    "get_window_rect",
    "list_windows",
    "screenshot_region",
    "screenshot_window",
]
