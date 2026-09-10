"""Pixel-coordinate UI layout for the Champion collection screens, keyed by
(platform, window content size) - same convention as profiles/ui_layout.py
(see display_profiles.py for why exact-size keying matters). Kept as its own
registry rather than folded into UILayout since champions and flagships are
separate screens with no coordinate overlap - consolidating them into one
dataclass would just make both harder to read.

All values below were confirmed live against a running game (darwin,
(1280, 828)) - see calibration notes on each field. No Windows profile exists
yet; add one the same way profiles/ui_layout.py's win32 profile was built.
"""
from dataclasses import dataclass

from display_profiles import ProfileKey, select_profile


@dataclass(frozen=True)
class ChampionLayout:
    # Base-view bottom bar icon that opens the Champion collection grid.
    # Confirmed live: pressing nav.py's "c" overlay shortcut did NOT
    # reliably open this screen (landed back on system_map, likely a focus
    # issue), while clicking this icon directly worked every time - use
    # this, not nav.goto("champion").
    champion_grid_icon: tuple[int, int]

    # 5 column x-centers and the row y-centers visible in one viewport
    # (no scrolling) - confirmed live against a 17-champion roster that fit
    # entirely on screen. Row spacing is NOT uniform (rows 1-3 confirmed at
    # a ~190px pitch, but row 4 sits only ~140px below row 3) - this is
    # exactly why these are listed explicitly rather than computed from a
    # single row-height constant. A roster with more champions than fit in
    # one viewport needs scrolling, which champions.py measures by actual
    # pixel content (same _content_offset idiom as attribute_details.py),
    # not by assuming another fixed row position below these.
    grid_columns: tuple[int, int, int, int, int]
    grid_rows: tuple[int, ...]

    # Offset (left, top, right, bottom) from a card's (column, row) center
    # to its bottom status-text region, used to tell a locked/unrecruited
    # card (shows "N/40" - a slash) from an unlocked one (shows "Level NNN"
    # plus star pips, no slash) - confirmed live: OCR of this region with a
    # "0123456789/" whitelist reads a clean "0/40" on a locked card and
    # digit noise with no "/" on an unlocked one. Checking for "/" alone is
    # enough; no need to parse the unlocked card's noisy digit soup at all.
    card_status_offset: tuple[int, int, int, int]

    # --- Detail view: Info tab ---
    name_box: tuple[int, int, int, int]
    title_box: tuple[int, int, int, int]  # flavor subtitle under the name (e.g. "GOVERNOR") - not champion type
    quality_box: tuple[int, int, int, int]  # "LEGENDARY"/"EPIC" plain text banner, top-right
    star_level_pips_box: tuple[int, int, int, int]  # 5-pip strip next to the quality banner - see champion_star_level.py
    element_icon_box: tuple[int, int, int, int]  # 1st badge under the name - matched against icons/elements/
    type_icon_box: tuple[int, int, int, int]  # 2nd badge under the name - matched against icons/champion_types/
    level_box: tuple[int, int, int, int]
    power_box: tuple[int, int, int, int]
    weapon_badge_click: tuple[int, int]  # opens the equipped-weapon detail page; shows a "+" placeholder if none equipped
    # Pixel-color fingerprint for the "+" no-weapon-equipped placeholder
    # (points, expected RGB) - checked BEFORE ever clicking
    # weapon_badge_click, per explicit instruction not to click into that
    # placeholder at all. Confirmed live: the placeholder's ring is a
    # consistent dark teal (61,103,88-90) at both points regardless of
    # champion, while a real equipped weapon's badge art varies widely
    # there (confirmed distinct on a separate champion: 127-151 range) -
    # same pixel-fingerprint approach as profiles/fingerprints.py's screen
    # detection, just for a widget instead of a whole screen.
    weapon_badge_empty_fingerprint: tuple[tuple[int, int, tuple[int, int, int]], ...]

    # --- Attribute Details modal (hamburger icon, bottom-right of the
    # portrait) - confirmed to reuse the exact same click position and
    # close button as the ship version (attribute_close_button in
    # ui_layout.py), and the same "Space Combat"/"Ground Combat" tab
    # concept, but the content itself is a short flat list here (5-6 rows,
    # no scrolling needed) unlike the ship's nested/scrolling table. ---
    hamburger_icon: tuple[int, int]
    space_combat_tab: tuple[int, int]
    ground_combat_tab: tuple[int, int]
    attribute_modal_close: tuple[int, int]
    attribute_modal_box: tuple[int, int, int, int]  # the list content area, either tab

    # --- Weapon detail page (opened via weapon_badge_click) ---
    weapon_name_box: tuple[int, int, int, int]
    weapon_element_type_box: tuple[int, int, int, int]  # plain-text "KINETIC" / "ATTACK" pair, unlike the icon-only Info tab badges
    weapon_level_box: tuple[int, int, int, int]
    weapon_stats_box: tuple[int, int, int, int]
    # Confirmed live: this list doesn't fit in weapon_stats_box's visible
    # height (9 rows total, ~5 visible) and is drag-scrollable, same as the
    # ship attribute table - see scroll_stitch.py. No static header chrome
    # inside the box itself (unlike the ship table's tab bar), so the
    # stitching call uses static_header_height=0.
    #
    # Drag distance deliberately kept short (~30px) rather than matching a
    # full "page" scroll: scroll_stitch.content_offset can only measure an
    # offset up to (box_height - strip_h), and strip_h=80 is fixed to suit
    # the much taller ship table. weapon_stats_box is only 115px tall, so
    # a 100px drag (what a naive "drag most of the box" choice would use)
    # is mathematically unmeasurable - confirmed live: it silently capped
    # every measurement at ~15-21px, causing the stitch to splice in tiny
    # slivers, falsely detect a stall, and skip most of the list (missing
    # "POWER" and every Champion stat row) rather than raising any error.
    # A 30px drag stays safely under the 35px ceiling this box's height
    # allows.
    weapon_stats_drag_from: tuple[int, int]
    weapon_stats_drag_to: tuple[int, int]
    # This page comes in two variants sharing the exact same name/badge/
    # level/stats field positions above, differing only in what's below the
    # stats and how they close - confirmed live the hard way: a "Select
    # Weapon" browse variant (multiple owned weapons, an EQUIP button)
    # closes via an X button at a totally different position than the
    # simple single-weapon preview's back-arrow (champion_layout doesn't
    # have its own separate close position for that one - it's the shared
    # champion detail view's back arrow). Calling the wrong one silently
    # fails to close the page - confirmed live: it cascaded into repeatedly
    # misreading whatever weapon was left on screen for every subsequent
    # champion in a batch run, since nothing verified the close succeeded.
    # This box's text ("Select Weapon") is present only on that variant -
    # see champion_weapon.close_weapon_page.
    weapon_select_list_label_box: tuple[int, int, int, int]
    weapon_select_list_close: tuple[int, int]

    # The two "Lvl N" badges next to the weapon's Level bar (space combat
    # bonus, ground combat bonus) - confirmed live: each is an independent
    # toggle, not a tab switcher. Clicking one while the OTHER is already
    # open just closes that other one instead of switching to the clicked
    # one's content - confirmed by direct comparison of before/after
    # screenshots. Read each with a full open -> read -> close cycle before
    # touching the other one, rather than clicking straight from one to the
    # next. Order: (space combat icon, ground combat icon).
    weapon_bonus_icons: tuple[tuple[int, int], tuple[int, int]]
    weapon_bonus_info_box: tuple[int, int, int, int]

    # --- Bottom tab bar: Info / Ability / Star Level ---
    info_tab: tuple[int, int]
    ability_tab: tuple[int, int]
    star_level_tab: tuple[int, int]

    # --- Ability tab: 7 clickable icons (3 Space Combat left, Ultimate
    # center, 3 Ground Combat right) and the info box that updates below
    # whichever one was last clicked. ---
    ability_icons: tuple[tuple[int, int], ...]  # exactly 7, order: space x3, ultimate, ground x3
    # The per-ability info card has a fixed header (name/tag/level bar) and a
    # fixed footer ("Promote the Star Level..."), with only the middle
    # (description/Awakening Effect/Signature Weapon sections) actually
    # drag-scrollable - confirmed live by diffing before/after-scroll
    # screenshots pixel-by-pixel: only y 503-671 changed, not the header
    # above or footer below. ability_header_box is read once per ability;
    # ability_scroll_box is scrolled and stitched (see scroll_stitch.py) to
    # get the full description, which routinely doesn't fit in one capture
    # (confirmed live: "Missile count increases to 11" and an entire
    # "Signature Weapon" section were cut off before scrolling).
    ability_header_box: tuple[int, int, int, int]
    ability_scroll_box: tuple[int, int, int, int]
    # Drag distance kept well under (box_height - 80px strip_h) = 98px -
    # scroll_stitch.content_offset can't measure an offset past that
    # ceiling (see weapon_stats_drag_from's comment for the full mechanism
    # and how it silently truncated data there). The original 100px drag
    # here was *just* over that ceiling and happened to work in testing
    # only because the actual per-scroll movement measured under it
    # (88-95px) - not a safe margin for a longer description on some other
    # champion's ability.
    ability_scroll_drag_from: tuple[int, int]
    ability_scroll_drag_to: tuple[int, int]

    @property
    def weapon_stats_expected_scroll_offset(self) -> int:
        return self.weapon_stats_drag_from[1] - self.weapon_stats_drag_to[1]

    @property
    def ability_expected_scroll_offset(self) -> int:
        return self.ability_scroll_drag_from[1] - self.ability_scroll_drag_to[1]


_CHAMPION_LAYOUT_PROFILES: dict[ProfileKey, ChampionLayout] = {
    ("darwin", (1280, 828)): ChampionLayout(
        champion_grid_icon=(940, 780),
        grid_columns=(433, 537, 640, 743, 845),
        grid_rows=(175, 365, 555, 695),
        card_status_offset=(-45, 63, 47, 83),
        name_box=(433, 42, 700, 68),
        title_box=(433, 70, 600, 90),
        quality_box=(800, 68, 930, 90),
        star_level_pips_box=(835, 35, 930, 65),
        element_icon_box=(360, 98, 400, 138),
        type_icon_box=(403, 98, 443, 138),
        level_box=(605, 622, 675, 662),  # digits only - excludes the "Level" label line above (see champion_info._read_level)
        power_box=(600, 668, 700, 690),
        weapon_badge_click=(400, 195),
        weapon_badge_empty_fingerprint=((378, 195, (61, 103, 88)), (422, 195, (61, 103, 90))),
        hamburger_icon=(822, 722),
        space_combat_tab=(537, 227),
        ground_combat_tab=(742, 227),
        attribute_modal_close=(814, 176),
        attribute_modal_box=(452, 260, 830, 460),
        weapon_name_box=(455, 58, 825, 88),
        weapon_element_type_box=(548, 100, 730, 118),
        weapon_level_box=(515, 405, 575, 440),
        # Bottom trimmed 3px from the visually-obvious 700: the box's own
        # bottom edge renders a thin white border highlight that showed up
        # mid-composite at every stitch seam (confirmed by inspecting the
        # actual composite image, not guessed) - it corrupted whichever row
        # happened to land on a seam (e.g. "Formation DEF Bonus" read as
        # doubled/overlapping text). Excluding it from the capture in the
        # first place, rather than trying to filter it out after stitching,
        # is the fix.
        weapon_stats_box=(470, 585, 820, 697),
        weapon_stats_drag_from=(640, 680),
        weapon_stats_drag_to=(640, 650),
        weapon_select_list_label_box=(449, 505, 570, 530),
        weapon_select_list_close=(904, 60),
        weapon_bonus_icons=((590, 505), (690, 505)),
        weapon_bonus_info_box=(463, 163, 817, 460),
        info_tab=(501, 800),
        ability_tab=(640, 800),
        star_level_tab=(778, 800),
        ability_icons=(
            (517, 163), (482, 253), (517, 340),  # space combat: top, mid, bottom
            (640, 305),  # ultimate (locked until star level maxed)
            (762, 163), (797, 253), (762, 340),  # ground combat: top, mid, bottom
        ),
        ability_header_box=(463, 405, 817, 500),
        ability_scroll_box=(463, 500, 817, 678),
        ability_scroll_drag_from=(640, 640),
        ability_scroll_drag_to=(640, 570),
    ),
}


def get_champion_layout(hwnd) -> ChampionLayout:
    return select_profile(hwnd, _CHAMPION_LAYOUT_PROFILES, "champion UI layout")
