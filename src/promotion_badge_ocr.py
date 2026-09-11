"""Reads the ship Promote tab's current-level badge icon (a differently
shaped/colored icon per tier - see ocr_training/generate_promotion_badge_data.py)
via a PaddleOCR recognition model fine-tuned on real captures of it.

Stock PaddleOCR (paddle_ocr.py) consistently misread a real level-I capture
as a bare "A" across 1x-4x upscaling - a genuine failure on this icon shape,
not a resolution issue (see the OCR-consolidation plan and
promotion_details.py's docstring). This fine-tuned model fixes that, but has
its own known blind spot: level 0's badge (a muted star/cross glyph, no
numeral) gets confidently misread as "I" by the CTC recognizer itself,
confirmed on 0/30 held-out validation samples despite the training run's own
self-reported metric claiming ~100% accuracy throughout (that metric turned
out to silently mishandle empty-ground-truth rows - not the first time in
this project a self-reported OCR training metric didn't match reality; see
ocr_training/'s session notes on the orange_kid run's own broken first-pass
eval). A CTC-based text recognizer isn't well-suited to outputting "nothing"
for an icon that's structurally similar to text it does know - it will
confidently guess a character rather than abstain.

So level 0 is detected with a plain pixel/structural check instead, same
"check a distinguishing signal before trusting OCR" pattern already used
elsewhere in this codebase (e.g. champion_weapon.has_weapon_equipped's
pixel fingerprint, promotion_details._is_maxed's button-text check): the
numeral badges (I-V) all have a bright horizontal serif bar near the top of
the glyph, while level 0's star glyph doesn't - measured directly against
all 6 real captures, level 0 sits at mean brightness ~75 in that band vs.
~104-155 for every numeral, a wide, comfortable margin. Confirmed on the
one real level-0 capture available; like any single-example fingerprint in
this codebase (see weapon_badge_empty_fingerprint's history), a second
quality-tier theme could in principle sit differently - re-verify against a
live capture if this ever misfires.
"""
import logging
from pathlib import Path

import numpy as np
from PIL import Image

log = logging.getLogger(__name__)

_MODEL_DIR = Path(__file__).resolve().parent.parent / "ocr_training" / "promotion_badge_model"

# [y_start, y_end, x_start, x_end] within a promotion_badge_box crop,
# proportional to the crop's own size (not fixed pixels) so this survives a
# differently-sized crop than the 115x85px one it was measured against.
_SERIF_BAND = (0.235, 0.39, 0.35, 0.66)
_EMPTY_BRIGHTNESS_THRESHOLD = 90  # empty~75 vs numerals 104-155, see module docstring

_model = None


def _get_model():
    global _model
    if _model is None:
        log.info("Loading promotion badge OCR model (first use - a few seconds)")
        from paddlex import create_model
        _model = create_model(model_name="en_PP-OCRv4_mobile_rec", model_dir=str(_MODEL_DIR))
    return _model


def _is_unpromoted(image: Image.Image) -> bool:
    gray = np.array(image.convert("L"))
    h, w = gray.shape
    y0, y1, x0, x1 = _SERIF_BAND
    band = gray[int(h * y0):int(h * y1), int(w * x0):int(w * x1)]
    brightness = band.mean()
    log.debug("Promotion badge serif-band brightness: %.1f", brightness)
    return brightness < _EMPTY_BRIGHTNESS_THRESHOLD


def read_promotion_badge(image: Image.Image) -> str:
    """Returns the badge's Roman numeral ("I".."V"), or "" for level 0's
    non-numeral glyph. Never returns anything outside {"", "I", "II",
    "III", "IV", "V"} - the model's own character dict is just "I"/"V"."""
    if _is_unpromoted(image):
        return ""
    model = _get_model()
    array = np.array(image.convert("RGB"))[:, :, ::-1]
    result = next(iter(model.predict(array)))
    text, score = result["rec_text"], result["rec_score"]
    log.debug("OCR (promotion badge): %r (score=%.3f)", text, score)
    return text
