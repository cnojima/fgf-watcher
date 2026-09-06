"""Platform dispatch: re-exports the Windows or macOS input backend.

Everything else in this repo imports from here (`from input_control import
click, press_key, ...`) rather than from
mac.input_control_mac/win.input_control_win directly, so downstream modules
need no platform-specific code at all.
"""
import sys

if sys.platform == "darwin":
    from mac.input_control_mac import click, drag, focus_window, press_key
else:
    from win.input_control_win import click, drag, focus_window, press_key

__all__ = ["click", "drag", "focus_window", "press_key"]
