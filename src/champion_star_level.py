"""Read a champion's star level (0-30) from the 5-pip strip next to the
quality banner (visible on every tab - Info/Ability/Star Level all show it,
so no tab navigation is needed to read it).

Star levels are grouped into six 5-star tiers, each with its own color
(confirmed via reference screenshots the user supplied of the in-game
"PREVIEW" milestone roadmap - src/icons/star_level/*.png, cropped from
those): teal (1-5), gold (6-10), orange (11-15), red (16-20), blue (21-25),
holographic (26-30).

This is NOT the pip widget shown on the Star Level tab itself (a different,
more complex widget below the portrait that shows a sliding window around
the current position plus an ambiguous "next star" preview pip - initially
mistaken for the source of truth here, but its preview pip's color doesn't
reliably indicate group membership, confirmed by direct pixel comparison
against the reference colors). The header strip is simpler: each of its 5
pips is always shown in its true, fully-saturated group color when earned -
there is no "empty/preview" state to disambiguate.

The 5 pips run newest-to-oldest, left to right: pip 1 is the most recently
earned star. Confirmed against a live example (Zora, told directly by the
user to be at star level 17): pips read as [red, red, orange, orange,
orange] - i.e. the two most recent stars (16, 17) are in the red tier
(16-20), and the three before that (13, 14, 15) are in orange (11-15).
Reading just the leftmost pip's tier plus how many leading pips share that
same tier is therefore enough to reconstruct the exact level:
level = (tier_index - 1) * 5 + run_length, with no ambiguity at tier
boundaries (a level exactly divisible by 5, e.g. 20, shows all 5 pips in
that tier's color with run_length 5 - not 0 - since a just-finished tier's
stars are still the 5 most recent ones).

Whole-image template matching (icon_match.match_icon) was tried first and
rejected for this: these pips are identical diamond shapes differing only
by fill color, so template matching's shape-sensitivity to crop framing
only added noise. Comparing average color of the pip's interior instead
(after trimming its background border) is both simpler and far more
robust here - confirmed by direct comparison of match distances.
"""
import logging
from pathlib import Path

import numpy as np
from PIL import Image

from capture import screenshot_region
from icon_match import autocrop_to_content
from profiles.champion_layout import ChampionLayout

log = logging.getLogger(__name__)

_ICONS_DIR = Path(__file__).resolve().parent / "icons" / "star_level"
# (tier index 1-6, reference filename) - order matters, it's the group sequence.
_TIERS = [
    (1, "1_teal.png"),
    (2, "2_gold.png"),
    (3, "3_orange.png"),
    (4, "4_red.png"),
    (5, "5_blue.png"),
    (6, "6_holo.png"),
]

_reference_colors: dict[str, np.ndarray] | None = None


def _pip_color(img: Image.Image) -> np.ndarray:
    """Average color of the pip's interior, after trimming its dark
    background border - see module docstring for why this (not whole-image
    template matching) is used for these solid-color diamond icons."""
    cropped = autocrop_to_content(img.convert("RGB"))
    arr = np.asarray(cropped, dtype=np.float64)
    h, w = arr.shape[:2]
    patch = arr[h * 3 // 8:h * 5 // 8, w * 3 // 8:w * 5 // 8]
    return patch.reshape(-1, 3).mean(axis=0)


def _get_reference_colors() -> dict[str, np.ndarray]:
    global _reference_colors
    if _reference_colors is None:
        _reference_colors = {
            name: _pip_color(Image.open(_ICONS_DIR / filename)) for name, filename in
            ((f"tier{i}", fname) for i, fname in _TIERS)
        }
        log.debug("Loaded %d star-level tier reference colors", len(_reference_colors))
    return _reference_colors


def _nearest_tier(color: np.ndarray) -> int:
    refs = _get_reference_colors()
    distances = {name: float(np.linalg.norm(color - ref)) for name, ref in refs.items()}
    best = min(distances, key=distances.get)
    return int(best.removeprefix("tier"))


def read_star_level(hwnd, layout: ChampionLayout) -> int:
    """Assumes a champion's detail view is currently showing, any tab
    active (the pip strip is part of the shared header, visible on all
    three tabs)."""
    img = screenshot_region(hwnd, layout.star_level_pips_box)
    w = img.width
    pip_colors = []
    for i in range(5):
        x0, x1 = int(i * w / 5), int((i + 1) * w / 5)
        pip_colors.append(_pip_color(img.crop((x0, 0, x1, img.height))))

    tiers = [_nearest_tier(c) for c in pip_colors]
    leftmost = tiers[0]
    run = 1
    for t in tiers[1:]:
        if t != leftmost:
            break
        run += 1

    level = (leftmost - 1) * 5 + run
    log.info("Star level: %d (tiers=%s)", level, tiers)
    return level
