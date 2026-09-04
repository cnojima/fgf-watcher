# fgf-watcher

Capture a game window, OCR specific stat regions, log values over time, and (optionally) drive menu input.

Built and tested against Python 3.12 + Tesseract 5.4 on Windows, targeting a windowed (non-fullscreen-exclusive) game.

## Setup (already done in this environment)

- Python 3.12: `C:\Users\cnoji\AppData\Local\Programs\Python\Python312\python.exe`
- Tesseract OCR: `C:\Program Files\Tesseract-OCR\tesseract.exe` (path is hardcoded in `src/ocr.py`)
- Python deps: `pip install -r requirements.txt` (includes EasyOCR, which pulls in torch —
  large install, and its first use downloads model weights)

**The game runs elevated (as Administrator).** Windows blocks synthetic input from a
lower-integrity process to a higher-integrity window (UIPI), so any script that clicks or
presses keys — not pure screenshotting — must run elevated too, via `run_admin.ps1`:
```
powershell -File run_admin.ps1 src\some_script.py [args]
```
This triggers one UAC consent prompt per invocation; there's no way around that, and
scripts here don't try to.

## Workflow

1. **Find your window title and calibrate pixel coordinates**
   ```
   python src/calibrate.py list
   python src/calibrate.py shot "substring of window title"
   python src/calibrate.py zoom X Y [radius] [source]
   ```
   `shot` saves a full gridded screenshot to `data/calibration.png` (50px grid) plus an
   ungridded `data/calibration_raw.png`. Use it to read off *approximate* coordinates, then
   **always confirm with `zoom`** (10px grid) before clicking anything — reading coordinates
   off the full, downscaled screenshot is unreliable enough that it caused several wrong
   clicks during development; `zoom` is what actually gets you a correct coordinate.

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

4. **Navigate menus** (`src/nav.py`) — prefers the game's keyboard shortcuts
   (`docs/keyboard-shortcuts.jpg`) over pixel-coordinate clicks wherever one exists, since a
   key press needs no calibration and survives the window moving/resizing:
   - `goto(hwnd, screen_name)` — jumps to a base view (`system_map`/`city_view`, toggled by
     SPACE) or opens an overlay (`fleet_list`=V, `storage`=B, `champion`=C, `guild`=G,
     `radiant`=R, `chat`=ENTER). Verifies arrival via `fingerprints.py` when one is
     catalogued for that screen.
   - `back(hwnd)` — closes the current overlay via the on-screen back-arrow click.
   - **ESC is deliberately never used** for navigation. It's "Quit game" from a base view,
     and per a known game bug it can also trigger a full quit from certain overlays instead
     of closing just that overlay — unsafe as a generic back/reset action.

5. **Detect which screen is showing** (`src/fingerprints.py`) — pixel-color fingerprints,
   not OCR. Several UI elements here (the "FLAGSHIP" title, "Trader Era") use a decorative
   font or sit over a watermark graphic that defeats text recognition entirely, but a single
   pixel inside a known letter stroke or background patch is reliably the same color
   whenever that screen is showing.

6. **Send input** (`src/input_control.py`) — building blocks only, not a full bot:
   - `focus_window(hwnd)`, `click(hwnd, x, y)`, `press_key(hwnd, key)`
   - Coordinates are relative to the window's client area, same frame as calibration.
   - Uses `pydirectinput` instead of `pyautogui` because many games only respond to
     DirectInput-style synthetic input.
   - Must run elevated (see above) — the game runs as Administrator.

7. **Example feature: reading owned flagships** (`src/flagships.py`) — opens the fleet
   list, pages through the ship detail view (1-4 ships), and OCRs each ship's name with
   `ocr_easy.py` (EasyOCR) rather than Tesseract. See "Known gotchas" below for why.

8. **Example feature: reading a ship's full stat breakdown** (`src/attribute_details.py`)
   — opens the "Attribute Details" modal and scrolls through its full, longer-than-one-
   screen table (HP/ATTACK/INT/DEF plus derived stats like Crit Rate and Damage Reduction,
   each broken into modifier sub-rows). Scrolls by dragging (this game has no scroll wheel
   support), stitches every capture into one seamless image aligned by actual pixel content
   rather than merging OCR text across captures, OCRs the whole thing once, and
   cross-validates + self-corrects each section's total against its own sub-row math via
   `validate_sections()`/`heal_totals()`. See CLAUDE.md for the full story of why this
   module looks the way it does - getting a reliable scrollable-list reader working took
   many iterations and each one taught something worth not re-learning.

## Known gotchas (found while testing against a live game)

- **Give text regions vertical margin for descenders — this caused most of our OCR
  failures, not font/engine limitations.** A box cropped tight to what *looks* like a
  line of text (e.g. `y: 10-65`) clips the bottoms of `g/j/p/q/y`, and both Tesseract and
  EasyOCR then misread the whole word ("Opportunity" → "Opportunitv", "Gungnir" → garbage)
  — not because the font is hard, but because part of the glyph is simply gone. Confirmed
  by re-cropping with a taller box (`y: 5-80`): both engines then read every name
  correctly. Before concluding an engine/font can't handle some text, save the crop and
  look at it — if a descender is cut off, that's the bug, not the OCR.
- **Don't hard-threshold/binarize game UI text.** `src/ocr.py`'s `preprocess()` used to
  apply a fixed-cutoff black/white threshold, which looked cleaner to the eye but actually
  *destroyed* OCR accuracy — anti-aliased UI fonts lost their edges and Tesseract read
  garbage. Default is now grayscale + 3x upscale only, no threshold. Only pass a
  `threshold=` value if you've confirmed it helps for a specific noisy-background region.
- **Decorative title fonts can still defeat Tesseract even with a correct box** — the
  "FLAGSHIP" screen title (heavy tracking, gradient fill) reads as garbage under every
  PSM mode tried. EasyOCR reads it about as well as Tesseract (still imperfect: `'FLHecl'`).
  This is a real font-rendering limit, unlike the descender issue above — don't waste time
  re-tuning the box for something like this; use a pixel fingerprint instead (see
  `fingerprints.py`) since you only need to *detect* the screen, not transcribe the title.
- **`screenshot_window()` refuses to capture unless the target window is actually in the
  foreground.** `mss` grabs a screen *region* at the window's last-known coordinates, not
  the window's content directly — if another window (browser, alt-tab) covers that region,
  a naive capture would silently return the wrong thing. Bring the game window to front
  before calling any `calibrate.py`/`capture.py` function if you hit this error.
- **Pick regions that don't scroll/animate.** A region over live chat or a ticker will
  OCR whatever's there *at the instant of capture* — fine for a one-off read, useless for
  a stable "current value" reading. Point regions at static HUD elements (resource
  counters, health bars, etc.), not scrolling panels.
- Client-area capture (`win32gui.GetClientRect` + `ClientToScreen`) excludes the title bar
  automatically, so pixel coordinates in `calibrate.py` output line up directly with
  `regions.json` boxes.
- **DPI awareness must be set before any `win32gui` call or `mss` capture** (`capture.py`
  does this at import time). Without it, this process is DPI-unaware and `win32gui`
  returns coordinates in a virtualized logical-pixel space that doesn't match the physical
  pixels `mss`/`SetCursorPos` use on a scaled display — silently misaligning every
  screenshot and click by the scale factor (e.g. 1.25x at 125% scaling).

## Next steps to consider

- If a HUD has a genuinely noisy background, try `read_text(image, threshold=N)` per-region
  rather than changing the global default.
- For numeric-only stats, `digits_only: true` in a region's config restricts Tesseract's
  character whitelist, which helps a lot with 0/O and 1/l confusion.
- **Default to Tesseract (`ocr.py`) for new regions, not EasyOCR.** `flagships.py` uses
  EasyOCR (`ocr_easy.py`) for ship names, but once the descender-clipping bug above was
  fixed, Tesseract read those same names correctly too — the engine wasn't the problem.
  EasyOCR is slower (a torch model to load) and a much heavier dependency; reach for it
  only after confirming a *correctly-sized* box still fails on Tesseract, which so far has
  only been true for decorative titles like "FLAGSHIP" that we don't actually need to OCR
  (a pixel fingerprint identifies the screen instead).
- Only 2 of ~7 catalogued screens (`system_map`, `fleet_list`) have pixel fingerprints in
  `fingerprints.py`. `storage`, `champion`, `guild`, `radiant`, `chat`, and `city_view` are
  wired into `nav.py`'s key mappings but `goto()` can't verify arrival for them yet.
