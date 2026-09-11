"""Reads game's custom "orange kid" font (large level-badge digits - champion
level, weapon level) via a PaddleOCR recognition model fine-tuned on that
exact font (see ocr_training/WINDOWS_GPU_HANDOFF.md and
ocr_training/orange_kid_rec.yaml for how it was trained, and
ocr_training/generate_orange_kid_data.py's docstring for why: Tesseract fails
on this font uniformly regardless of preprocessing, and EasyOCR's
letter/digit confusions - "121" -> "Izi" - previously needed a hand-built
confusion table (see git history) that this model replaces outright, not
just papers over).

Loading paddlex/paddle takes a few seconds, so - same lazy-singleton pattern
as ocr_easy.py's EasyOCR reader - the model loads once on first use, not per
call. Only plain-CPU `paddlepaddle` + `paddleocr` are needed for this (both
listed explicitly in requirements.txt - neither pulls the other in); the
heavier paddlenlp/datasets/albumentations/etc. stack in
ocr_training/.venv-paddle is training-only and irrelevant here (confirmed by
testing this exact model in a clean venv with just those two installed).
"""
import logging
from pathlib import Path

import numpy as np
from PIL import Image

log = logging.getLogger(__name__)

_MODEL_DIR = Path(__file__).resolve().parent.parent / "ocr_training" / "orange_kid_model"

_model = None


def _get_model():
    global _model
    if _model is None:
        log.info("Loading orange_kid OCR model (first use - a few seconds)")
        from paddlex import create_model
        _model = create_model(model_name="en_PP-OCRv4_mobile_rec", model_dir=str(_MODEL_DIR))
    return _model


def read_level(image: Image.Image) -> int | None:
    """Reads a level-badge crop (digits only, e.g. ChampionLayout.level_box /
    weapon_level_box) and returns the integer value, or None if nothing was
    read."""
    model = _get_model()
    # predict() only accepts a file path (str) or a numpy array - not a PIL
    # Image. Channel order matters for a raw array (unlike a file path,
    # which goes through the same DecodeImage/cv2 BGR convention the model's
    # own inference.yml declares - img_mode: BGR - so this converts to match
    # rather than passing PIL's native RGB order). Not distinguishable on a
    # near-grayscale test crop (both orders read it correctly) - this
    # follows the training config's stated convention, not an empirical
    # RGB-vs-BGR comparison.
    array = np.array(image.convert("RGB"))[:, :, ::-1]
    result = next(iter(model.predict(array)))
    text, score = result["rec_text"], result["rec_score"]
    log.debug("OCR (orange_kid): %r (score=%.3f)", text, score)
    return int(text) if text.isdigit() else None
