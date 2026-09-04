"""Preprocess a cropped screenshot region and OCR it."""
import pytesseract
from PIL import Image, ImageOps

# UB-Mannheim installer default path; adjust if Tesseract was installed elsewhere.
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def preprocess(image: Image.Image, upscale: int = 3, threshold: int | None = None) -> Image.Image:
    """Grayscale + upscale. Game HUD text is usually small, which trips up Tesseract
    at native resolution.

    threshold=None (default) skips binarization: most game UI text is anti-aliased,
    and a fixed threshold cutting at mid-gray chews up those soft edges and makes
    OCR *worse*, not better. Pass a 0-255 cutoff only if a region has a genuinely
    noisy/busy background where thresholding measurably helps for it.
    """
    gray = ImageOps.grayscale(image)
    gray = gray.resize((gray.width * upscale, gray.height * upscale), Image.LANCZOS)
    if threshold is not None:
        gray = gray.point(lambda p: 255 if p > threshold else 0)
    return gray


def read_text(image: Image.Image, digits_only: bool = False, threshold: int | None = None) -> str:
    processed = preprocess(image, threshold=threshold)
    config = "--psm 7"  # treat region as a single line of text
    if digits_only:
        config += " -c tessedit_char_whitelist=0123456789,./%"
    return pytesseract.image_to_string(processed, config=config).strip()
