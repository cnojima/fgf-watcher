"""General-purpose text OCR via PaddleOCR's stock (not fine-tuned) English
recognition model - replaces both ocr.py (Tesseract) and ocr_easy.py
(EasyOCR) for single-line/short-text crops.

Confirmed directly this session, not assumed: the stock `en_PP-OCRv4_mobile_rec`
recognizer (same base model orange_kid_ocr.py fine-tuned) scored 99/100 on
the orange_kid digit-badge validation set with *zero* fine-tuning - the exact
font Tesseract reads as "pure garbage" and EasyOCR needed a hand-built
confusion table for - and correctly read a real captured stylized weapon
title. See the OCR-consolidation plan for the full investigation. This
justifies a general-purpose reader built on PaddleOCR alone rather than
picking between three engines per field.

This is recognition-only (no text detection) - same constraint as
orange_kid_ocr.py: pass one pre-cropped single-line region per call, not a
multi-line block. Multi-line free-text blocks (ability descriptions,
attribute tables) need PaddleOCR's full detection+recognition pipeline
instead - a separate, not-yet-built module (see the plan's Phase 2).
"""
import logging

import numpy as np
from PIL import Image

log = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        log.info("Loading PaddleOCR text recognition model (first use - a few seconds)")
        from paddlex import create_model
        # paddlex's own __init__ calls setup_logging() at import time, which
        # sets its "paddlex" logger to INFO regardless of this app's own
        # logging config - must be quieted after the import, not before, or
        # this line has no effect (see setup_logging()'s unconditional
        # logger.setLevel(INFO) call). Silences its noisy per-call "Creating
        # model: (...)" / "Model files already exist..." INFO lines.
        logging.getLogger("paddlex").setLevel(logging.WARNING)
        _model = create_model(model_name="en_PP-OCRv4_mobile_rec")
    return _model


def read_text(image: Image.Image) -> str:
    """Reads a single-line/short-text crop (e.g. a name, title, badge label,
    or button) and returns the recognized text, or "" if nothing was read."""
    model = _get_model()
    # BGR conversion matches this model's own DecodeImage/img_mode: BGR
    # convention - see orange_kid_ocr.py's read_level for the same reasoning.
    array = np.array(image.convert("RGB"))[:, :, ::-1]
    result = next(iter(model.predict(array)))
    text, score = result["rec_text"].strip(), result["rec_score"]
    log.debug("OCR (paddle): %r (score=%.3f)", text, score)
    return text
