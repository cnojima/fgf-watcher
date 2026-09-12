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
from profiles.ui_layout import require_field

__all__ = ["ChampionLayout", "get_champion_layout", "require_field"]


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
    weapon_level_box: tuple[int, int, int, int]

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

    # Not yet calibrated for every profile - default None rather than a
    # guessed value, so an uncalibrated platform fails loudly (via
    # require_field, same helper profiles/ui_layout.py's UILayout uses for
    # its own not-yet-calibrated sub-view fields) instead of silently
    # misclicking with a wrong-scale coordinate. Must stay after every field
    # above without a default (dataclass field-order rule).
    #
    # Offset (left, top, right, bottom) from a card's (column, row) center to
    # its bottom status-text region, used to tell a locked/unrecruited card
    # (shows "N/40" - a slash) from an unlocked one (shows "Level NNN" plus
    # star pips, no slash) - see champions.py._card_state.
    card_status_offset: tuple[int, int, int, int] | None = None

    # Grid screen's "CHAMPION" title box - see champions.on_grid. Was
    # previously a single flat module constant shared across every profile
    # regardless of platform/window size (confirmed broken live on darwin
    # (1280, 828): the stale value's x1=1400 exceeds that window's own
    # width, so it could never have landed on real content there) - moved
    # here so it's calibrated per profile like every other coordinate in
    # this file, instead of silently assuming one window size fits all.
    grid_title_box: tuple[int, int, int, int] | None = None

    # Pixel-color fingerprint VARIANTS for the "+" no-weapon-equipped
    # placeholder (each a tuple of (x, y, expected RGB) points; a badge
    # matches "empty" if ALL points of ANY ONE variant line up) - checked
    # BEFORE ever clicking weapon_badge_click, per explicit instruction not
    # to click into that placeholder at all. Multiple variants because this
    # ring's color isn't universal - see champion_weapon.has_weapon_equipped.
    weapon_badge_empty_fingerprint: tuple[tuple[tuple[int, int, tuple[int, int, int]], ...], ...] | None = None

    # --- Weapon detail page fields below: name/element-type/stats boxes,
    # the stats scroll drag, the "Select Weapon" browse-variant close
    # controls, and the two bonus-badge fields. See champion_weapon.py. ---
    weapon_name_box: tuple[int, int, int, int] | None = None
    weapon_element_type_box: tuple[int, int, int, int] | None = None  # plain-text "KINETIC" / "ATTACK" pair, unlike the icon-only Info tab badges
    weapon_stats_box: tuple[int, int, int, int] | None = None
    weapon_stats_drag_from: tuple[int, int] | None = None
    weapon_stats_drag_to: tuple[int, int] | None = None
    weapon_select_list_label_box: tuple[int, int, int, int] | None = None
    weapon_select_list_close: tuple[int, int] | None = None
    weapon_bonus_icons: tuple[tuple[int, int], tuple[int, int]] | None = None
    weapon_bonus_info_box: tuple[int, int, int, int] | None = None

    # Pixel-color fingerprint (points, expected RGB) for the "MAX-LEVEL
    # PREVIEW" button's inactive/outlined styling on a maxed weapon's detail
    # page - a structurally different layout from the plain single-weapon
    # preview and "Select Weapon" browse variants documented above (same
    # "one screen, two layouts" pattern as promotion_details.py's maxed-ship
    # badge - see CLAUDE.md). Sampled from two points inside the button's
    # gold-orange outline/text (a border corner and the "L" in "LEVEL"),
    # both confirmed live to read the same (213,155,58) - not yet compared
    # against how this same button renders for a non-maxed weapon (would
    # need a champion with an upgradeable, non-signature weapon open to
    # confirm the colors actually differ there).
    weapon_maxed_fingerprint: tuple[tuple[int, int, tuple[int, int, int]], ...] | None = None

    # champions.check_last_row_after_scroll: a real champion in the grid's
    # last row can have its status text render below the visible window
    # (confirmed live), unlike anything else in this grid - these support
    # scrolling down once to reveal it. grid_scroll_measure_box must stay
    # within the scrollable card area only (no fixed title/button chrome),
    # and drag_from/drag_to don't need to be precise - the actual movement
    # is measured from real content (see _scroll_grid_down), same principle
    # as every other scroll in this codebase.
    grid_scroll_drag_from: tuple[int, int] | None = None
    grid_scroll_drag_to: tuple[int, int] | None = None
    grid_scroll_measure_box: tuple[int, int, int, int] | None = None

    # The last row's confirmed "cy" (equivalent to a grid_rows entry) once
    # scrolling has revealed it - NOT derived from any measured scroll
    # offset. Confirmed live the grid doesn't uniformly translate all
    # content by the drag's measured pixel movement: the last row instead
    # snaps to this fixed resting position once scrolled into view (found
    # by direct search against a real "scrolled to bottom" screenshot,
    # confirmed reading "165" cleanly for the one real champion there and
    # "empty" for every other column in that row - see champions.py's
    # module docstring).
    grid_scrolled_last_row_y: int | None = None

    @property
    def weapon_stats_expected_scroll_offset(self) -> int:
        drag_from = require_field(self.weapon_stats_drag_from, "weapon_stats_drag_from")
        drag_to = require_field(self.weapon_stats_drag_to, "weapon_stats_drag_to")
        return drag_from[1] - drag_to[1]

    @property
    def ability_expected_scroll_offset(self) -> int:
        return self.ability_scroll_drag_from[1] - self.ability_scroll_drag_to[1]

    @property
    def grid_scroll_expected_offset(self) -> int:
        drag_from = require_field(self.grid_scroll_drag_from, "grid_scroll_drag_from")
        drag_to = require_field(self.grid_scroll_drag_to, "grid_scroll_drag_to")
        return drag_from[1] - drag_to[1]


_CHAMPION_LAYOUT_PROFILES: dict[ProfileKey, ChampionLayout] = {
    ("darwin", (1280, 828)): ChampionLayout(
        champion_grid_icon=(940, 780),
        grid_columns=(433, 537, 640, 743, 845),
        grid_rows=(175, 365, 555, 695),
        card_status_offset=(-45, 63, 47, 83),
        # Confirmed via calibrate.py zoom against a live grid screenshot,
        # then cross-checked by cropping data/calibration_raw.png at this
        # exact box and OCR'ing it directly - reads clean "CHAMPION". The
        # previous flat-constant value (1150, 10, 1400, 75) had x1=1400,
        # past this window's own 1280px width - could never have landed on
        # real content here (see this field's docstring above).
        grid_title_box=(580, 30, 710, 70),
        # Confirmed live: dragging from (640, 550) to (640, 250) (a 300px
        # throw, well within the visible card grid, over card art the same
        # way attribute_details.py's drag sits on top of table content)
        # measured a real 102px upward content shift via
        # grid_scroll_measure_box - confirmed by comparing two saved
        # screenshots (top vs. scrolled-to-bottom) with independent
        # cross-correlation checks at two different y-anchors, both
        # agreeing exactly at 102px. grid_scroll_measure_box excludes the
        # fixed "CHAMPION" title (ends ~y=90) and the fixed bottom bar/
        # RECRUIT button (starts ~y=750) - confirmed by direct pixel
        # inspection, not guessed.
        grid_scroll_drag_from=(640, 550),
        grid_scroll_drag_to=(640, 250),
        grid_scroll_measure_box=(390, 90, 890, 700),
        # Confirmed via direct search against a real "scrolled to bottom"
        # screenshot (not derived from the 102px general content-shift
        # measured above - that value read as garbage at this row, see
        # champions.py's module docstring): (695 - 58), reading "165" for
        # the one real champion in this row and "empty" for the rest.
        grid_scrolled_last_row_y=637,
        name_box=(433, 42, 700, 68),
        title_box=(433, 70, 600, 90),
        quality_box=(800, 68, 930, 90),
        star_level_pips_box=(835, 35, 930, 65),
        element_icon_box=(360, 98, 400, 138),
        type_icon_box=(403, 98, 443, 138),
        level_box=(605, 622, 675, 662),  # digits only - excludes the "Level" label line above (see champion_info._read_level)
        power_box=(600, 668, 700, 690),
        weapon_badge_click=(400, 195),
        # Second variant added after the single teal one below produced a
        # real false-negative live: Doug Rockwell owns no weapon on this
        # account, but has_weapon_equipped() read his badge as equipped
        # (matched neither variant) and clicked into the "+" placeholder
        # anyway, corrupting his capture (garbled name/stats read from
        # whatever page that click actually landed on) - per explicit
        # instruction that placeholder must never be clicked. Confirmed by
        # reading Doug's actual info-000.png frame at these exact points
        # ((122,118,84)/(123,119,84)) - a warm-gold LEGENDARY-tier tint,
        # same root cause as win32's Doug/Klara split (see win32's
        # weapon_badge_empty_fingerprint comment) - and cross-checked
        # against all 16 captured champions in the same run to confirm it
        # only matches Doug's own badge, not any equipped one.
        weapon_badge_empty_fingerprint=(
            ((378, 195, (61, 103, 88)), (422, 195, (61, 103, 90))),  # EPIC/teal (Lucius Pullo)
            ((378, 195, (122, 118, 84)), (422, 195, (123, 119, 84))),  # LEGENDARY (Doug Rockwell)
        ),
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
    # Confirmed live via calibrate.py zoom against a running game (not
    # eyeballed) at this exact window size - keyed by the real size rather
    # than a (0,0) fallback sentinel, unlike ui_layout.py's legacy win32
    # profile (see display_profiles.py for why that distinction matters).
    ("win32", (2560, 1600)): ChampionLayout(
        champion_grid_icon=(1889, 1505),  # "Champion" icon in the base-view bottom bar
        # Column pitch confirmed uniform at 205px via background-gap
        # detection at both ends of the row (not eyeballed).
        #
        # Row y-centers: an initial pass eyeballed these off one gridded
        # screenshot at ~295-298px pitch for rows 1-3 - looked plausible, and
        # clicking these values did successfully open cards (huge click
        # tolerance on a whole card hides a lot of imprecision). But that
        # imprecision broke card_status_offset (below), which needs real
        # accuracy: enumerate_grid()/_card_state() using that pitch correctly
        # read row 1 but silently misread most of rows 2-3 as "empty" (no
        # exception - a false negative that looks identical to "no more
        # champions here"), confirmed live in a batch scan that only
        # processed 3 of 12 remaining roster positions before finishing with
        # no error. Re-measured via tight zooms (radius <=150 - see
        # card_status_offset's note on why radius matters) directly on each
        # row's own "165"+pips status bar (a fixed screen element, unlike
        # the card art) - actual pitch is a uniform ~378px for rows 1-3, not
        # ~295-298px. Values here are each row's status-bar vertical center;
        # row 4 (single locked/next-tier card, no status bar at all - see
        # card_status_offset) is instead its portrait's vertical center,
        # measured the same way.
        grid_columns=(850, 1055, 1260, 1465, 1670),
        grid_rows=(440, 817, 1195, 1335),
        # Confirmed live: an initial box spanning the full icon+digits+pips
        # bar came back completely empty from OCR at every upscale tried
        # (3/6/8) despite the crop being visibly correct - the circular
        # weapon-type icon graphic included above the digits was confusing
        # psm 7 (expects one line of text, not a graphic+text mix), not an
        # OCR engine limitation (see CLAUDE.md: capture evidence before
        # tuning). Narrowing the box to just the digit/pip row (excluding
        # the icon) fixed it.
        #
        # This offset is now measured relative to grid_rows' corrected,
        # per-row digit-bar centers above (not a single row's card center
        # extrapolated to the others, which is what broke rows 2-3 - see
        # grid_rows' note). Confirmed live reading "165" cleanly on rows 1-3
        # with this offset. Row 4's card has no status bar at all (a locked/
        # next-tier preview, matching the pattern champions.py's docstring
        # already documents) - this box lands on blank card background
        # there, correctly reading as "empty".
        #
        # General lesson from this session: calibrate.py zoom's labels
        # become unreliable to read by eye above roughly radius 200-250 (text
        # crowds together at this game's font size) - this bit both this
        # field and several Info-tab boxes earlier in this profile. Only
        # trust wider zooms for rough click targets (a whole card, tolerant
        # of 100+px error), never for a tight OCR/pixel-fingerprint box.
        card_status_offset=(-70, -30, 20, 30),
        # name_box/title_box/element_icon_box/type_icon_box/weapon_badge_click
        # were all originally derived from one zoom crop (radius 400) whose
        # labels were too crowded to read reliably - confirmed live the hard
        # way: weapon_badge_click at the old (610,680) landed ~330px below the
        # actual badge, which is why clicking it never opened the weapon page
        # (not a game-version difference, as first assumed - see
        # champion_weapon.py's docstring for the corrected story). A first
        # re-measurement attempt (radius 350, on a second champion, Killer
        # Bee) turned out to have the SAME crowded-label problem for
        # name_box/title_box/element_icon_box/type_icon_box (its
        # weapon_badge_click reading happened to still land correctly, cross-
        # confirmed against a second, radius-180 zoom below). Radius ~400 and
        # ~350 both proved unreliable for reading text/box edges here - only
        # trust zoom crops at radius <=200 for this kind of precise boundary
        # reading; wider crops are fine for eyeballing rough click targets
        # (e.g. a whole card) where the tolerance is huge. Final values below
        # are all from radius-150-180 zooms on Zora Domini.
        # quality_box/star_level_pips_box/level_box/power_box were checked
        # against their original values at a clean radius and matched, so
        # those were left alone.
        name_box=(850, 10, 1140, 70),
        title_box=(850, 80, 1060, 120),
        quality_box=(1600, 80, 1895, 125),
        star_level_pips_box=(1655, 5, 1875, 75),
        element_icon_box=(695, 135, 785, 210),
        type_icon_box=(785, 135, 875, 210),
        level_box=(1130, 1195, 1350, 1290),
        power_box=(990, 1270, 1400, 1312),
        weapon_badge_click=(780, 345),  # confirmed via two independent tight zooms (Killer Bee and Zora Domini)
        # Confirmed live on Doug Rockwell (no weapon equipped - shows the "+"
        # placeholder). Unlike darwin's opaque ring, this badge's "empty"
        # circle is translucent - a horizontal pixel scan through it showed
        # the tan background bleeding through near the circle's curved edge
        # (an initial sample point there read as plain background, not the
        # ring), but a wide stable band well inside the circle (x 735-870 at
        # y 325, and y 305-380 at x 750/850) reads a consistent dark
        # olive-gray regardless of position within that band. Cross-checked
        # against two different equipped-weapon champions (Zora Domini,
        # Killer Bee) at these exact points - both differ from this
        # fingerprint by 20-100 per channel, well past the 25-tolerance
        # has_weapon_equipped() uses.
        #
        # A SECOND variant was needed after this fingerprint alone produced
        # a false positive live on Klara (EPIC quality, teal page theme):
        # her empty ring read (63,103,90)/(66,108,96) at these same points -
        # a ~60-point swing on the red channel from Doug's (LEGENDARY,
        # warm-gold theme) values above, confirmed to be the ring rendering
        # as a translucent overlay tinted by the page's own quality-tier
        # background rather than a fixed universal color (the two
        # equipped-weapon cross-checks above stay valid discriminators
        # against both variants - neither is within 25 of either). Add a
        # third variant the same way if another quality tier's empty badge
        # ever produces a third distinct color.
        weapon_badge_empty_fingerprint=(
            ((750, 340, (124, 117, 86)), (850, 340, (125, 121, 84))),  # LEGENDARY (Doug Rockwell)
            ((750, 340, (63, 103, 90)), (850, 340, (66, 108, 96))),  # EPIC (Klara)
        ),
        # Confirmed live: this is the SAME icon ui_layout.py's win32
        # UILayout.hamburger_icon already points at (1645,1385) - re-derived
        # independently here and landed within 6px, confirming that reuse.
        # (A different top-right icon on this screen opens the champion's
        # lore/bio page instead - see champion_weapon.py's docstring, which
        # already warns about exactly this mix-up.)
        hamburger_icon=(1651, 1389),
        space_combat_tab=(1090, 400),
        ground_combat_tab=(1390, 400),
        # NOT reused from ui_layout.py's win32 attribute_close_button
        # (1275, 230) - confirmed live that coordinate misses this modal's
        # actual close X by 422px on the x-axis (y matches closely). This
        # looks like a genuinely different widget (the champion Attribute
        # Details modal's own X button) rather than evidence that
        # ui_layout.py's stored value is wrong - nav.py's back() click at
        # ui_layout.py's win32 back_arrow (705,35) was separately confirmed
        # live this session to close the champion detail view correctly (an
        # earlier "this is stale too" note here was based on a bad test:
        # back() called with no overlay actually open, so the click landed
        # on bare map content instead of any button).
        attribute_modal_close=(1697, 235),
        # x0 corrected this session from 930 to 885 - the old value clipped
        # the left stroke of the first letter on every row ("Formation" ->
        # "ormation" every time; "Champion" -> ":hampion" on one row where
        # anti-aliasing happened to leave a stray mark instead of nothing).
        # Not a font/OCR problem - confirmed by cropping the exact old box
        # and looking at it directly (see CLAUDE.md's descender-clipping
        # lesson, same failure mode rotated 90 degrees). Re-verify with
        # calibrate.py zoom if this box is ever suspected stale again.
        attribute_modal_box=(885, 455, 1650, 950),
        # Weapon detail page fields below: all confirmed live once
        # weapon_badge_click's fix (above) actually opened the page. Read
        # off a maxed signature weapon's page (Zora Domini's "Endless
        # Whisper") - not yet cross-checked against a regular, non-signature
        # weapon's page. This variant DOES show plain-text element/type
        # badges ("KINETIC"/"ATTACK") despite an earlier session note
        # assuming signature weapons lacked them - that assumption was
        # itself downstream of weapon_badge_click's bug (it was never
        # actually opened programmatically before, only reached by manually
        # navigating there, so this structural claim was never actually
        # tested until now).
        # weapon_name_box/weapon_element_type_box corrected this session -
        # both had drifted ~75-80px higher than these original values on the
        # same weapon page (Zora Domini's "Endless Whisper" again), confirmed
        # by re-zooming a fresh live capture; weapon_level_box below was
        # unaffected. Likely a game UI update moved the title/badge row up
        # without touching the Level/stats section beneath it, rather than a
        # miscalibration - re-verify the rest of this profile if other
        # fields start reading empty/wrong.
        weapon_name_box=(790, 60, 1690, 120),
        weapon_element_type_box=(740, 130, 1490, 180),
        weapon_level_box=(1030, 755, 1140, 830),
        # Box covers the visible ~4 rows (POWER + 3 Formation bonuses); the
        # full list is 9 rows per champion_weapon.py's docstring, hence the
        # drag/stitch below. Live-scroll-tested; top edge was originally
        # 1085, confirmed live to start 30px too low (clipping the top of
        # the POWER row) and corrected to 1055.
        weapon_stats_box=(880, 1055, 1780, 1410),
        weapon_stats_drag_from=(1330, 1320),
        weapon_stats_drag_to=(1330, 1200),
        # Clicking either bonus icon on this signature weapon's page did NOT
        # visibly open/toggle an info card the way champion_weapon.py's
        # _read_bonuses docstring describes for a regular weapon - possibly
        # another signature-weapon-specific layout difference, not yet
        # investigated. weapon_bonus_info_box left uncalibrated (None) since
        # nothing was confirmed to actually open.
        weapon_bonus_icons=((1018, 970), (1233, 970)),  # space combat, ground combat - positions confirmed, click behavior not
        info_tab=(1007, 1550),  # matches ui_layout.py's win32 overview_tab almost exactly - same shared tab-bar row
        ability_tab=(1280, 1550),  # exact match to ui_layout.py's win32 component_tab
        star_level_tab=(1542, 1550),  # matches ui_layout.py's win32 promote_tab almost exactly
        ability_icons=(
            (1038, 251), (966, 440), (1039, 635),  # space combat: top, mid, bottom
            (1287, 513),  # ultimate
            (1526, 255), (1603, 445), (1520, 632),  # ground combat: top, mid, bottom
        ),
        ability_header_box=(540, 745, 1618, 940),
        ability_scroll_box=(540, 945, 1618, 1325),
        # Derived proportionally from darwin's drag/box-height ratio (~39%
        # of box height) rather than live-scroll-tested - scroll_stitch.py
        # measures the actual per-drag offset from pixel content rather
        # than trusting this number (see darwin's own comments on this
        # field), so an imprecise starting distance self-corrects.
        ability_scroll_drag_from=(1079, 1200),
        ability_scroll_drag_to=(1079, 1050),
        # Sampled live from a maxed signature weapon's detail page (see the
        # field's own docstring above) - both points read (213,155,58).
        weapon_maxed_fingerprint=((1290, 1424, (213, 155, 58)), (1455, 1487, (213, 155, 58))),
    ),
}


def get_champion_layout(hwnd) -> ChampionLayout:
    return select_profile(hwnd, _CHAMPION_LAYOUT_PROFILES, "champion UI layout")


def get_champion_layout_for_profile(profile: ProfileKey) -> ChampionLayout:
    """Return calibrated coordinates without requiring a live game window -
    same convention as ui_layout.get_layout_for_profile, for offline replay."""
    if profile in _CHAMPION_LAYOUT_PROFILES:
        return _CHAMPION_LAYOUT_PROFILES[profile]
    fallback = (profile[0], (0, 0))
    if fallback in _CHAMPION_LAYOUT_PROFILES:
        return _CHAMPION_LAYOUT_PROFILES[fallback]
    known = ", ".join(f"{platform} {width}x{height}" for platform, (width, height) in _CHAMPION_LAYOUT_PROFILES)
    raise RuntimeError(f"No calibrated champion UI layout for {profile[0]} {profile[1][0]}x{profile[1][1]}; known: {known}")
