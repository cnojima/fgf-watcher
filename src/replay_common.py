"""Shared offline-replay IO: load a capture manifest and its frames without
touching the game window, verifying each frame's content hasn't changed
since capture. Used by both replay_all_flagships.py and
replay_all_champions.py - see capture_run.py for the manifest/frame format
this reads.
"""
import hashlib
import json
from pathlib import Path

from PIL import Image


def load_manifest(root: Path) -> dict:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("version") != 1:
        raise RuntimeError(f"Unsupported capture manifest version: {manifest.get('version')!r}")
    return manifest


def load_frame(root: Path, entry: dict) -> Image.Image:
    path = root / entry["path"]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != entry["sha256"]:
        raise RuntimeError(f"Capture frame changed: {path}")
    return Image.open(path).convert("RGB")


def crop(image: Image.Image, box) -> Image.Image:
    return image.crop(box)


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # ensure_ascii=False - ability/bonus text is full of legitimate non-ASCII
    # glyphs read straight off the game's UI (the "×" multiplication
    # sign in e.g. "Formation INT × 300%"), which the default escapes into
    # unreadable \uXXXX sequences throughout every ability description.
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
