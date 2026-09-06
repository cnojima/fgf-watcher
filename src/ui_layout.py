"""Pixel-coordinate UI layout, keyed by (platform, window content size) - see
display_profiles.py for why exact-size keying matters. Consolidates every
click/box/drag coordinate used across nav.py, flagships.py,
attribute_details.py, and collect_all_flagships.py in one place, since they
were all calibrated together against the same reference window and would
drift together whenever that changes.
"""
from dataclasses import dataclass

from display_profiles import ProfileKey, select_profile


@dataclass(frozen=True)
class UILayout:
    back_arrow: tuple[int, int]                  # nav.py: on-screen back chevron, present on every overlay
    first_card_click: tuple[int, int]            # flagships.py / collect_all_flagships.py: first fleet-list card
    name_box: tuple[int, int, int, int]          # flagships.py / collect_all_flagships.py: ship name OCR box
    right_arrow: tuple[int, int]                 # flagships.py / collect_all_flagships.py: page to next ship
    hamburger_icon: tuple[int, int]              # attribute_details.py: opens the ship detail view's menu
    details_tab: tuple[int, int]                 # attribute_details.py: Attribute Details modal's Details tab
    table_box: tuple[int, int, int, int]         # attribute_details.py: scrollable stat table capture region
    table_tab_bar_height: int                    # attribute_details.py: static chrome to skip when diffing scroll offset
    drag_from: tuple[int, int]                   # attribute_details.py: scroll-down drag start
    drag_to: tuple[int, int]                     # attribute_details.py: scroll-down drag end
    attribute_close_button: tuple[int, int]      # collect_all_flagships.py: closes the Attribute Details overlay

    @property
    def expected_scroll_offset(self) -> int:
        return self.drag_from[1] - self.drag_to[1]


_LAYOUT_PROFILES: dict[ProfileKey, UILayout] = {
    # Legacy default: this calibration's exact window size was never recorded
    # (see display_profiles.py) - used whenever no exact-size Windows profile matches.
    ("win32", (0, 0)): UILayout(
        back_arrow=(705, 35),
        first_card_click=(1000, 210),
        # Bottom was originally 65, which clipped descenders (p/y/g) and was
        # the actual cause of several OCR misreads (e.g. "Opportunity" ->
        # "Opportunitv"), not an OCR engine limitation - confirmed by
        # inspecting the crop directly.
        name_box=(845, 5, 1090, 80),
        right_arrow=(1825, 1010),
        hamburger_icon=(1645, 1385),
        details_tab=(1475, 410),
        # Bottom was originally 1060, then 1150 - both wrong, both from
        # eyeballing the full downscaled screenshot. At true max-scroll the
        # last section's content extends to y=1290; confirmed via zoom.py's
        # 10px grid against calibration_raw.png, not another eyeball guess.
        table_box=(650, 350, 1650, 1330),
        table_tab_bar_height=180,
        # Drag from a lower point to a higher one = touch-style swipe-up
        # (scrolls the list down). Exact distance matters less than it looks -
        # attribute_details.py measures actual scroll offset from pixel
        # content rather than trusting this number.
        drag_from=(1000, 900),
        drag_to=(1000, 550),
        attribute_close_button=(1275, 230),
    ),
    # Add a ("darwin", (width, height)): UILayout(...) entry per Mac window
    # size calibrated via calibrate.py (it prints the exact key to use).
}


def get_layout(hwnd) -> UILayout:
    return select_profile(hwnd, _LAYOUT_PROFILES, "UI layout")
