"""Step 2: poll the regions defined in a config file, OCR each one, and log
values that change to a CSV (timestamped) plus keep the latest values in memory
as running state.

Usage:
    python src/tracker.py config/regions.json
"""
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from capture import find_window, screenshot_region
from display_profiles import ProfileKey, select_profile
from ocr import read_text

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_region_profiles(config: dict) -> dict[ProfileKey, dict]:
    profiles: dict[ProfileKey, dict] = {}
    for p in config["profiles"]:
        size = tuple(p["window_size"]) if p.get("window_size") else (0, 0)
        profiles[(p["platform"], size)] = p["regions"]
    return profiles


def poll_loop(config_path: str, interval_seconds: float = 2.0) -> None:
    config = load_config(config_path)
    hwnd = find_window(config["window_title"])
    regions = select_profile(hwnd, _load_region_profiles(config), "regions")

    DATA_DIR.mkdir(exist_ok=True)
    log_path = DATA_DIR / "log.csv"
    is_new_log = not log_path.exists()

    state: dict[str, str] = {name: "" for name in regions}

    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new_log:
            writer.writerow(["timestamp", "region", "value"])

        print(f"Tracking {list(regions)} — polling every {interval_seconds}s. Ctrl+C to stop.")
        try:
            while True:
                for name, spec in regions.items():
                    box = tuple(spec["box"])
                    digits_only = spec.get("digits_only", False)
                    image = screenshot_region(hwnd, box)
                    value = read_text(image, digits_only=digits_only)

                    if value != state[name]:
                        timestamp = datetime.now(timezone.utc).isoformat()
                        writer.writerow([timestamp, name, value])
                        f.flush()
                        print(f"[{timestamp}] {name}: {state[name]!r} -> {value!r}")
                        state[name] = value

                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    poll_loop(sys.argv[1])
