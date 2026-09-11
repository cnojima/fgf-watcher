"""Generate synthetic training data for fine-tuning a PaddleOCR recognition
model on "orange kid" - the game's custom font used for large level-badge
digits (champion level, weapon level, confirmed live to be the same font in
both places via direct visual comparison against the extracted TTF).

Why this exists: Tesseract fails on this font uniformly regardless of
preprocessing (confirmed across multiple champions/weapons - a visibly
clean, correctly-bounded crop still reads as garbage under every PSM mode,
the same "genuine font limitation" pattern CLAUDE.md documents for the ship
"FLAGSHIP" title). EasyOCR does somewhat better but with predictable
letter/digit confusion (e.g. "121" -> "Izi") that champion_info.py
currently corrects with a hand-built confusion table - a workaround, not a
fix. The font file itself was extracted directly from the game's Unity
asset archive (data.unity3d, via UnityPy) rather than approximated, so
synthetic samples use the *exact* glyphs the game renders, not a lookalike.

The font file is the game's own copyrighted asset - kept under data/fonts/
(gitignored, same boundary as screenshots) rather than committed to the
tracked repo. This script (and the rest of the training pipeline) IS
tracked, since it contains no copyrighted content itself - just re-run it
locally to regenerate the dataset from your own extracted copy.

Output matches PaddleX's expected text-recognition dataset layout exactly
(confirmed by reading its dataset_checker source, not guessed):

    orange_kid_dataset/
        dict.txt          # one character per line - the model's output vocabulary
        train.txt         # "train/images/000000.jpg\t<label>" per line
        val.txt           # same, for validation
        train/images/*.jpg
        val/images/*.jpg

train.txt/val.txt paths are relative to the dataset root (PaddleX does
`os.path.join(dataset_dir, file_name)` directly), not to their own file.
"""
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = Path(__file__).resolve().parent.parent / "data" / "fonts" / "orange_kid.ttf"
OUTPUT_DIR = Path(__file__).resolve().parent / "orange_kid_dataset"

# Confirmed live: champion level runs roughly 1-125+, weapon level 1-20ish -
# generated range covers both with margin rather than hand-splitting into
# two separate ranges, since the model doesn't need to know which field a
# digit string came from.
MIN_VALUE = 0
MAX_VALUE = 200

# Backgrounds sampled from real captures across this project's screenshots:
# dark olive/brown (weapon mini-badge), dark green/teal and dark red
# (champion level badge, varies with the quality-tier gradient behind it).
# Not exhaustive - real crops will show other tones - but covers the
# confirmed-observed variety rather than a single guessed background.
BACKGROUND_TONES = [
    (43, 40, 33),    # dark olive/brown - weapon mini-badge
    (30, 45, 40),    # dark teal-green - champion level badge (green side)
    (45, 30, 32),    # dark red - champion level badge (red side)
    (35, 35, 38),    # neutral dark gray
]

TEXT_COLOR = (238, 235, 222)  # off-white/cream, matches real captures (not pure white)

FONT_SIZES = (34, 38, 42, 46, 50)


def _random_background(width: int, height: int) -> Image.Image:
    base = random.choice(BACKGROUND_TONES)
    img = Image.new("RGB", (width, height), base)
    # Slight per-pixel noise so the model doesn't overfit to perfectly flat
    # backgrounds, which real screen captures never have (JPEG-like capture
    # noise, faint background art bleeding through).
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


def _render_sample(value: int, font_size: int) -> Image.Image:
    font = ImageFont.truetype(str(FONT_PATH), font_size)
    text = str(value)
    # Measure at a throwaway image first to size the canvas to the text,
    # then add margin - real crops always have a few px of padding around
    # the digits, not a pixel-tight bound.
    dummy = Image.new("RGB", (1, 1))
    bbox = ImageDraw.Draw(dummy).textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = random.randint(6, 14), random.randint(6, 14)
    width, height = text_w + pad_x * 2, text_h + pad_y * 2

    img = _random_background(width, height)
    draw = ImageDraw.Draw(img)
    draw.text((pad_x - bbox[0], pad_y - bbox[1]), text, font=font, fill=TEXT_COLOR)
    return img


def generate_dataset(n_train: int = 8000, n_val: int = 800, seed: int = 0) -> None:
    random.seed(seed)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Digit-only vocabulary - this font is only ever used for plain integer
    # level values in this project's captures, so the recognition model
    # only needs to output 0-9 (a much smaller/easier output space than a
    # general English charset, which should mean faster convergence with
    # fewer samples).
    (OUTPUT_DIR / "dict.txt").write_text("\n".join(str(d) for d in range(10)) + "\n", encoding="utf-8")

    for split, n in (("train", n_train), ("val", n_val)):
        images_dir = OUTPUT_DIR / split / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        lines = []
        for i in range(n):
            value = random.randint(MIN_VALUE, MAX_VALUE)
            font_size = random.choice(FONT_SIZES)
            img = _render_sample(value, font_size)
            filename = f"{i:06d}.jpg"
            img.save(images_dir / filename, quality=90)
            lines.append(f"{split}/images/{filename}\t{value}")
        (OUTPUT_DIR / f"{split}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"{split}: {n} samples -> {OUTPUT_DIR / split}")


if __name__ == "__main__":
    generate_dataset()
