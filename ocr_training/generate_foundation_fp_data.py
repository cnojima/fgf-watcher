"""Generate synthetic training data for fine-tuning a PaddleOCR recognition
model on "Foundation FP" - the game's other custom font, used for major
section titles, champion/weapon/ship names, and short subtitles (see
CLAUDE.md and champion_info.py's docstring). Same font family behind the one
*genuine* font limitation found so far ("FLAGSHIP" - heavy tracking,
gradient fill, unreadable under every PSM mode and both Tesseract and
EasyOCR) as well as the champion-name/title and ship-name fields that
currently rely on EasyOCR as a workaround (predictable letter confusions,
e.g. "DOUG ROCKWELL" -> "'Dove ROCKWE!" under Tesseract).

Unlike orange_kid_rec (a closed 10-digit vocabulary), this font renders
open-ended free text - champion/ship/weapon names, not a small fixed set -
and there's no authoritative ground-truth name list to train against (see
this session's notes: several data/champions/*.json filenames are
themselves stale/imperfect OCR output, not confirmed-correct labels). So
this generates syllable-based pseudo-names rather than real game text - the
model needs to learn this font's *glyph shapes* across the full character
set and casing styles actually observed live, not memorize real vocabulary,
the same reasoning that let orange_kid_rec train on random digit strings
(not real level values) and still hit 100/100 on held-out real captures.

Casing styles confirmed live this session (see calibrate.py zoom captures):
- ALL CAPS, multi-word: champion names ("DOUG ROCKWELL", "KILLER BEE"),
  weapon titles ("ENDLESS WHISPER - ENERGY CANNON", the a-b-a-b hyphenated
  form included below)
- Title Case, single word: ship names ("Demerzel", "Gram", "Gungnir",
  "Opportunity" - confirmed via data/attributes/*.json, which unlike the
  champion filenames are stable/repeatedly-correct reads)
A small set of these confirmed-real strings is mixed in directly (weighted
low, since the point is glyph coverage, not memorization) alongside the
generated pseudo-names.
"""
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = Path(__file__).resolve().parent.parent / "data" / "fonts" / "Foundation_FP.ttf"
OUTPUT_DIR = Path(__file__).resolve().parent / "foundation_fp_dataset"

_CONSONANTS = "bcdfghjklmnpqrstvwxz"
_VOWELS = "aeiou"

# Confirmed-real strings from this session's live captures/docstrings - see
# module docstring. Mixed into the corpus at low weight (CONFIRMED_WEIGHT
# below), not the bulk of it.
_CONFIRMED_REAL = (
    "FLAGSHIP", "DOUG ROCKWELL", "KILLER BEE", "ZORA DOMINI", "GOVERNOR",
    "Demerzel", "Gram", "Gungnir", "Opportunity",
    "ENDLESS WHISPER - ENERGY CANNON", "KINETIC", "ATTACK",
)
CONFIRMED_WEIGHT = 0.15

# Characters this font actually needs to render, per confirmed live
# examples: uppercase/lowercase letters, space, apostrophe (possessive
# names, e.g. "Widow's Kiss"), hyphen (weapon title separator). Digits
# included at low cost/uncertain need (no confirmed example yet, but cheap
# to cover in a CTC head this small).
CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 '-"

BACKGROUND_TONES = [
    (43, 40, 33),    # dark olive/brown
    (30, 45, 40),    # dark teal-green
    (45, 30, 32),    # dark red
    (35, 35, 38),    # neutral dark gray/navy (title bars)
    (150, 105, 40),  # warm gold/tan - confirmed live (weapon hero backdrop)
]

TEXT_COLOR = (238, 235, 222)  # off-white/cream, matches real captures

FONT_SIZES = (26, 32, 38, 44, 50, 58)


def _syllable() -> str:
    return random.choice(_CONSONANTS) + random.choice(_VOWELS) + random.choice("" if random.random() < 0.5 else _CONSONANTS)


def _pseudo_word(min_syl: int = 1, max_syl: int = 3) -> str:
    return "".join(_syllable() for _ in range(random.randint(min_syl, max_syl)))


def _random_string() -> str:
    style = random.choices(
        ("all_caps_multi", "title_single", "title_possessive", "hyphenated_title"),
        weights=(0.4, 0.3, 0.15, 0.15),
    )[0]
    if style == "all_caps_multi":
        words = [_pseudo_word() for _ in range(random.randint(1, 2))]
        return " ".join(words).upper()
    if style == "title_single":
        return _pseudo_word(2, 3).capitalize()
    if style == "title_possessive":
        return f"{_pseudo_word(1, 2).capitalize()}'s {_pseudo_word(1, 2).capitalize()}"
    return f"{_pseudo_word(1, 2)} - {_pseudo_word(1, 2)}".upper()


def _next_text() -> str:
    if random.random() < CONFIRMED_WEIGHT:
        return random.choice(_CONFIRMED_REAL)
    return _random_string()


def _random_background(width: int, height: int) -> Image.Image:
    base = random.choice(BACKGROUND_TONES)
    img = Image.new("RGB", (width, height), base)
    pixels = img.load()
    for y in range(height):
        for x in range(width):
            jitter = random.randint(-8, 8)
            r, g, b = base
            pixels[x, y] = (
                max(0, min(255, r + jitter)),
                max(0, min(255, g + jitter)),
                max(0, min(255, b + jitter)),
            )
    return img


def _render_sample(text: str, font_size: int) -> Image.Image:
    font = ImageFont.truetype(str(FONT_PATH), font_size)
    dummy = Image.new("RGB", (1, 1))
    bbox = ImageDraw.Draw(dummy).textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = random.randint(6, 16), random.randint(6, 16)
    width, height = text_w + pad_x * 2, text_h + pad_y * 2

    img = _random_background(width, height)
    draw = ImageDraw.Draw(img)
    draw.text((pad_x - bbox[0], pad_y - bbox[1]), text, font=font, fill=TEXT_COLOR)
    return img


def generate_dataset(n_train: int = 12000, n_val: int = 1200, seed: int = 0) -> None:
    random.seed(seed)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "dict.txt").write_text("\n".join(CHARSET) + "\n", encoding="utf-8")

    for split, n in (("train", n_train), ("val", n_val)):
        images_dir = OUTPUT_DIR / split / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        lines = []
        for i in range(n):
            text = _next_text()
            font_size = random.choice(FONT_SIZES)
            img = _render_sample(text, font_size)
            filename = f"{i:06d}.jpg"
            img.save(images_dir / filename, quality=90)
            lines.append(f"{split}/images/{filename}\t{text}")
        (OUTPUT_DIR / f"{split}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"{split}: {n} samples -> {OUTPUT_DIR / split}")


if __name__ == "__main__":
    generate_dataset()
