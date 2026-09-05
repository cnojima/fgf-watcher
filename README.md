# fgf-watcher

Capture a game window, OCR specific stat regions, log values over time, and (optionally) drive menu input.

Built and tested against Python 3.12 + Tesseract 5.4 on Windows, targeting a windowed (non-fullscreen-exclusive) game.

## Setup (already done in this environment)

- Python 3.12: `C:\Users\cnoji\AppData\Local\Programs\Python\Python312\python.exe`
- Tesseract OCR: `C:\Program Files\Tesseract-OCR\tesseract.exe` (path is hardcoded in `src/ocr.py`)
- EasyOCR (`ocr_easy.py`): a heavier fallback engine for text Tesseract can't read even with
  a correctly-sized box (see Known gotchas) — installed via `requirements.txt` below, pulls
  in torch, and downloads its model weights on first use (needs network access that once).
- Python deps: `pip install -r requirements.txt` (mss, pywin32, pytesseract, pillow,
  pydirectinput, easyocr)

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
   - `focus_window(hwnd)`, `click(hwnd, x, y)`, `press_key(hwnd, key)`, `drag(hwnd, x1, y1, x2, y2)`
   - Coordinates are relative to the window's client area, same frame as calibration.
   - Uses `pydirectinput` instead of `pyautogui` because many games only respond to
     DirectInput-style synthetic input. `pydirectinput` has no `scroll()` at all (no
     `MOUSEEVENTF_WHEEL` wrapper) - `drag()` is how every scrollable list here is scrolled,
     as a mouse-down/move/hold-briefly/mouse-up touchscreen-style swipe. The brief hold
     before release matters: releasing the instant the cursor stops reads as a flick and
     the list keeps coasting on momentum afterward, making the actual scroll distance
     inconsistent between calls.
   - Must run elevated (see above) — the game runs as Administrator.

7. **Example feature: reading owned flagships** (`src/flagships.py`) — opens the fleet
   list, pages through the ship detail view (1-4 ships), and OCRs each ship's name with
   `ocr_easy.py` (EasyOCR) rather than Tesseract. See "Known gotchas" below for why.

8. **Example feature: reading a ship's full stat breakdown** (`src/attribute_details.py`)
   — opens the "Attribute Details" modal and scrolls through its full, longer-than-one-
   screen table (HP/ATTACK/INT/DEF plus derived stats like Crit Rate and Damage Reduction,
   each broken into modifier sub-rows). Scrolls with `drag()`, stitches every capture into
   one seamless image aligned by actual pixel content (`_content_offset`) rather than
   merging OCR text across captures, OCRs the whole thing once, and cross-validates +
   self-corrects each section's total against its own sub-row math via
   `validate_sections()`/`heal_totals()`. See CLAUDE.md for the full story of why this
   module looks the way it does - getting a reliable scrollable-list reader working took
   many iterations and each one taught something worth not re-learning.

9. **Example feature: collecting every owned flagship's full stats**
   (`src/collect_all_flagships.py`) — opens the fleet list, pages through all 1-4 owned
   ships (left/right arrows within the ship detail view, not by re-entering the list and
   clicking a card each time - see the module docstring for why that approach was tried
   and abandoned), runs `attribute_details.read_attribute_details()` on each one, and
   writes `data/attributes/{ship name}.json` (`{"ship", "attributes", "validation"}`) per
   ship. Run directly: `powershell -File run_admin.ps1 src\collect_all_flagships.py`.

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
- **A label can legitimately appear twice under one section** — e.g. `attribute_details.py`
  found ATK/DEF/INT each list "Components" once as a raw base value (e.g. `11,309`) and
  again as a separate bonus percentage (e.g. `20.00%`, confirmed against the game directly
  by the user: it's a "complete set" bonus). Keying a row store on label alone silently
  drops one; key on `(label, is_percentage)` instead so both survive.
- **When comparing pixels between two scrolled captures to measure scroll distance, exclude
  any static UI chrome from the compared strip.** A strip that included the modal's fixed
  "Overview/Details" tab bar always scored a perfect match at offset 0 no matter how far the
  actual list content had moved, since that chrome never changes - making the scroll
  mechanism look completely broken when it was working fine. Sample the comparison strip
  from below any fixed header/tab-bar region.
- **A parsing regex that requires an entire line to be clean fails completely on one stray
  OCR character, not partially.** `"ATTACK 23,725"` misread as `"ATTACK 23,/25"` (a "7"
  swapped for a symbol) made a strict end-anchored pattern reject the *whole line* -
  silently dropping a section header and misattributing all its sub-rows to whichever
  section was previously active. Match the value as the first plausible number token and
  ignore what follows, rather than requiring the rest of the line to be digit-free.
- **When a field is redundantly determined by others, use that redundancy to correct OCR
  errors, not just detect them.** A section's total is a known function of its own
  sub-rows (see `validate_sections`'s docstring for the formula, confirmed against the
  game's real numbers). `heal_totals` replaces a total that fails validation with the
  value computed from its sub-rows, and marks the section `"_total_healed": "true"` so
  a caller can still tell the original OCR'd number didn't match.
- **The elevated console window can render on top of the game and eat clicks meant for
  it**, with no error raised (the game was still technically the foreground window).
  `run_admin.ps1` launches the elevated Python process with `-WindowStyle Hidden` to
  prevent this - `python.exe` is a console app, so without it Windows shows a visible,
  topmost-when-it-spawns console window for the elevated process.
- **Re-entering a list screen and clicking a specific card's position is less reliable than
  it looks.** Selecting flagships by returning to the fleet list and clicking each card in
  turn needed a manual pixel correction on one card, and separately re-clicking a card
  position twice both times reopened a ship already seen instead of a new one (never fully
  root-caused - possibly a "last selected" sticky-highlight state). `collect_all_flagships.py`
  avoids this entirely by staying in the ship detail view and paging with the left/right
  arrows instead of returning to the list between ships.

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
- `collect_all_flagships.py` occasionally captures 11 of a ship's 12 stat sections instead
  of 12 - the twelfth ("Chance to inflict Major Damage") sometimes only gets its `_total`
  without sub-rows on a given run. Not corrupted data, just incomplete for that one field;
  a retry-on-incomplete-section pass would close this gap if it matters for a given use.
