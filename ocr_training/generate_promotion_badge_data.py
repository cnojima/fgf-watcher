"""Generate synthetic training data for fine-tuning a PaddleOCR recognition
model on the ship Promote tab's current-level badge - a small icon (a
different shape/color per tier: teal triangle for I, gold triangle for II,
blue diamond for III, purple shield for IV, maroon pentagon for V, a muted
star/cross glyph with no numeral for level 0) that the stock PaddleOCR
recognizer misread as a bare "A" on a real level-I capture, confirmed live
this session across 1x-4x upscaling - not a resolution issue, a genuine
failure on this icon shape (see promotion_details.py's docstring and the
OCR-consolidation plan).

Unlike orange_kid_rec (the game's actual extracted font, unlimited exact-
fidelity synthetic renders) there's no source asset for this icon - each
class has exactly ONE real captured example (data/promotion_badges/*.png,
gathered live this session: three are the genuine current-status badge style
- I, III, empty; two are a differently-styled "next tier" gold/purple
preview badge - II, IV; V comes from a reference "Preview" panel showing all
tiers at once). This generates a training set by heavily augmenting each of
those six seed images (rotation, scale, color/brightness jitter, slight
translation) rather than rendering from scratch, since there's nothing to
render from - the model needs to learn to generalize from one real example
per class to the live game's actual crop, not memorize a synthetic
approximation of an icon it's never actually seen.

Character set is just "I"/"V" - every label ("", "I", "II", "III", "IV",
"V") is built from those two characters alone.
"""
import random
from pathlib import Path

from PIL import Image, ImageEnhance

SEED_DIR = Path(__file__).resolve().parent.parent / "data" / "promotion_badges"
OUTPUT_DIR = Path(__file__).resolve().parent / "promotion_badge_dataset"

# filename stem -> label. "empty" (level 0's muted star/cross glyph, no
# numeral) trains the model to predict nothing here, rather than leaving it
# unhandled - promotion_details.py's _read_badge_text keeps only I/V
# characters from whatever comes back, so any non-numeral prediction here
# already resolves to "no match" - but training on it directly is more
# honest than hoping an untrained input generalizes safely.
SEED_LABELS = {
    "empty": "",
    "I": "I",
    "II": "II",
    "III": "III",
    "IV": "IV",
    "V": "V",
}

CANVAS_SIZE = (140, 110)  # generous margin around the ~100-115x85-90px seeds for rotation/scale headroom


def _paste_centered(base: Image.Image, fg: Image.Image, cx: int, cy: int) -> None:
    base.paste(fg, (cx - fg.width // 2, cy - fg.height // 2))


def _augment_once(seed: Image.Image) -> Image.Image:
    # Background fill sampled from the seed's own corner rather than a fixed
    # color - each seed's real background tone differs slightly (the badge
    # sits on the ship-detail view's own gradient, which varies by ship).
    bg_color = seed.getpixel((1, 1))
    canvas = Image.new("RGB", CANVAS_SIZE, bg_color)

    img = seed.copy()
    scale = random.uniform(0.85, 1.15)
    img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS)

    angle = random.uniform(-8, 8)
    img = img.rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor=bg_color)

    img = ImageEnhance.Brightness(img).enhance(random.uniform(0.85, 1.15))
    img = ImageEnhance.Contrast(img).enhance(random.uniform(0.85, 1.15))
    img = ImageEnhance.Color(img).enhance(random.uniform(0.8, 1.2))

    cx = CANVAS_SIZE[0] // 2 + random.randint(-6, 6)
    cy = CANVAS_SIZE[1] // 2 + random.randint(-6, 6)
    _paste_centered(canvas, img, cx, cy)
    return canvas


def generate_dataset(n_train_per_class: int = 300, n_val_per_class: int = 30, seed: int = 0) -> None:
    random.seed(seed)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "dict.txt").write_text("I\nV\n", encoding="utf-8")

    seeds = {stem: Image.open(SEED_DIR / f"{stem}.png").convert("RGB") for stem in SEED_LABELS}

    for split, n_per_class in (("train", n_train_per_class), ("val", n_val_per_class)):
        images_dir = OUTPUT_DIR / split / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        lines = []
        i = 0
        for stem, label in SEED_LABELS.items():
            seed_img = seeds[stem]
            for _ in range(n_per_class):
                img = _augment_once(seed_img)
                filename = f"{i:06d}.jpg"
                img.save(images_dir / filename, quality=90)
                lines.append(f"{split}/images/{filename}\t{label}")
                i += 1
        (OUTPUT_DIR / f"{split}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"{split}: {len(lines)} samples ({n_per_class}/class) -> {OUTPUT_DIR / split}")


if __name__ == "__main__":
    generate_dataset()
