# fgf-watcher

Capture a game window, OCR specific stat regions, log values over time, and (optionally) drive menu input.

Built and tested against Python 3.12 + Tesseract 5.4 on Windows, targeting a windowed (non-fullscreen-exclusive) game.

## Setup (already done in this environment)

- Python 3.12: `C:\Users\cnoji\AppData\Local\Programs\Python\Python312\python.exe`
- Tesseract OCR: `C:\Program Files\Tesseract-OCR\tesseract.exe` (path is hardcoded in `src/ocr.py`)
- Python deps: `pip install -r requirements.txt`

## Workflow

1. **Find your window title and calibrate pixel coordinates**
   ```
   python src/calibrate.py list
   python src/calibrate.py shot "substring of window title"
   ```
   This saves `data/calibration.png` — a screenshot of the window's client area with a red
   50px grid and coordinate labels. Open it and read off `(left, top, right, bottom)` pixel
   boxes for each stat you want tracked.

2. **Define regions** in a config file (see `config/regions.example.json`):
   ```json
   {
     "window_title": "substring of window title",
     "regions": {
       "gold": {"box": [1690, 100, 1900, 140], "digits_only": true}
     }
   }
   ```
   Copy it to `config/regions.json` and fill in real boxes/title.

3. **Track**
   ```
   python src/tracker.py config/regions.json
   ```
   Polls every region on an interval, OCRs each, and appends a row to `data/log.csv`
   whenever a value changes (timestamp, region name, new value).

4. **Menu input** (`src/input_control.py`) — building blocks only, not a full bot:
   - `focus_window(hwnd)`, `click(hwnd, x, y)`, `press_key(hwnd, key)`
   - Coordinates are relative to the window's client area, same frame as calibration.
   - Uses `pydirectinput` instead of `pyautogui` because many games only respond to
     DirectInput-style synthetic input.

## Known gotchas (found while testing against a live game)

- **Don't hard-threshold/binarize game UI text.** `src/ocr.py`'s `preprocess()` used to
  apply a fixed-cutoff black/white threshold, which looked cleaner to the eye but actually
  *destroyed* OCR accuracy — anti-aliased UI fonts lost their edges and Tesseract read
  garbage. Default is now grayscale + 3x upscale only, no threshold. Only pass a
  `threshold=` value if you've confirmed it helps for a specific noisy-background region.
- **Pick regions that don't scroll/animate.** A region over live chat or a ticker will
  OCR whatever's there *at the instant of capture* — fine for a one-off read, useless for
  a stable "current value" reading. Point regions at static HUD elements (resource
  counters, health bars, etc.), not scrolling panels.
- Client-area capture (`win32gui.GetClientRect` + `ClientToScreen`) excludes the title bar
  automatically, so pixel coordinates in `calibrate.py` output line up directly with
  `regions.json` boxes.

## Next steps to consider

- If a HUD has a genuinely noisy background, try `read_text(image, threshold=N)` per-region
  rather than changing the global default.
- For numeric-only stats, `digits_only: true` in a region's config restricts Tesseract's
  character whitelist, which helps a lot with 0/O and 1/l confusion.
- If OCR accuracy is still poor on a particular font, EasyOCR (GPU-friendly, no fixed
  charset) is a heavier but often more accurate fallback — not installed here yet.
