"""Dismiss the game's transient guild/system notification banner
("Congratulations to [Guild]Name on becoming...", "[Guild]Name on becoming
the new Counselor...", etc.) - a global overlay that can slide in on top of
ANY screen (confirmed live on the champion grid, a champion's Info tab, and
a weapon detail page), not tied to any one screen's own layout.

Confirmed the source of several unrelated-looking OCR failures this
session: the banner sits in the same fixed screen position regardless of
what's underneath it, and happened to overlap champion_layout.py's
name_box/title_box/weapon_element_type_box on different screens, corrupting
those reads (e.g. a real weapon name misread as "be (}") in a way that
looked at first like a coordinate bug, not a transient overlay. Call
dismiss_if_present() before any OCR-sensitive capture that isn't otherwise
protected by a retry (see champion_weapon.py's _NAME_PATTERN checks for the
retry-based mitigation this replaces with something more direct).

Keyed by (platform, window content size) - see display_profiles.py.
"""
import logging

from capture import screenshot_window
from display_profiles import ProfileKey, select_profile
from input_control import click
from profiles.fingerprints import Fingerprint

log = logging.getLogger(__name__)

_NOTIFICATION_PROFILES: dict[ProfileKey, Fingerprint] = {
    # Confirmed live: the close button's small white "X" glyph reads as the
    # exact same (253,231,175) regardless of which screen the banner is
    # covering (champion grid, champion Info tab, weapon detail page all
    # gave an identical value) - a strong, opaque fingerprint, unlike some
    # of this game's translucent badges elsewhere. Points sampled from
    # several *absent*-banner screenshots at this same coordinate were all
    # far outside tolerance (dark UI chrome, character art, teal
    # background - none close to this bright near-white), so a single
    # point is enough to tell presence apart from absence confidently.
    ("win32", (2560, 1600)): Fingerprint(points=[(1830, 160, (253, 231, 175))], tolerance=20),
    ("darwin", (1280, 828)): Fingerprint(points=[(913, 108, (253, 231, 175))], tolerance=20),

}

_CLOSE_BUTTON: dict[ProfileKey, tuple[int, int]] = {
    ("win32", (2560, 1600)): (1830, 160),
    ("darwin", (1280, 828)): (913, 108),
}


def is_showing(hwnd) -> bool:
    fingerprint = select_profile(hwnd, _NOTIFICATION_PROFILES, "notification banner fingerprint")
    img = screenshot_window(hwnd)
    return all(
        all(abs(img.getpixel((x, y))[i] - rgb[i]) <= fingerprint.tolerance for i in range(3))
        for x, y, rgb in fingerprint.points
    )


def dismiss_if_present(hwnd) -> bool:
    """Checks for the banner and clicks its close button if present.
    Returns whether one was actually dismissed - never clicks blind, since
    the close button's coordinate sits close enough to at least one other
    real widget (a champion's lore icon) on some screens that a blind click
    risks opening the wrong thing when no banner is actually there."""
    if not is_showing(hwnd):
        return False
    close_button = select_profile(hwnd, _CLOSE_BUTTON, "notification banner close button")
    log.debug("Notification banner detected - dismissing")
    click(hwnd, *close_button)
    return True
