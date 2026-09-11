# fgf-watcher

Capture a game window, OCR specific stat regions, log values over time, and (optionally) drive menu input.

Built and tested against Python 3.12 + PaddleOCR on Windows, targeting a windowed
(non-fullscreen-exclusive) game. Also supports macOS against a native Mac build of the
same game, via a separate capture/input backend (see "macOS setup" below) — **fullscreen
is unsupported on either platform** (see "Windowed, fixed-size only" below); everything
else in this repo (`nav.py`, `calibrate.py`, `paddle_ocr.py`, `tracker.py`, etc.) is
platform-agnostic and needs no changes to work on either OS.

All OCR goes through PaddleOCR now (`paddle_ocr.py` for single-line text,
`paddle_ocr_blocks.py` for multi-line blocks like stat tables, plus two small
fine-tuned models - `orange_kid_ocr.py` for level-badge digits,
`promotion_badge_ocr.py` for the Promote tab's Roman-numeral badge - for the two
places PaddleOCR's stock recognizer didn't already read a custom game icon/font
correctly). Tesseract and EasyOCR were both dropped this session after directly
confirming PaddleOCR reads this game's stylized fonts as well or better across
every field checked - see `ocr_training/` for the fine-tuning work and CLAUDE.md
for the fuller investigation.

## Setup (already done in this environment, Windows)

- Python 3.12: `C:\Users\cnoji\AppData\Local\Programs\Python\Python312\python.exe`
- Python deps: `pip install -r requirements.txt` (mss, pywin32, pillow, pydirectinput,
  paddlepaddle, paddleocr) - no external OCR binary to install; `paddlepaddle` and
  `paddleocr` are plain pip packages (each listed explicitly - neither pulls the
  other in automatically, checked directly via `pip show`).

**The game runs elevated (as Administrator).** Windows blocks synthetic input from a
lower-integrity process to a higher-integrity window (UIPI), so any script that clicks or
presses keys — not pure screenshotting — must run elevated too, via `run_admin.ps1`:
```
powershell -File run_admin.ps1 src\some_script.py [args]
```
This triggers one UAC consent prompt per invocation; there's no way around that, and
scripts here don't try to.

## macOS setup

- `pip install -r requirements.txt` — installs `pyobjc-framework-Quartz` and
  `pyobjc-framework-Cocoa` instead of the Windows-only `pywin32`/`pydirectinput`
  (environment markers in `requirements.txt` pick the right set automatically).
- Grant two permissions **once**, to whichever app runs these scripts (Terminal, iTerm,
  or your IDE) via System Settings → Privacy & Security:
  - **Screen Recording** — needed for `mss` screenshots and to read other apps' window
    titles via Quartz.
  - **Accessibility** — needed to post synthetic clicks/key presses and to activate the
    game's window.

  Unlike Windows' `run_admin.ps1`, there's no per-invocation prompt once these are granted
  — no macOS equivalent of `run_admin.ps1` is needed at all.
- Region boxes are **not portable between platforms** — recalibrate from scratch with
  `calibrate.py` on each. On Windows, boxes are relative to the window's *client area*
  (title bar excluded, via `GetClientRect`); on macOS there's no cheap equivalent query for
  another app's window, so boxes are relative to the **whole window frame, title bar
  included**. Different game build/resolution/UI scaling per platform would have forced a
  recalibration anyway, independent of this difference.

## Windowed, fixed-size only

Fullscreen is explicitly unsupported on both platforms — calibrated pixel boxes are only
meaningful at a fixed, known viewport size, and exclusive fullscreen often isn't
capturable via normal window APIs at all.

Confirmed live during Mac bring-up: even a *windowed* game at a differently-sized window
puts UI elements at different absolute pixel positions — a "resolution" or aspect ratio
matching isn't enough, only an **exact** window content pixel size transfers a calibration.
Windows DPI scaling has the same failure mode (100/125/150/175%, auto-picked per-monitor —
there's no safe universal default to assume). So every module holding calibrated pixel
data (`fingerprints.py`, `ui_layout.py`, `tracker.py`'s region configs) is keyed by
`(platform, exact window content size in pixels)` via `src/display_profiles.py`, and
raises a clear error listing known profiles + your current size/scale if nothing matches,
rather than silently reading the wrong pixels. `calibrate.py shot` prints the exact
`(platform, size)` key to use when adding a new profile. See "Adding a display profile"
below.

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
   clicks during development; `zoom` is what actually gets you a correct coordinate. `shot`
   takes an optional `[delay]` (default 3s) and prints a countdown before it captures —
   `screenshot_window()` requires the game to be the foreground window, but launching `shot`
   from a terminal makes the *terminal* the foreground window, so the delay is your window
   to alt-tab back to the game before the actual capture happens. `zoom` never touches the
   live game at all (it just re-crops the already-saved `calibration_raw.png`), so it needs
   no delay and can be run any time after a `shot`.

2. **Define regions** in a config file (see `config/regions.example.json`):
   ```json
   {
     "window_title": "substring of window title",
     "profiles": [
       {
         "platform": "win32",
         "window_size": null,
         "regions": {
           "gold": {"box": [1690, 100, 1900, 140], "digits_only": true}
         }
       }
     ]
   }
   ```
   Copy it to `config/regions.json` and fill in real boxes/title. One file can hold a
   profile per platform/window-size combination you actually use — `tracker.py` picks the
   one matching the game's current window automatically (see "Adding a display profile").
   `"window_size": null` marks the legacy fallback profile (used when nothing else
   matches); a real profile needs an exact `[width, height]` in pixels, from
   `calibrate.py shot`'s output.

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

5. **Detect which screen is showing** (`src/profiles/fingerprints.py`) — pixel-color fingerprints,
   not OCR. Several UI elements here (the "FLAGSHIP" title, "Trader Era") use a decorative
   font or sit over a watermark graphic that defeats text recognition entirely, but a single
   pixel inside a known letter stroke or background patch is reliably the same color
   whenever that screen is showing.

6. **Send input** (`src/input_control.py`) — building blocks only, not a full bot:
   - `focus_window(hwnd)`, `click(hwnd, x, y)`, `press_key(hwnd, key)`, `drag(hwnd, x1, y1, x2, y2)`
   - Coordinates are relative to the window's client area on Windows, or the whole window
     frame on macOS (see "macOS setup" above) — same frame calibration was done in either way.
   - `input_control.py` is a thin `sys.platform` dispatcher onto
     `src/win/input_control_win.py` (`pydirectinput`, chosen over `pyautogui` because many
     games only respond to DirectInput-style synthetic input) or
     `src/mac/input_control_mac.py` (raw Quartz `CGEvent` posting). Neither backend has a
     real `scroll()` — `drag()` is how every scrollable
     list here is scrolled, as a mouse-down/move/hold-briefly/mouse-up touchscreen-style
     swipe. The brief hold before release matters: releasing the instant the cursor stops
     reads as a flick and the list keeps coasting on momentum afterward, making the actual
     scroll distance inconsistent between calls.
   - Must run elevated on Windows (see above) — the game runs as Administrator. On macOS,
     grant Accessibility once instead (see "macOS setup").

7. **Example feature: reading owned flagships** (`src/flagships.py`) — opens the fleet
   list, pages through the ship detail view (1-4 ships), and OCRs each ship's name with
   `paddle_ocr.py`. Ship/champion names render in a stylized display font
   ("Foundation FP") that both Tesseract and EasyOCR needed workarounds for; PaddleOCR's
   stock recognizer reads it correctly with no fine-tuning, confirmed against real
   captures (see CLAUDE.md).

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

9. **Example feature: reading a ship's equipped components** (`src/component_details.py`)
   — the Component tab has two distinct layouts: a grid of up to 5 icons around the ship
   (no detail panel) right after opening the tab, and a detail view (name/rarity/level,
   stat block, set-bonus text) after clicking one of those icons, with a *different* row
   of 5 thumbnails at the bottom to switch between components without leaving the detail
   view. `read_all_components()` opens the first icon automatically, then pages through
   the rest via that thumbnail row.

10. **Example feature: reading a ship's promotion level** (`src/promotion_details.py`) — the
    Promote tab renders two structurally different layouts depending on state. An unmaxed
    ship (level 0-5) shows a "current → next" comparison row with a badge - a differently
    shaped/colored icon per tier (I-V), or a muted star/cross glyph (no numeral) for level
    0. A maxed ship (level 6) drops that whole row, shifting everything below it up - so
    the same fixed badge box no longer lines up with anything meaningful.
    `read_promotion_level()` checks the PROMOTE/PROMOTED button text first (the one element
    confirmed to sit in the same place in *both* layouts) to detect max, then reads the
    badge via `promotion_badge_ocr.py` - a small model fine-tuned on real captures of this
    icon, since PaddleOCR's stock recognizer misread it as a bare "A" (see
    `ocr_training/generate_promotion_badge_data.py`). Level 0 is detected with a pixel
    brightness check rather than trusting the recognizer to output "nothing" for a
    look-alike icon - a CTC-based OCR model isn't built to abstain, it confidently guesses.

11. **Example feature: collecting every owned flagship's full stats**
    (`src/collect_all_flagships.py`) — opens the fleet list, pages through every owned ship
    (left/right arrows within the ship detail view, not by re-entering the list and
    clicking a card each time - see the module docstring for why that approach was tried
    and abandoned), reads each one's attributes, components, and promotion level, and writes
    `data/attributes/{ship name}.json`
    (`{"ship", "attributes", "validation", "components", "promotion"}`) per real ship -
    locked/not-yet-unlocked ship slots are detected and skipped (see Known gotchas). Run
    directly: `powershell -File run_admin.ps1 src\collect_all_flagships.py`.

## Adding a display profile

Every module holding calibrated pixel data — `src/profiles/fingerprints.py` (screen detection),
`src/profiles/ui_layout.py` (every click/box/drag coordinate used by `nav.py`/`flagships.py`/
`attribute_details.py`/`collect_all_flagships.py`), and `config/regions.json`'s
`profiles` array — is keyed by `(platform, exact window content size in pixels)` via
`src/display_profiles.py`. To add a new one (a different machine, monitor, DPI scaling,
or a second platform):

1. Run `python src/calibrate.py shot "window title"` — it prints the exact profile key
   to use, e.g. `Profile key for this window: ('darwin', (2560, 1656))`, plus a
   display-scale diagnostic (DPI% on Windows, backing scale + "looks like" resolution on
   macOS) for your own reference.
2. Calibrate coordinates the normal way (`calibrate.py zoom`, never eyeballed — see below).
3. Add a new dict entry keyed by that exact tuple to `_LAYOUT_PROFILES` in
   `src/profiles/ui_layout.py`, `_FINGERPRINT_PROFILES` in
   `src/profiles/fingerprints.py`, and a new object in `regions.json`'s
   `profiles` array with that `window_size`.

If the window is later resized, moved to a different DPI setting, or a `regions.json`
without a matching profile is used, every one of these raises a clear error listing known
profiles and the currently detected size/scale — this is deliberate (this repo's core
rule is never guess or mathematically transform a coordinate across sizes, only ever use
one directly confirmed at that exact size).

## Known gotchas (found while testing against a live game)

- **Give text regions vertical margin for descenders — this caused most of our OCR
  failures, not font/engine limitations.** A box cropped tight to what *looks* like a
  line of text (e.g. `y: 10-65`) clips the bottoms of `g/j/p/q/y`, and both Tesseract and
  EasyOCR then misread the whole word ("Opportunity" → "Opportunitv", "Gungnir" → garbage)
  — not because the font is hard, but because part of the glyph is simply gone. Confirmed
  by re-cropping with a taller box (`y: 5-80`): both engines then read every name
  correctly. Before concluding an engine/font can't handle some text, save the crop and
  look at it — if a descender is cut off, that's the bug, not the OCR.
- **Don't hard-threshold/binarize game UI text.** This was a real problem for Tesseract
  (dropped this session, see below) — a fixed-cutoff black/white threshold looked cleaner
  to the eye but destroyed anti-aliased UI fonts' edges. Not applicable to `paddle_ocr.py`/
  `paddle_ocr_blocks.py`, which don't threshold at all; noted here for history.
- **Decorative title fonts defeated both Tesseract and EasyOCR even with a correct box** —
  the "FLAGSHIP" screen title (heavy tracking, gradient fill) read as garbage under every
  Tesseract PSM mode tried, and EasyOCR did about as well (still imperfect: `'FLHecl'`).
  Not yet re-tested against PaddleOCR specifically - this screen is still detected via a
  pixel fingerprint (`fingerprints.py`) rather than OCR'd, which remains the right call
  regardless (only the screen's *presence* is needed, not the title text itself).
- **`screenshot_window()` refuses to capture unless the target window is actually in the
  foreground.** `mss` grabs a screen *region* at the window's last-known coordinates, not
  the window's content directly — if another window (browser, alt-tab) covers that region,
  a naive capture would silently return the wrong thing. `calibrate.py shot` calls
  `focus_window()` itself before capturing, so it handles this automatically; if you call
  `screenshot_window()`/`screenshot_region()` directly (e.g. from a Python shell), bring
  the game window to front yourself first, or call `focus_window(hwnd)` before it.
- **Pick regions that don't scroll/animate.** A region over live chat or a ticker will
  OCR whatever's there *at the instant of capture* — fine for a one-off read, useless for
  a stable "current value" reading. Point regions at static HUD elements (resource
  counters, health bars, etc.), not scrolling panels.
- Client-area capture (`win32gui.GetClientRect` + `ClientToScreen`, in
  `src/win/capture_win.py`) excludes the title bar automatically, so pixel coordinates in
  `calibrate.py` output line up directly with `regions.json` boxes. macOS has no
  equivalent client-rect-only query for another app's window, so `src/mac/capture_mac.py`
  works against the whole window frame instead — boxes calibrated on Mac include the
  title bar's height as an offset; this is just a different, equally consistent frame,
  not a bug.
- **DPI/scale awareness must be handled before any window-coordinate query or `mss`
  capture, on both platforms.** On Windows, `src/win/capture_win.py` sets DPI awareness
  at import time — without it, this process is DPI-unaware and `win32gui` returns
  coordinates in a virtualized logical-pixel space that doesn't match the physical
  pixels `mss`/`SetCursorPos` use on a scaled display, silently misaligning every
  screenshot and click by the scale factor (e.g. 1.25x at 125% scaling). On macOS, the
  equivalent issue is Retina backing scale: `CGWindowListCopyWindowInfo` bounds come back
  in points, while `mss` and `CGEventPost` expect physical pixels and points respectively
  — `src/mac/capture_mac.py`/`src/mac/input_control_mac.py` convert via
  `NSScreen.backingScaleFactor()` at every boundary crossing. Don't "simplify away"
  either conversion.
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
- **Paging between ships with the side arrows does not reset which tab (Overview/Component/
  Promote) is active.** Whichever tab was showing for the previous ship stays showing for
  the next one. `collect_all_flagships.py` explicitly clicks the Overview tab at the start
  of every iteration rather than assuming it - true for ship 1 (freshly opened from the
  fleet list) but not ship 2 onward (arrived at via the arrows, still on whatever tab the
  previous ship ended on).
- **`back()` only closes one level, and "one level" means something different depending on
  which sub-view you're in.** From a component's detail view, one `back()` lands on the
  Component tab's own grid-of-5-icons view - not Overview, not the fleet list. Don't assume
  a fixed number of `back()` calls reaches a given destination without confirming from the
  specific state you're actually leaving.
- **A direct "is this badge present" check is much cheaper than "did the expensive read
  come back empty."** Detecting
  a locked/not-yet-unlocked ship slot by checking `read_attribute_details()` for an empty
  result works, but wastes a full failed scroll-and-OCR pass on every locked slot.
  Checking for the "Level NN" badge on the Overview tab first (present only on real,
  unlocked ships - confirmed by the user directly) catches the same case for the cost of
  one small OCR call. This game's UI uses that same locked-vs-unlocked metaphor broadly:
  locked items are still viewable, just rendered without the labels/badges an unlocked one
  gets, rather than being hidden entirely - worth checking for an equivalent badge before
  assuming "empty result = not real" elsewhere in the UI.
- **A short badge like "Level NN" can need a different PSM mode than the multi-line blocks
  elsewhere in this codebase.** `--psm 6` (the usual default for stat blocks) read this
  specific badge as empty every time despite the crop being visibly correct; `--psm 11`
  (sparse text) read it reliably. The word "Level" itself still didn't come through even
  with 11 - only the digits did, which was enough for a presence check.
- **Recalibrating coordinates from a saved reference image only works if that image is
  actually current.** A batch of `component_details.py`'s boxes were originally derived
  from crops of `calibration_raw.png` without first confirming a fresh `shot` had just been
  taken - the file still held an older screenshot, and every box came out wrong by
  150-450px as a result, in a way that looked at first like ordinary miscalibration.
  Confirmed by comparing pixel values directly between the "reference" and a genuinely
  fresh shot. Always take (or explicitly confirm the freshness of) the screenshot you're
  about to crop from, not just trust a filename.
- **Disabling Windows UAC prompts does not mean scripts run elevated.** With UAC prompts
  disabled system-wide, `run_admin.ps1`'s elevation request goes through silently (no
  visible consent dialog), but a plain, non-elevated `python.exe` invocation still cannot
  reach the (elevated) game at all - confirmed directly (`IsInRole(Administrator)` false,
  and clicks/keys silently not landing). Elevation still has to actually happen per
  process; UAC being disabled just removes the prompt from that process, not the
  requirement for the process to be elevated in the first place.
- **A UI element can move between two states of the same screen, breaking a fixed
  calibrated box for one of them.** `promotion_details.py`'s Promote tab reads the current
  level off a badge, but a maxed ship's layout drops an entire progress row that a
  non-maxed ship shows above that badge - shifting everything below it (including the
  badge itself) to a different position. A box calibrated against a level-1-5 ship simply
  doesn't contain the badge at all once a ship is maxed; it wasn't a case of "OCR misread
  the icon" but "the icon isn't in this box on this screen." Confirmed by capturing real
  screenshots of a level-0 ship, a level-I ship, and a maxed ship and comparing the actual
  panel layouts, not by assuming one screen's coordinates generalize to a related one.
  Fixed by finding a *different* element (the PROMOTE/PROMOTED button) confirmed to sit in
  the same place in both layouts, and reading that instead for the one distinction (max vs
  not) that the moved badge could no longer make reliably.
- **`calibrate.py shot` stealing focus made it unusable for calibrating a screen you need
  to keep visible.** Its foreground-window check is correct and load-bearing (see the
  gotcha above about `screenshot_window()`), but running `shot` from a terminal makes the
  *terminal* the foreground window at the exact moment it's about to capture, so it always
  failed against a screen you'd just switched to. Fixed by adding an optional countdown
  delay (default 3s) before the actual capture, giving time to alt-tab back to the game
  after launching the command - `zoom` needed no such fix since it only re-crops an
  already-saved file and never touches the live game.

## Next steps to consider

- For numeric-only stats, `tracker.py`'s `digits_only: true` now does a regex post-filter
  on `paddle_ocr.py`'s output rather than a Tesseract character whitelist (which PaddleOCR
  has no equivalent of per-call) - same effect, different mechanism.
- **Default to `paddle_ocr.py` (single-line) / `paddle_ocr_blocks.py` (multi-line) for new
  regions.** Confirmed this session across every field checked in this codebase that
  PaddleOCR's stock recognizer matches or beats both Tesseract and EasyOCR, including
  stylized fonts that used to need EasyOCR as a workaround. Reach for a dedicated
  fine-tuned model (see `ocr_training/`, `orange_kid_ocr.py`, `promotion_badge_ocr.py`)
  only after confirming a correctly-sized box still fails on stock PaddleOCR - so far
  that's only been true for two small custom game icons the stock recognizer
  misinterpreted as different characters/letters entirely (not a resolution issue).
- Only 3 of ~7 catalogued screens (`system_map`, `fleet_list`, `city_view`) have pixel
  fingerprints in `fingerprints.py`. `storage`, `champion`, `guild`, `radiant`, and `chat`
  are wired into `nav.py`'s key mappings but `goto()` can't verify arrival for them yet.
- `collect_all_flagships.py` occasionally captures 11 of a ship's 12 stat sections instead
  of 12 - the twelfth ("Chance to inflict Major Damage") sometimes only gets its `_total`
  without sub-rows on a given run. Not corrupted data, just incomplete for that one field;
  a retry-on-incomplete-section pass would close this gap if it matters for a given use.
