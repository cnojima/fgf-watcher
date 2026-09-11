"""Reads a multi-line/multi-region block of text (a stat table, a scrolled
list, free-form paragraph text) via PaddleOCR's full detection+recognition
pipeline - unlike paddle_ocr.py's recognition-only read_text(), which expects
one pre-cropped single-line region per call and can't segment a block into
lines itself.

Confirmed directly this session against a real captured ship-attribute table
(data/_debug_attribute_stitch.png, ~1000x5567px): every row correctly
detected and read at ~100% confidence end to end, including a title-case
multi-word header that visually line-wraps ("Chance to inflict Major" /
"Damage") - the detector splits it the same way the screen renders it, which
attribute_details.py's existing _join_wrapped_lines() already re-joins.

Two things needed to get there, not assumed:
- `enable_mkldnn=False` - the default CPU oneDNN backend crashes on this
  Paddle version/machine with `NotImplementedError:
  ConvertPirAttribute2RuntimeAttribute...` for ANY detection model tried.
- Reconstructing row-level text from the detector's individual (often
  column-separated, e.g. "HP" ... "558,760") boxes, since a recognition
  pipeline naturally returns one text per detected region, not one per
  visual row. Groups boxes into rows by vertical (y) proximity, orders each
  row left-to-right, and joins with a space - producing the same "label
  value" per-line shape Tesseract's psm 6/12 output already had, so
  attribute_details.py's whole parsing pipeline (_join_wrapped_lines,
  _classify_label, _parse, validate_sections, heal_totals) needed zero
  changes, just a different text source.
"""
import logging

import numpy as np
from PIL import Image

log = logging.getLogger(__name__)

_pipeline = None


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        log.info("Loading PaddleOCR detection+recognition pipeline (first use - a few seconds)")
        from paddleocr import PaddleOCR
        _pipeline = PaddleOCR(
            lang="en",
            use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False,
            enable_mkldnn=False,
        )
    return _pipeline


def _group_into_rows(boxes: list, texts: list) -> list[str]:
    """boxes are [x1, y1, x2, y2]. Buckets by vertical proximity (row center
    within 0.6x the box's own height of an existing row's center) rather
    than a fixed pixel tolerance, since row height varies with font size
    across different UI contexts."""
    items = sorted(zip(boxes, texts), key=lambda t: (t[0][1] + t[0][3]) / 2)
    rows: list[dict] = []
    for box, text in items:
        y_center = (box[1] + box[3]) / 2
        height = box[3] - box[1]
        for row in rows:
            if abs(row["y"] - y_center) < height * 0.6:
                row["items"].append((box[0], text))
                break
        else:
            rows.append({"y": y_center, "items": [(box[0], text)]})
    return [" ".join(text for _, text in sorted(row["items"], key=lambda t: t[0])) for row in rows]


def read_text_block(image: Image.Image) -> str:
    """Reads a multi-line region and returns it as a text blob, one physical
    row per line - the same shape Tesseract's psm 6/11/12 block modes
    produced, so existing regex-based row parsers work unchanged."""
    pipeline = _get_pipeline()
    array = np.array(image.convert("RGB"))[:, :, ::-1]
    result = next(iter(pipeline.predict(array)))
    rows = _group_into_rows(list(result["rec_boxes"]), result["rec_texts"])
    text = "\n".join(rows)
    log.debug("OCR (paddle block): %d row(s)", len(rows))
    return text
