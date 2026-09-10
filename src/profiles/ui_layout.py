"""Pixel-coordinate UI layout, keyed by (platform, window content size) - see
display_profiles.py for why exact-size keying matters. Consolidates every
click/box/drag coordinate used across nav.py, flagships.py,
attribute_details.py, and collect_all_flagships.py in one place, since they
were all calibrated together against the same reference window and would
drift together whenever that changes.
"""
from dataclasses import dataclass
from typing import TypeVar

from display_profiles import ProfileKey, select_profile

T = TypeVar("T")


def require_field(value: T | None, field_name: str) -> T:
    """Some UILayout fields (component/promotion detail sub-views) default to
    None until calibrated for a given platform/window size - fail with a
    clear, actionable message instead of clicking/cropping with None, which
    would either crash confusingly deep inside input_control/capture or
    (worse) silently misbehave."""
    if value is None:
        raise RuntimeError(
            f"No calibrated {field_name} for this profile - navigate to the "
            f"relevant screen, run calibrate.py shot/zoom to find it, then add "
            f"it to the current profile's UILayout entry in profiles/ui_layout.py."
        )
    return value


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
    overview_tab: tuple[int, int]                # collect_all_flagships.py: ship detail view's Overview tab
    component_tab: tuple[int, int]               # component_details.py: ship detail view's Component tab
    promote_tab: tuple[int, int]                 # promotion_details.py: ship detail view's Promote tab
    level_badge_box: tuple[int, int, int, int]   # collect_all_flagships.py: "Level NN" badge, unlocked-ship check

    # Component detail sub-view (component_details.py). Not yet calibrated for
    # every profile - default None rather than a guessed value, so an
    # uncalibrated platform/size fails loudly (via component_details._require)
    # instead of silently misclicking with a wrong-scale coordinate. Must stay
    # after every field above without a default (dataclass field-order rule).
    first_grid_icon: tuple[int, int] | None = None              # first of 5 component icons in the grid view
    thumbnail_positions: tuple[tuple[int, int], ...] | None = None  # 5 equipped-component thumbnail centers
    component_name_box: tuple[int, int, int, int] | None = None
    component_rarity_box: tuple[int, int, int, int] | None = None
    component_level_box: tuple[int, int, int, int] | None = None
    component_stats_box: tuple[int, int, int, int] | None = None
    component_set_bonus_box: tuple[int, int, int, int] | None = None

    # promotion_details.py. Same "None until calibrated" rule as the component
    # detail fields above - see component_details._require.
    promotion_badge_box: tuple[int, int, int, int] | None = None  # current-level triangle badge, Promote tab
    promote_button_box: tuple[int, int, int, int] | None = None   # PROMOTE/PROMOTED button, same tab

    # overview_details.py. Same "None until calibrated" rule as above.
    element_icon_box: tuple[int, int, int, int] | None = None  # element-type badge, top-left of Overview tab

    # empowerment_details.py. Same "None until calibrated" rule as above.
    empowerment_box: tuple[int, int, int, int] | None = None  # "+N" empowerment value, below the element badge

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
        # Previously flat constants in component_details.py (OVERVIEW_TAB/
        # COMPONENT_TAB/PROMOTE_TAB) - moved here for consistency with every
        # other click coordinate, unchanged in value.
        overview_tab=(1007, 1550),
        component_tab=(1280, 1550),
        promote_tab=(1542, 1550),
        # Previously collect_all_flagships.py's own flat LEVEL_BADGE_BOX
        # constant - moved here for consistency, unchanged in value.
        level_badge_box=(1230, 1055, 1360, 1180),
        # Previously component_details.py's own flat constants - moved here
        # for consistency, unchanged in value.
        first_grid_icon=(980, 490),
        thumbnail_positions=((950, 1500), (1110, 1500), (1270, 1500), (1425, 1500), (1585, 1500)),
        component_name_box=(1040, 540, 1700, 595),
        component_rarity_box=(1040, 595, 1700, 645),
        component_level_box=(1040, 650, 1400, 715),
        component_stats_box=(900, 760, 1700, 1030),
        component_set_bonus_box=(960, 1055, 1700, 1230),
        # Previously promotion_details.py's own flat constants - moved here
        # for consistency, unchanged in value.
        promotion_badge_box=(1090, 580, 1205, 665),
        promote_button_box=(960, 1345, 1600, 1425),
        # Confirmed via calibrate.py zoom against live Gram/Demerzel Overview
        # tabs - the element-type badge directly under the ship name. Matched
        # via icon_match.py against src/icons/elements/ rather than OCR'd -
        # it's a pictographic icon with no text in it. An initial (360, 100,
        # 390, 130) (read off the gridded calibration.png by eye) clipped the
        # badge on its right/bottom edge - confirmed by comparing the actual
        # crop against a reference icon side by side, not just a bad match
        # score alone (see CLAUDE.md: never trust a coordinate without zoom).
        element_icon_box=(730, 152, 790, 207),
        # Confirmed via calibrate.py zoom against a live Gram Overview tab:
        # the "+N" empowerment value, directly below the element badge. Box
        # deliberately excludes the leading "+" glyph itself, not just the
        # icon - confirmed live that including it made Tesseract misread it
        # as a stray "4" digit (e.g. "+12" -> "412") even under a digit-only
        # whitelist; cropping it out entirely was the only fix that worked,
        # not a whitelist/psm change (see CLAUDE.md: capture evidence first).
        # Width allows for the full 0-21 range (1-2 digits).
        empowerment_box=(710, 247, 740, 278),        
    ),
    ("darwin", (1280, 828)): UILayout(
        # Recalibrated live via calibrate.py zoom against fresh screenshots
        # (not eyeballed) - the previous values in this block were all
        # systematically wrong (most landed in the title bar or on blank
        # space), apparently calibrated before get_window_rect()/
        # screenshot_window() included the title bar in their coordinate
        # space. Every point/box below was confirmed either by zoom
        # inspection or by a live click that produced the expected screen
        # transition.
        back_arrow=(378, 52),  # confirmed live: closes ship detail -> fleet_list
        first_card_click=(640, 165),  # confirmed via zoom: center of first fleet card art
        # Generous top/bottom margin around the ship name text (y 32-65) to
        # avoid clipping descenders - see the g/j/p/q/y lesson in CLAUDE.md.
        # Right edge stops well before the "rename" pencil icon at x~495-515.
        name_box=(395, 25, 610, 72),
        right_arrow=(912, 545),  # confirmed via zoom: unchanged from prior calibration
        hamburger_icon=(822, 722),  # confirmed live: opens the Attribute Details modal
        details_tab=(737, 227),  # confirmed live: switches modal to the Details tab
        # Top of table_box is the modal's Overview/Details tab bar (y=196),
        # not the scrollable content - table_tab_bar_height below tells
        # attribute_details.py where the real (scrolling) content starts
        # within this crop. Bottom was 698 (the modal's own lower edge per an
        # earlier zoom check), but that was catching UI chrome below the
        # actual table content in the stitched debug composite - pulled in by
        # 20px.
        table_box=(433, 196, 848, 678),
        table_tab_bar_height=57,  # confirmed via zoom: tab bar occupies y 196-253 of table_box
        # Drag from a lower point to a higher one = touch-style swipe-up
        # (scrolls the list down). Exact distance matters less than it looks -
        # attribute_details.py measures actual scroll offset from pixel
        # content rather than trusting this number.
        drag_from=(640, 650),
        drag_to=(640, 400),
        attribute_close_button=(814, 176),  # confirmed live: closes the Attribute Details modal
        # Confirmed via calibrate.py zoom against a live ship detail view -
        # the three tab labels' x-centers along the shared tab bar (y=800).
        overview_tab=(490, 800),
        component_tab=(640, 800),
        promote_tab=(780, 800),
        level_badge_box=(620, 580, 660, 620),  # confirmed via calibrate.py zoom against a live unlocked ship
        # Previously component_details.py's own flat constants - moved here
        # for consistency, unchanged in value.
        first_grid_icon=(640, 525),
        thumbnail_positions=((475, 775), (550, 775), (635, 775), (725, 775), (792, 775)),
        component_name_box=(530, 310, 750, 325),
        component_rarity_box=(530, 330, 750, 345),
        component_level_box=(530, 360, 640, 380),
        component_stats_box=(460, 450, 830, 600),
        component_set_bonus_box=(460, 610, 720, 620),
        # Previously promotion_details.py's own flat constants - moved here
        # for consistency, unchanged in value.
        # promotion_badge_box=(590, 325, 680, 425),
        promotion_badge_box=(540, 310, 600, 370),
        promote_button_box=(480, 680, 780, 750),
        # Confirmed via calibrate.py zoom against live Gram/Demerzel Overview
        # tabs - the element-type badge directly under the ship name. Matched
        # via icon_match.py against src/icons/elements/ rather than OCR'd -
        # it's a pictographic icon with no text in it. An initial (360, 100,
        # 390, 130) (read off the gridded calibration.png by eye) clipped the
        # badge on its right/bottom edge - confirmed by comparing the actual
        # crop against a reference icon side by side, not just a bad match
        # score alone (see CLAUDE.md: never trust a coordinate without zoom).
        element_icon_box=(362, 96, 398, 132),
        # Confirmed via calibrate.py zoom against a live Gram Overview tab:
        # the "+N" empowerment value, directly below the element badge. Box
        # deliberately excludes the leading "+" glyph itself, not just the
        # icon - confirmed live that including it made Tesseract misread it
        # as a stray "4" digit (e.g. "+12" -> "412") even under a digit-only
        # whitelist; cropping it out entirely was the only fix that worked,
        # not a whitelist/psm change (see CLAUDE.md: capture evidence first).
        # Width allows for the full 0-21 range (1-2 digits).
        empowerment_box=(397, 147, 430, 181),
    )
}


def get_layout(hwnd) -> UILayout:
    return select_profile(hwnd, _LAYOUT_PROFILES, "UI layout")
