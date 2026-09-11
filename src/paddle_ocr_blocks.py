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
  visual row. Groups boxes into rows by Y-range *overlap* (see
  _cluster_by_overlap) rather than distance-to-a-fixed-point - the latter
  looked fine on this module's original ship-attribute-table test case but
  broke, confirmed live, on a weapon-stats table with a wrapped 2-line
  label ("Kinetic DMG Advantage" / "Boost"): the wrapped continuation word
  got attached to the *next* row instead of its own, corrupting both rows'
  data ("Boost Formation ATK Bonus" as one label). Orders each row
  left-to-right (by column, then top-to-bottom within a column) and joins
  with a space, producing the same "label value" per-line shape Tesseract's
  psm 6/12 output already had, so attribute_details.py's whole parsing
  pipeline (_join_wrapped_lines, _classify_label, _parse, validate_sections,
  heal_totals) needed zero changes, just a different text source.
"""
import logging

import numpy as np
from PIL import Image

log = logging.getLogger(__name__)

_pipeline = None

# See _cluster_by_overlap's min_overlap docstring: every genuine same-row
# label/value overlap measured against a real capture was 20px+, while the
# boundary-noise overlap that incorrectly bridged two distinct rows was 1-2px.
_ROW_OVERLAP_MARGIN = 5


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        log.info("Loading PaddleOCR detection+recognition pipeline (first use - a few seconds)")
        from paddleocr import PaddleOCR
        # See paddle_ocr.py's _get_model() for why this must come after the
        # import, not before: paddlex's own import-time setup_logging() sets
        # its "paddlex" logger to INFO unconditionally, so quieting it any
        # earlier gets silently overwritten.
        logging.getLogger("paddlex").setLevel(logging.WARNING)
        _pipeline = PaddleOCR(
            lang="en",
            use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False,
            enable_mkldnn=False,
        )
    return _pipeline


def _cluster_by_overlap(items: list[tuple], lo: int, hi: int, min_overlap: int = 1) -> list[list[tuple]]:
    """Buckets items (tuples with numeric fields at indices lo/hi, e.g.
    (x0, y0, y1, text)) into groups by actual range overlap on the (lo, hi)
    span against any existing member of a group - not distance-to-a-frozen-
    reference-point, which breaks in two different, confirmed-live ways (see
    _group_into_rows's docstring): (1) a wrapped label's own continuation
    line can sit centered closer to the *next* row than to its own row, and
    (2) two boxes on the visually same line can differ by a stray 1-2px in
    y0 - real detection noise, not a second line - which would otherwise
    flip their left-to-right order if sorted by y0 first. Overlap-based
    clustering handles both: a continuation line overlaps the *value* box
    sitting at its own row's first line even when it doesn't overlap that
    row's label box, and same-line noise trivially overlaps itself.

    min_overlap raises the bar above "any positive overlap" (the default,
    matching the original behavior). Needed for row-level clustering (see
    _group_into_rows): confirmed directly against a real capture where a
    bold value glyph's box (e.g. "4,405") sat a couple pixels taller than
    its own row and dipped 1-2px into the *next* row's label box, which
    then transitively chain-merged four separate component-stat rows
    (ATTACK/DEF/INT/Command Points) into one garbled line - every genuine
    same-row label/value pair measured in that capture overlapped by 20px+,
    so a small margin cleanly rejects that boundary noise without affecting
    same-line noise (still overlaps itself trivially) or a wrapped
    continuation line (merges via much deeper overlap than a couple of
    stray pixels)."""
    ordered = sorted(items, key=lambda i: i[lo])
    groups: list[list[tuple]] = []
    for item in ordered:
        matched = None
        for group in groups:
            if any(min(item[hi], g[hi]) - max(item[lo], g[lo]) >= min_overlap for g in group):
                matched = group
                break
        if matched is not None:
            matched.append(item)
        else:
            groups.append([item])
    groups.sort(key=lambda group: min(i[lo] for i in group))
    return groups


def _group_into_rows(boxes: list, texts: list) -> list[str]:
    """boxes are [x1, y1, x2, y2].

    Clusters into rows by Y-range overlap (see _cluster_by_overlap) - fixes
    a real, confirmed-live data-corruption bug: a label that wraps onto its
    own second line ("Kinetic DMG Advantage" / "Boost", with the value
    "0.6%" sitting at the *first* line's height) previously got its
    continuation word attached to the *next* row instead of its own, which
    then fed "Boost" into `_join_wrapped_lines`'s "no trailing number ->
    prepend to whatever comes next" fallback, producing "Boost Formation
    ATK Bonus" (a different row's label with the previous row's leftover
    word glued onto its front).

    Within a row, splits into columns by the single largest horizontal gap
    between item x-positions (label column vs. value column; a row with
    only one item skips this) so a wrapped label's second line joins the
    label column rather than getting sorted in between the label and the
    value - then orders each column top-to-bottom by the same overlap
    clustering (not a raw (y, x) sort, which flips same-line items whose y0
    differs by only detection noise - confirmed live: two value boxes on
    the same "POWER" row differed by 1px in y0 and came out reversed under
    a plain sort), and concatenates columns left to right."""
    items = [(box[0], box[1], box[3], text) for box, text in zip(boxes, texts)]  # (x0, y0, y1, text)
    rows = _cluster_by_overlap(items, lo=1, hi=2, min_overlap=_ROW_OVERLAP_MARGIN)

    lines = []
    for row in rows:
        xs = sorted(item[0] for item in row)
        gaps = [(xs[i + 1] - xs[i], xs[i]) for i in range(len(xs) - 1)]
        split_after_x = max(gaps)[1] if gaps else None
        left = [i for i in row if split_after_x is None or i[0] <= split_after_x]
        right = [i for i in row if split_after_x is not None and i[0] > split_after_x]
        ordered_texts = []
        for column in (left, right):
            for line in _cluster_by_overlap(column, lo=1, hi=2):
                ordered_texts.extend(i[3] for i in sorted(line, key=lambda i: i[0]))
        lines.append(" ".join(ordered_texts))
    return lines


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
