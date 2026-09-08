"""Step 1: find your game window and save a full screenshot with a coordinate grid,
so you can read off pixel boxes for regions.json by eye.

Usage:
    python src/calibrate.py list                        # show all window titles
    python src/calibrate.py shot "window title"          # save gridded screenshot to data/
    python src/calibrate.py zoom X Y [radius] [source]   # zoom into (X,Y) from a prior shot

IMPORTANT: reading coordinates by eye off the full screenshot (especially after
it gets downscaled for viewing) is error-prone — text near where you *think* a
UI element is often turns out to be blank space once you zoom in, because a
few percent of visual misjudgment on a 2000+px-wide image is a lot of real
pixels. Always confirm a coordinate with `zoom` before clicking it, rather than
eyeballing the full shot.

`shot` brings the game window to the foreground itself (via focus_window())
before capturing, since screenshot_window() refuses otherwise. On Windows this
means `shot` now goes through the same SetForegroundWindow path as click()/
press_key() - if the game's elevated (as Administrator) and this needs
elevation too where it didn't before, run it via run_admin.ps1 like any other
input-driving script. Not yet confirmed live on Windows.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from capture import describe_display_scale, find_window, get_window_rect, list_windows, screenshot_window
from input_control import focus_window

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _draw_grid(img: Image.Image, step: int) -> Image.Image:
    draw = ImageDraw.Draw(img)
    for x in range(0, img.width, step):
        draw.line([(x, 0), (x, img.height)], fill=(255, 0, 0), width=1)
        draw.text((x + 2, 2), str(x), fill=(255, 0, 0))
    for y in range(0, img.height, step):
        draw.line([(0, y), (img.width, y)], fill=(255, 0, 0), width=1)
        draw.text((2, y + 2), str(y), fill=(255, 0, 0))
    return img


def save_gridded_screenshot(title_substring: str, grid_step: int = 50) -> Path:
    hwnd = find_window(title_substring)
    focus_window(hwnd)  # screenshot_window refuses unless hwnd is frontmost
    img = screenshot_window(hwnd).convert("RGB")
    _draw_grid(img, grid_step)

    DATA_DIR.mkdir(exist_ok=True)
    out_path = DATA_DIR / "calibration.png"
    img.save(out_path)
    return out_path


def save_zoom(x: int, y: int, radius: int = 100, source: str | None = None, grid_step: int = 10) -> Path:
    """Crop a region around (x, y) out of an *ungridded* copy of the last screenshot
    and overlay a fine grid, so labels don't obscure the content you're trying to
    pixel-hunt through."""
    src_path = Path(source) if source else DATA_DIR / "calibration_raw.png"
    img = Image.open(src_path).convert("RGB")
    box = (max(0, x - radius), max(0, y - radius), x + radius, y + radius)
    crop = img.crop(box)
    crop = crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS)

    # re-draw grid in crop-local coordinates but label with original-image coordinates
    draw = ImageDraw.Draw(crop)
    x0, y0 = box[0], box[1]
    for gx in range(x0 - (x0 % grid_step), box[2], grid_step):
        lx = (gx - x0) * 2
        draw.line([(lx, 0), (lx, crop.height)], fill=(255, 0, 0), width=1)
        draw.text((lx + 2, 2), str(gx), fill=(255, 255, 0))
    for gy in range(y0 - (y0 % grid_step), box[3], grid_step):
        ly = (gy - y0) * 2
        draw.line([(0, ly), (crop.width, ly)], fill=(255, 0, 0), width=1)
        draw.text((2, ly + 2), str(gy), fill=(255, 255, 0))

    DATA_DIR.mkdir(exist_ok=True)
    out_path = DATA_DIR / "zoom.png"
    crop.save(out_path)
    return out_path


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("list", "shot", "zoom"):
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == "list":
        for title in list_windows():
            print(title)
    elif sys.argv[1] == "shot":
        if len(sys.argv) < 3:
            print("Usage: python src/calibrate.py shot \"window title substring\"")
            sys.exit(1)
        hwnd = find_window(sys.argv[2])
        focus_window(hwnd)  # screenshot_window refuses unless hwnd is frontmost
        raw = screenshot_window(hwnd).convert("RGB")
        DATA_DIR.mkdir(exist_ok=True)
        raw.save(DATA_DIR / "calibration_raw.png")
        gridded = raw.copy()
        _draw_grid(gridded, 50)
        gridded.save(DATA_DIR / "calibration.png")
        rect = get_window_rect(hwnd)
        print(f"Profile key for this window: ({sys.platform!r}, ({rect.width}, {rect.height}))")
        print(describe_display_scale(hwnd))
        print(f"Saved {DATA_DIR / 'calibration.png'}")
        print("Open it and read off approximate pixel coordinates (red gridlines every 50px), "
              "then run `zoom X Y` to confirm before clicking anything.")
    elif sys.argv[1] == "zoom":
        if len(sys.argv) < 4:
            print("Usage: python src/calibrate.py zoom X Y [radius] [source]")
            sys.exit(1)
        x, y = int(sys.argv[2]), int(sys.argv[3])
        radius = int(sys.argv[4]) if len(sys.argv) > 4 else 100
        source = sys.argv[5] if len(sys.argv) > 5 else None
        out_path = save_zoom(x, y, radius, source)
        print(f"Saved {out_path} (10px grid, yellow labels are original-image coordinates)")
