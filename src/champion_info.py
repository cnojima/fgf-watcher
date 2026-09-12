"""Read a champion's Info tab: name, title, quality, element, champion
type, level, and power.

Quality ("LEGENDARY"/"EPIC") is plain OCR-able text - no icon matching
needed, unlike element and type which are icon-only badges here (their
plain-text equivalents only show up on the weapon detail page - see
champion_weapon.py).

Element reuses the same icons/elements/ library built for flagships -
confirmed live that champions render the identical kinetic/beam/ion badge
art.

Champion type is a new icons/champion_types/ library, self-derived from
live captures rather than hand-supplied: the weapon detail page happens to
show the same icon next to a plain-text label ("ATTACK"), so a crop from
that page could be paired with ground truth directly. Only "attack" is
confirmed this way so far; a second icon (a green gear/cog glyph, seen on
an unweaponed champion with no text label available to confirm it) is
saved as "support_unconfirmed.png" - a guess, not a confirmed reading, per
the same "don't invent unconfirmed data" precedent as
attribute_details.py's KNOWN_SUBROW_LABELS "Construction" entry. Expect
icon_match to return None (logged as a warning) for any other type until
more reference icons are added.
"""
import difflib
import logging
import re

import orange_kid_ocr
import paddle_ocr
from capture import screenshot_region
from icon_match import match_icon
from profiles.champion_layout import ChampionLayout
from profiles.notifications import dismiss_if_present

log = logging.getLogger(__name__)

# Confirmed by the user: every champion's quality is one of exactly these
# two values - a closed vocabulary, so fuzzy-matched the same way
# champion_weapon.py matches element/type words rather than trusted as
# free-text OCR. A raw OCR misread (e.g. a stray leading character) no
# longer needs perfect text, just something close enough to one of these.
_QUALITIES = ("legendary", "epic")

# name_box's stylized condensed font (see the docstring on read_info's `name`
# line) hallucinates trailing garbage past the real text and drops spaces
# between words often enough that raw OCR output can't be trusted as-is -
# confirmed live across a real roster capture, and confirmed NOT a cropping
# bug first (per CLAUDE.md's "capture evidence before tuning" bar - every
# crop behind these reads was visibly clean and correctly bounded):
# "ZORADOMINI" (dropped space), "LILY-" (hallucinated trailing dash, and a
# stray lowercase letter mid-word), "KILLER BEE ." / "COCOONTTO" (trailing
# noise/repeats), "JODIE BEARTA" (extra trailing letter, dropped accent).
# Corrected by fuzzy-matching against a whitelist of names already confirmed
# correct by the user - same closed-vocabulary approach as _match_quality
# above and champion_weapon._find_keyword, except deliberately narrow (only
# entries actually confirmed, not every name seen in a capture) per the
# "don't invent unconfirmed data" precedent in attribute_details.py's
# KNOWN_SUBROW_LABELS docstring. Grows one confirmed name at a time; any
# name not yet in it just passes through unchanged (open vocabulary).
_KNOWN_NAMES = ("ZORA DOMINI", "LILY", "KILLER BEE", "COCOON", "JODIE BEART")


def _match_known_name(text: str) -> str:
    if not text:
        return text
    match = difflib.get_close_matches(text.upper(), _KNOWN_NAMES, n=1, cutoff=0.75)
    return match[0] if match else text


def _read_level(hwnd, layout: ChampionLayout) -> int | None:
    # Both Tesseract and EasyOCR struggle with this octagon-badge font (see
    # ocr_training/generate_orange_kid_data.py's docstring) - EasyOCR needed
    # a hand-built letter/digit confusion table as a workaround. Replaced by
    # a PaddleOCR model fine-tuned on the game's actual extracted font file,
    # confirmed live against real captures (see ocr_training's session notes).
    return orange_kid_ocr.read_level(screenshot_region(hwnd, layout.level_box))


def _clean_leading_noise(text: str) -> str:
    return re.sub(r"^[^A-Za-z0-9]*[A-Za-z]{0,2}\s+(?=[A-Z0-9])", "", text.strip())


def _normalize_power(text: str) -> str:
    # Confirmed against a real capture: paddle_ocr occasionally misreads
    # this field's comma thousands-separator as a period (e.g. "993,672" ->
    # "993.672"). Power is always a plain integer count here (never a true
    # decimal), so any "." sitting between digit groups is safe to normalize
    # back to ",".
    return re.sub(r"(?<=\d)\.(?=\d{3}(?:\D|$))", ",", text)


def _match_quality(text: str) -> str | None:
    for word in re.findall(r"[A-Za-z]+", text.upper()):
        match = difflib.get_close_matches(word, [q.upper() for q in _QUALITIES], n=1, cutoff=0.7)
        if match:
            return match[0].lower()
    return None


def read_info(hwnd, layout: ChampionLayout) -> dict:
    """Assumes the champion's Info tab is currently showing."""
    # The global notification banner (profiles/notifications.py) can cover
    # name_box/title_box right as this tab opens - confirmed live corrupting
    # a real champion name. Dismiss it before reading anything.
    dismiss_if_present(hwnd)

    # Tesseract misreads this stylized font the same way it does the ship
    # name/"FLAGSHIP" title (see CLAUDE.md) - confirmed live across a full
    # roster collection: "DOUG ROCKWELL" -> "'Dove ROCKWE!", "KILLER BEE" ->
    # "KILLER BEF", plausible near-misses rather than random noise, the
    # signature of a font/engine mismatch rather than a timing issue. Now
    # reads via paddle_ocr (see the OCR-consolidation plan) rather than
    # EasyOCR - PaddleOCR's recognizer read this exact font correctly on a
    # different real crop (a weapon title) without any fine-tuning; verify
    # against a real champion name/title crop before trusting this in
    # production, same as every other field migrated this session.
    name = _match_known_name(paddle_ocr.read_text(screenshot_region(hwnd, layout.name_box)))
    title = paddle_ocr.read_text(screenshot_region(hwnd, layout.title_box))
    quality = _match_quality(paddle_ocr.read_text(screenshot_region(hwnd, layout.quality_box)))
    element = match_icon(screenshot_region(hwnd, layout.element_icon_box), "elements")
    champion_type = match_icon(screenshot_region(hwnd, layout.type_icon_box), "champion_types")
    level = _read_level(hwnd, layout)
    power = _normalize_power(_clean_leading_noise(paddle_ocr.read_text(screenshot_region(hwnd, layout.power_box))))

    log.info(
        "%s (%s): quality=%s element=%s type=%s level=%s power=%s",
        name, title, quality, element, champion_type, level, power,
    )
    return {
        "name": name,
        "title": title,
        "quality": quality,
        "element": element,
        "type": champion_type,
        "level": level,
        "power": power,
    }
