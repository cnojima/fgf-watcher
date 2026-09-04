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
cross-capture merging step, cross-capture misattribution isn't possible.

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
import re
import time

import numpy as np
from PIL import Image

from capture import screenshot_region
from input_control import click, drag
from ocr import preprocess, pytesseract

HAMBURGER_ICON = (1645, 1385)  # on the ship detail view (Overview tab)
DETAILS_TAB = (1475, 410)
# Bottom was originally 1060, then 1150 - both times widened by eyeballing
# position on the full downscaled screenshot, and both times still wrong: at
# the list's true max-scroll rest position the last section's content
# ("Chance to inflict Major Damage" + its Level/Technology sub-rows) actually
# extends to y=1290, with the modal's own visible border at y=1335. 1150 was
# cutting off "Level"/"Technology" entirely, not just trimming their margin.
# This value came from zoom.py's 10px grid against calibration_raw.png, not
# another eyeball guess - see CLAUDE.md on why that distinction matters here.
TABLE_BOX = (650, 350, 1650, 1330)
# Drag from a lower point to a higher one to scroll the list down (touch-style
# swipe-up), both inside the table area and away from row edges/the header row.
# The exact distance matters much less now than it did before image
# stitching: _content_offset() measures how far the content actually moved
# from real pixels rather than trusting this number, so it only needs to be
# a reasonable seed for that search (see EXPECTED_SCROLL_OFFSET) - it no
# longer has to simultaneously satisfy "enough overlap for OCR redundancy"
# and "not so much overlap that stale content resurfaces," since there's no
# cross-capture text merging left for that tradeoff to apply to.
DRAG_FROM = (1000, 900)
DRAG_TO = (1000, 550)
EXPECTED_SCROLL_OFFSET = DRAG_FROM[1] - DRAG_TO[1]
MAX_SCROLLS = 45  # smaller per-drag distance means more scrolls needed to reach the bottom

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
    no-trailing-number line and get wrongly joined onto real content below it."""
    raw_lines = [_TAB_BAR_NOISE.sub("", l).strip() for l in text.splitlines()]
    raw_lines = [l for l in raw_lines if l]
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
        results[section] = {
            "expected": expected,
            "actual": total,
            "valid": abs(expected - total) <= tolerance,
        }
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
        fields["_total"] = f"{expected:.2f}%" if is_pct else f"{round(expected):,}"
        fields["_total_healed"] = "true"
    return data


STRIP_Y = 180  # skip past the static "Overview/Details" tab bar at the top of TABLE_BOX


def _content_offset(prev_img: Image.Image, curr_img: Image.Image,
                     expected: int = EXPECTED_SCROLL_OFFSET, margin: int = 150) -> int:
    """How far curr_img's content has scrolled down relative to prev_img, in
    pixels - found by matching actual pixel content (a thin strip against a
    sliding window of prev_img) rather than trusting the drag gesture
    produced exactly the requested distance, which touch-scroll physics
    doesn't guarantee. Searches a margin around the requested drag distance
    rather than the whole image, since the true answer is always close to
    it - a full search isn't needed and is slower.

    The strip is sampled starting at STRIP_Y, not the very top of the crop:
    TABLE_BOX's top ~150px is the "Overview/Details" tab bar, which is fixed
    UI chrome that never scrolls - comparing that against itself always
    scored a perfect match at offset=0 regardless of how far the actual list
    content below it had moved, making this function report "no movement"
    on every call even when the list had clearly scrolled several sections
    down. Confirmed by saving and inspecting the actual crop, not guessed."""
    prev = np.asarray(prev_img.convert("L"), dtype=np.int32)
    curr = np.asarray(curr_img.convert("L"), dtype=np.int32)
    strip_h = 80
    curr_strip = curr[STRIP_Y:STRIP_Y + strip_h, :]

    # Always search from 0, not expected-margin: at the true scroll-bottom
    # the frames are identical and the real answer is 0, which a window
    # centered on `expected` would never even consider - that's exactly what
    # happened the first time this ran (stall never detected, scrolled all
    # the way to MAX_SCROLLS, produced a 17,000px-tall composite Tesseract
    # then refused to process at all).
    lo = 0
    hi = min(prev.shape[0] - STRIP_Y - strip_h, expected + margin)
    best_offset, best_score = expected, None
    for offset in range(lo, hi + 1):
        score = np.sum((prev[STRIP_Y + offset:STRIP_Y + offset + strip_h, :] - curr_strip) ** 2)
        if best_score is None or score < best_score:
            best_score = score
            best_offset = offset
    return best_offset


def _stitch_full_table(hwnd) -> Image.Image:
    """Scrolls through the whole list, splicing only the genuinely new bottom
    slice of each capture (per _content_offset) onto one growing composite
    image, so the whole table ends up as a single seamless image with each
    row appearing exactly once - no OCR text merging step needed at all."""
    frame = screenshot_region(hwnd, TABLE_BOX)
    parts = [frame]

    stalls = 0
    for _ in range(MAX_SCROLLS):
        drag(hwnd, *DRAG_FROM, *DRAG_TO)
        time.sleep(0.7)  # let scroll momentum/animation fully settle before capturing
        next_frame = screenshot_region(hwnd, TABLE_BOX)
        offset = _content_offset(frame, next_frame)
        if offset <= 5:
            stalls += 1
            # Same reasoning as the old text-based stall check: one
            # negligible-movement reading isn't reliable proof we've hit the
            # true bottom on its own. Two in a row is a much stronger signal.
            if stalls >= 2:
                break
        else:
            stalls = 0
            parts.append(next_frame.crop((0, frame.height - offset, next_frame.width, next_frame.height)))
        frame = next_frame

    composite = Image.new("RGB", (frame.width, sum(p.height for p in parts)))
    y = 0
    for part in parts:
        composite.paste(part, (0, y))
        y += part.height
    return composite


def read_attribute_details(hwnd) -> dict[str, dict[str, str]]:
    click(hwnd, *HAMBURGER_ICON)
    time.sleep(0.6)
    click(hwnd, *DETAILS_TAB)
    time.sleep(0.6)

    composite = _stitch_full_table(hwnd)
    text = pytesseract.image_to_string(preprocess(composite, upscale=2), config="--psm 6").strip()

    data: dict[str, dict[str, str]] = {}
    section: list[str | None] = [None]  # no cross-capture concern - this is one linear pass
    _parse(text, data, section)
    return heal_totals(data)
