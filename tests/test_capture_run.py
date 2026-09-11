import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PIL import Image

from capture_run import CaptureRun
from replay_all_flagships import _load_frame, _load_manifest


class CaptureRunTests(unittest.TestCase):
    def test_manifest_records_and_verifies_frame_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = CaptureRun(root)
            image = Image.new("RGB", (4, 3), (12, 34, 56))
            run.save_image(image, "ship-000/overview-000.png", kind="overview", ship_index=0, sequence=0)
            run.write_manifest(platform="darwin", window_size=[4, 3])

            manifest = _load_manifest(root)
            self.assertEqual(manifest["window_size"], [4, 3])
            loaded = _load_frame(root, manifest["frames"][0])
            self.assertEqual(loaded.size, (4, 3))

            frame_path = root / manifest["frames"][0]["path"]
            frame_path.write_bytes(frame_path.read_bytes() + b"tampered")
            with self.assertRaisesRegex(RuntimeError, "Capture frame changed"):
                _load_frame(root, manifest["frames"][0])


if __name__ == "__main__":
    unittest.main()
