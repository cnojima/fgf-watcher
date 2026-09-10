"""Classify a small icon crop by matching it against a library of reference
images - for pictographic game UI elements that OCR can't read at all (no
text in them to recognize), unlike the stylized-font cases ocr_easy.py exists
for. Same underlying idea as profiles/fingerprints.py (this game's UI is
pixel-exact and renders identically every time, so a saved reference image
reliably matches a live crop of the same element) extended from a couple of
sample pixel points to a whole small image, since these icons vary by shape
as well as color.

Reference icons live under icons/<category>/<name>.png (e.g.
icons/elements/kinetic.png). Add a new category directory for a new kind of
icon (rarity, class, ...), or a new file within one to teach it a new icon of
an existing kind - no code change needed either way.
"""
import logging
from pathlib import Path

import numpy as np
from PIL import Image

log = logging.getLogger(__name__)

ICONS_DIR = Path(__file__).resolve().parent / "icons"

# Every icon (reference and live crop alike) is resized to this before
# comparing, so reference images captured at a different crop size than the
# live UI box still compare correctly. Kept square: known references so far
# (kinetic 57x56, beam 34x34) are roughly square - if a future icon's real
# aspect ratio is meaningfully non-square, resizing to a square here would
# distort it, so re-examine this if match quality is ever poor specifically
# for a tall/wide icon (e.g. ion at 58x67 vs. the others being ~1:1).
_MATCH_SIZE = (48, 48)

_cache: dict[str, dict[str, np.ndarray]] = {}


def _autocrop_to_content(img: Image.Image, tolerance: int = 30) -> Image.Image:
    """Trims a roughly-uniform background border down to the bounding box of
    the actual icon content, so reference PNGs and live UI crops compare
    correctly even when cropped with different amounts of padding around the
    icon - confirmed necessary live: a user-supplied reference (e.g. 34x34)
    and a live crop of the same badge slot (30x30) scored as barely-not-a-
    match before this, purely from the resize-to-canonical-size stretching
    each crop's padding by a different amount, not any real visual
    difference (widening the live box's padding to match monotonically
    improved the score, confirming padding - not content - was the cause).

    Background color is sampled from the four corners (each icon here sits
    on a roughly solid color background, not corner-to-corner content), and
    any pixel far enough from it in any channel is "content"."""
    arr = np.asarray(img, dtype=np.int32)
    h, w = arr.shape[:2]
    corners = np.array([arr[0, 0], arr[0, w - 1], arr[h - 1, 0], arr[h - 1, w - 1]])
    bg = corners.mean(axis=0)
    diff = np.abs(arr - bg).max(axis=2)
    mask = diff > tolerance
    if not mask.any():
        return img  # solid image, e.g. a blank/unrendered slot - nothing to crop to
    ys, xs = np.where(mask)
    box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    return img.crop(box)


def _load(path: Path) -> np.ndarray:
    img = _autocrop_to_content(Image.open(path).convert("RGB")).resize(_MATCH_SIZE, Image.LANCZOS)
    return np.asarray(img, dtype=np.int32)


def _get_category(category: str) -> dict[str, np.ndarray]:
    if category not in _cache:
        category_dir = ICONS_DIR / category
        refs = {p.stem: _load(p) for p in sorted(category_dir.glob("*.png"))}
        if not refs:
            raise RuntimeError(f"No reference icons found in {category_dir}")
        log.debug("Loaded %d reference icon(s) for category %r: %s", len(refs), category, list(refs))
        _cache[category] = refs
    return _cache[category]


def match_icon(crop: Image.Image, category: str, max_mse: float = 3000.0) -> str | None:
    """Returns the name of the closest-matching reference icon in `category`,
    or None if even the best match is too far off to trust - an
    uncalibrated/unrecognized icon should come back as "don't know" rather
    than silently picking the least-wrong of several bad options.

    Default threshold set from real measurements, not guessed: live captures
    of the "elements" category's badge box (profiles/ui_layout.py's
    element_icon_box) scored ~680 (Demerzel, Beam) and ~934 (Gram, Kinetic)
    against their correct reference icon - confirmed correct against each
    ship's actual on-screen badge, not assumed. The residual gap from a
    perfect 0 is inherent noise between a static reference PNG and an actual
    screen capture (compression, anti-aliasing); _autocrop_to_content already
    removes the larger source of error (inconsistent padding). The nearest
    *wrong*-icon score seen live is ~3751 - 3000 sits with comfortable margin
    on both sides of that gap. Re-measure if a new icon in a category is ever
    visually close to another one.

    A wrong element_icon_box (clipping the badge, even by a few px on one
    edge) is enough to push a real match's score well past this threshold
    without changing which icon looks closest by eye - confirmed live: an
    earlier, slightly-too-small box scored the correct icon at 4864 (would
    have wrongly read as "no match"). If real captures start scoring high
    across the board, re-check the box against a fresh zoom before touching
    this threshold."""
    refs = _get_category(category)
    query_img = _autocrop_to_content(crop.convert("RGB")).resize(_MATCH_SIZE, Image.LANCZOS)
    query = np.asarray(query_img, dtype=np.int32)

    scores = {name: float(np.mean((query - ref) ** 2)) for name, ref in refs.items()}
    best_name = min(scores, key=scores.get)
    best_score = scores[best_name]
    log.debug("match_icon(%s): scores=%s", category, {k: round(v, 1) for k, v in scores.items()})

    if best_score > max_mse:
        log.warning(
            "match_icon(%s): no confident match (best %r score=%.1f > threshold %.1f)",
            category, best_name, best_score, max_mse,
        )
        return None
    return best_name
