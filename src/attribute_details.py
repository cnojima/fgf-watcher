"""Read a ship's full stat breakdown from the "Attribute Details" modal
(hamburger icon on the ship detail view -> Details tab), scrolling through
the whole table.

The table is a nested list: a section header with its total value (e.g.
"HP  1,029,897" or "Damage Reduction  60.00%"), followed by sub-rows (Level,
Promotion, Components, ...) that break down where that total comes from.

Earlier versions of this module scrolled, OCR'd each capture separately, and
merged the resulting text across captures - which meant tuning one global
scroll distance to satisfy two opposing needs at once: enough overlap between
captures for OCR redundancy (so a misread row gets a second chance), but not
so much that a row could resurface many captures after its own section's
header was last seen, causing it to be misattributed to whatever section was
*most recently* recognized (confirmed by tracing a real run). No single
distance satisfied both - large steps lost rows to lack of redundancy, small
steps caused stale misattribution.

This version sidesteps that tradeoff entirely: instead of merging OCR *text*
across captures, it stitches the *images* into one seamless composite first
(aligning each new capture against the previous one by actual pixel content,
not the requested drag distance - touch-scroll physics doesn't guarantee that
distance exactly), then runs OCR exactly once on the whole thing. With no
cross-capture merging step, cross-capture misattribution isn't possible. The
scroll/stitch mechanics themselves live in scroll_stitch.py, shared with
champion_weapon.py's stats list once that needed the exact same approach.

Section headers are NOT reliably distinguishable from sub-rows by casing -
top-level stats (HP, ATTACK, INT, DEF) happen to be short all-caps words, but
deeper derived stats have title-case, multi-word headers ("Damage
Reduction", "Chance to inflict Major Damage") that look just like a normal
label. What actually distinguishes them: sub-row labels are drawn from a
small, closed vocabulary (Level, Promotion, Components, ...), and section
headers aren't. So classification here is a whitelist match on the label,
not a capitalization check - an even earlier version used caps and silently
merged every title-case section's rows into the wrong bucket.
"""
import difflib
import logging
import re
import time
from pathlib import Path

from PIL import Image

from input_control import click
from ocr import preprocess, pytesseract
from profiles.ui_layout import get_layout
from scroll_stitch import stitch_scrolled_region

log = logging.getLogger(__name__)

MAX_SCROLLS = 45  # smaller per-drag distance means more scrolls needed to reach the bottom
# Per CLAUDE.md: when OCR misreads/drops something, look at the exact image it
# read rather than guessing at preprocessing tweaks - every past OCR failure in
# this repo turned out to be a bug in the crop/composite itself, not an engine
# limitation. Saved unconditionally (cheap) so it's always available to
# inspect after a run that comes back with missing/wrong sections.
DEBUG_DIR = Path(__file__).resolve().parent.parent / "data"

# Every sub-row label seen so far across HP/ATTACK/INT/DEF/Damage Reduction/
# Chance to inflict Major Damage. Extend this if a new section introduces a
# label not in this set - anything not matching (even fuzzily) is treated as
# a possible section header instead of a sub-row, so an incomplete list causes
# a mis-bucketed section rather than a silently dropped row.
# Confirmed by the user directly (not inferred from OCR output): these are all
# the valid modifier names, and not every one applies to every top-level stat -
# a section having a different subset of these than another section is normal
# game data, not a parsing error. "Resonance" was previously (wrongly) listed
# as its own top-level section in KNOWN_SECTION_NAMES below; it's a modifier
# like the others. "Construction" is unconfirmed - it showed up consistently
# in captures but wasn't in the user's confirmed list; flagged for follow-up
# rather than removed outright, since removing it wrongly would misclassify
# every section that has a real Construction modifier as a bogus new section.
KNOWN_SUBROW_LABELS = {
    "Level", "Promotion", "Components", "Technology", "Champions",
    "Resonance", "Crew", "Appearance", "Port", "Events",
    "Construction",  # TODO: unconfirmed, see note above
}

# Every section header seen so far. A candidate header that doesn't fuzzy-match
# either this or KNOWN_SUBROW_LABELS is unrecognized text (usually a badly
# mistimed capture, e.g. mid-scroll blur) and gets dropped rather than kept as
# a garbage section - see _classify_label. Extend this when a genuinely new
# section is confirmed by inspecting the raw crop, not just an OCR guess.
KNOWN_SECTION_NAMES = {
    "HP", "ATTACK", "INT", "DEF", "Load", "Command Points",
    "Crit Rate", "Crit Resistance", "Crit Damage",
    "Damage Bonus", "Damage Reduction",
    "Chance to inflict Major Damage",
}

# No trailing anchor and no constraint on what follows the number: the old
# version required everything after the value to contain zero digits, so a
# single stray OCR misread mid-number (e.g. "23,725" read as "23,/25", the
# "7" misread as "/") made the *entire line* fail to match - not just the
# number. That silently dropped the whole row, including section headers,
# whose sub-rows then fell through to whatever section was previously
# active. Confirmed by tracing a real OCR failure on the "ATTACK" header.
# This version just grabs the first run of digits/commas/dots (+ optional %)
# after the label and ignores everything after it - a header's total can end
# up wrong if the number itself is garbled, but the header is still
# recognized and its sub-rows still attach to the right section, which
# matters far more than one wrong total.
_ROW_LINE = re.compile(r"^(.+?)\s+([\d][\d,\.]*%?)")


def _classify_label(label: str) -> tuple[str, str] | None:
    """Fuzzy-match against known sub-row and section vocabularies (handles OCR
    noise like "Lrew" for "Crew" or "Lrit vamage" for "Crit Damage"). Returns
    (kind, canonical_name) - kind is "subrow" or "section" - or None if this
    doesn't resemble anything known, meaning drop the line as unclassifiable
    noise rather than inventing a garbage section from it."""
    sub = difflib.get_close_matches(label, KNOWN_SUBROW_LABELS, n=1, cutoff=0.75)
    if sub:
        return "subrow", sub[0]
    sec = difflib.get_close_matches(label, KNOWN_SECTION_NAMES, n=1, cutoff=0.6)
    if sec:
        return "section", sec[0]
    return None


_TAB_BAR_NOISE = re.compile(r"^(Overview\s+Details|Overview|Details)\s*", re.IGNORECASE)


def _join_wrapped_lines(text: str) -> list[str]:
    """A section header that's too long to fit one line wraps (e.g. "Chance to
    inflict Major" / "Damage  65.00%"), splitting the header from its value
    across two OCR'd lines. Any line with no trailing number is a continuation
    of the next line, not its own row - join them before parsing rows.

    First strips "Overview"/"Details" tab-bar text that psm 6 sometimes prepends
    to the first content line (they're both text blocks close together
    vertically) - left in place, that noise would itself look like a
    no-trailing-number line and get wrongly joined onto real content below it.

    Also drops short all-lowercase-alpha lines: under psm 12 (sparse text,
    see read_attribute_details), each header row's dropdown chevron icon
    occasionally gets segmented as its own spurious garbage text block (seen
    live as "vw"/"Ww") rather than being absorbed into the row it belongs to -
    confirmed by inspecting the saved debug composite directly, not guessed.
    Left in place, one of these preceding the very first header ("HP") merges
    into its label and pushes the fuzzy-match ratio just below the
    classification cutoff, silently dropping that header. Every real label in
    this game starts with a capital letter (all-caps like HP/ATTACK, or
    Title-Case) so a short run of only lowercase letters can never be real
    content - safe to filter categorically rather than matching the exact
    misread string, which isn't guaranteed to repeat next time."""
    _ICON_GLYPH_NOISE = re.compile(r"^[a-z]{1,3}$")
    raw_lines = [_TAB_BAR_NOISE.sub("", l).strip() for l in text.splitlines()]
    raw_lines = [l for l in raw_lines if l and not _ICON_GLYPH_NOISE.match(l)]
    joined: list[str] = []
    buffer = ""
    for line in raw_lines:
        buffer = f"{buffer} {line}".strip() if buffer else line
        if re.search(r"[\d,\.]+%?\s*[^\d,.%]*$", buffer) and re.search(r"\d", buffer):
            joined.append(buffer)
            buffer = ""
    if buffer:
        joined.append(buffer)
    return joined


def _parse(text: str, data: dict[str, dict[str, str]], section: list[str | None]) -> None:
    for line in _join_wrapped_lines(text):
        m = _ROW_LINE.match(line)
        if not m:
            continue
        label, value = m.group(1).strip(), m.group(2)

        classified = _classify_label(label)
        if classified is None:
            log.debug("Dropped unrecognized label %r (value %r)", label, value)
            continue  # unrecognized text, likely a mistimed/blurred capture - drop it
        kind, canonical = classified
        if kind == "subrow":
            if section[0]:
                # Confirmed by the user: for ATK/DEF/INT, "Components" appears
                # TWICE under one section - once as a base value (e.g. 11,309
                # raw component count) and once as a separate bonus percentage
                # (e.g. 20% for having a complete set). Keying only on the
                # label would silently overwrite one with the other. Suffix
                # percentage rows so both survive as distinct entries; a label
                # that only ever appears one way just ends up with one key.
                key = f"{canonical} %" if value.endswith("%") else canonical
                if key in data[section[0]] and data[section[0]][key] != value:
                    # A sub-row label repeating WITH A DIFFERENT VALUE within
                    # what's supposedly still the same section is a strong
                    # signal that a section header was silently dropped by
                    # OCR in between (this composite is tall enough that
                    # Tesseract occasionally loses a whole header line even
                    # though the exact same crop reads fine in isolation -
                    # confirmed by direct comparison). Confirmed live: a
                    # dropped "ATTACK" header let its own "Champions"/"Crew"
                    # rows silently overwrite HP's real values with this
                    # exact symptom. We can't recover the missing header's
                    # name, but we can stop attributing further rows to the
                    # wrong section - dropping is far safer than silently
                    # corrupting one.
                    #
                    # A repeat with the SAME value is just this row being
                    # OCR'd again from overlapping capture regions - harmless,
                    # ignore rather than treat as a section boundary.
                    log.warning(
                        "%s: %r changed %r -> %r within same section - likely a "
                        "dropped header, abandoning this section", section[0], key,
                        data[section[0]][key], value,
                    )
                    section[0] = None
                    continue
                if key in data[section[0]]:
                    continue
                data[section[0]][key] = value
        else:
            data.setdefault(canonical, {})["_total"] = value
            section[0] = canonical


def _parse_number(value: str) -> tuple[float, bool]:
    """Returns (number, is_percentage)."""
    is_pct = value.endswith("%")
    return float(value.rstrip("%").replace(",", "")), is_pct


def validate_sections(data: dict[str, dict[str, str]]) -> dict[str, dict]:
    """Sanity-checks each section's total against its sub-rows, confirmed by
    the user directly against the game's own numbers: total = sum(base-value
    sub-rows) * (1 + sum(percentage sub-rows) / 100) - e.g. Load: (300 + 300)
    * (1 + (65 + 18) / 100) = 1,098, matching the captured total exactly.

    For sections whose own total is itself a percentage (Crit Rate, Damage
    Bonus, ...), there's no base component - the total is just the straight
    sum of its percentage sub-rows instead (also confirmed against captures).

    This catches incomplete/corrupted captures mathematically instead of by
    eyeballing whether a section's field set "looks right" - which is not a
    valid signal on its own, since different sections legitimately have
    different subsets of modifiers (see KNOWN_SUBROW_LABELS note above).
    Returns {section: {"expected": float, "actual": float, "valid": bool}} -
    sections with only a "_total" and no captured sub-rows are skipped, since
    there's nothing to check them against."""
    results = {}
    for section, fields in data.items():
        total_str = fields.get("_total")
        if total_str is None:
            continue
        total, total_is_pct = _parse_number(total_str)

        base_sum = 0.0
        pct_sum = 0.0
        for label, value in fields.items():
            if label in ("_total", "_total_healed"):
                continue
            num, is_pct = _parse_number(value)
            if is_pct:
                pct_sum += num
            else:
                base_sum += num

        if base_sum == 0 and pct_sum == 0:
            continue  # no sub-rows captured for this section - nothing to check

        expected = (base_sum + pct_sum) if total_is_pct else base_sum * (1 + pct_sum / 100)
        tolerance = max(1.0, total * 0.005)  # displayed percentages are rounded to 2dp
        valid = abs(expected - total) <= tolerance
        if not valid:
            log.debug("%s: total %s doesn't match sub-rows (expected %.2f)", section, total_str, expected)
        results[section] = {"expected": expected, "actual": total, "valid": valid}
    return results


def heal_totals(data: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """Section header totals are occasionally misread by OCR even when every
    one of that section's sub-rows was read correctly - confirmed on two
    independent sections in the same run by inspecting the actual composite
    image: "662" read as "620" (a plain digit substitution), and "23,725"
    read as "23,/25" then truncated to "23," by _ROW_LINE stopping at the
    stray "/". Since the total is mathematically determined by the sub-rows
    (see validate_sections), replace it with that computed value whenever
    they disagree beyond tolerance and sub-rows were actually captured -
    trusting several independently-read numbers over one already known to
    be wrong.

    This assumes the sub-rows themselves are complete and correct, which
    won't always hold (a missing/misread sub-row would also fail
    validation) - so a healed section is marked with "_total_healed": "true"
    rather than silently overwritten, so a caller can still tell the
    original OCR'd total didn't match if that distinction matters to them."""
    validation = validate_sections(data)
    for section, result in validation.items():
        if result["valid"]:
            continue
        fields = data[section]
        expected = result["expected"]
        is_pct = fields["_total"].endswith("%")
        healed = f"{expected:.2f}%" if is_pct else f"{round(expected):,}"
        log.info("%s: healed total %r -> %r from sub-rows", section, fields["_total"], healed)
        fields["_total"] = healed
        fields["_total_healed"] = "true"
    return data


def _stitch_full_table(hwnd, layout) -> Image.Image:
    """Scrolls through the whole list via the shared scroll_stitch helper -
    see that module for why image stitching (not cross-capture text
    merging) is used."""
    return stitch_scrolled_region(
        hwnd, layout.table_box, layout.drag_from, layout.drag_to,
        layout.expected_scroll_offset, static_header_height=layout.table_tab_bar_height,
        max_scrolls=MAX_SCROLLS,
    )


def read_attribute_details(hwnd, name) -> dict[str, dict[str, str]]:
    log.info("%s: collecting Attribute Details", name)
    layout = get_layout(hwnd)
    click (hwnd, *layout.overview_tab)
    time.sleep(0.2)
    click(hwnd, *layout.hamburger_icon)
    time.sleep(0.2)
    click(hwnd, *layout.details_tab)
    time.sleep(0.2)

    composite = _stitch_full_table(hwnd, layout)
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    composite.save(DEBUG_DIR / "_debug_attribute_stitch.png")
    log.debug("Stitched composite: %dx%d", composite.width, composite.height)

    # psm 6 was silently dropping whole section-header lines (e.g. "HP
    # 1,029,897") once the composite grew past a couple hundred px tall, even
    # though the exact same crop OCR'd correctly in isolation - psm 4 fixed
    # that at the time, but on a full multi-section composite (2700+px tall,
    # confirmed via the saved debug composite) psm 4 regressed to the same
    # failure: it dropped every section header except the very first,
    # confirmed by comparing psm 4/6 output against psm 12 on the identical
    # saved image - the header text wasn't misread, it just wasn't detected
    # as text at all (each header row sits in its own visually boxed/shaded
    # region, which apparently confuses layout modes that assume a uniform
    # text column). psm 12 (sparse text) treats each visual block
    # independently and recovered every header on that same comparison.
    text = pytesseract.image_to_string(preprocess(composite, upscale=2), config="--psm 12").strip()
    (DEBUG_DIR / "_debug_attribute_ocr.txt").write_text(text, encoding="utf-8")

    data: dict[str, dict[str, str]] = {}
    section: list[str | None] = [None]  # no cross-capture concern - this is one linear pass
    _parse(text, data, section)
    result = heal_totals(data)
    log.info("%s: read %d section(s): %s", name, len(result), list(result))
    return result
