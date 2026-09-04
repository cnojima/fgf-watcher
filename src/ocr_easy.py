"""EasyOCR-based text reading, for stylized game fonts that defeat Tesseract.

Tesseract (ocr.py) misreads individual letters on this game's display font -
G/C confusion on "FLAGSHIP", D/N confusion on "Demerzel" - regardless of
preprocessing (upscale, threshold, PSM mode all tried, see dev notes).
EasyOCR's neural model reads those same crops correctly. It's much slower to
load (a torch model, several seconds on first use) and to run per-call than
Tesseract, so it's used only where Tesseract has been confirmed to fail on
this font - e.g. ship names - not as a blanket replacement for digit/plain
UI text reading, where Tesseract is faster and already accurate.
"""
import numpy as np
from PIL import Image

_reader = None


def _get_reader():
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


def read_text(image: Image.Image) -> str:
    reader = _get_reader()
    results = reader.readtext(np.array(image.convert("RGB")), detail=0)
    return " ".join(results).strip()
