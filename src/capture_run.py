"""Write immutable screen-capture runs for offline OCR replay."""
import hashlib
import json
from pathlib import Path

from PIL import Image


class CaptureRun:
    """Capture directory writer with a stable, replayable frame manifest."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.frames_dir = self.root / "frames"
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self.frames = []

    def save_image(self, image: Image.Image, relative_path: str, *, kind: str,
                   ship_index: int | None = None, sequence: int | None = None) -> Path:
        path = self.frames_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        image.convert("RGB").save(path, format="PNG")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.frames.append({
            "path": str(path.relative_to(self.root)),
            "kind": kind,
            "ship_index": ship_index,
            "sequence": sequence,
            "sha256": digest,
            "width": image.width,
            "height": image.height,
        })
        return path

    def write_manifest(self, **metadata) -> Path:
        manifest = {"version": 1, "frames": self.frames, **metadata}
        path = self.root / "manifest.json"
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return path