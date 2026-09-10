# USAGE

Quick reference for the tools in this repo. For setup/install steps see
[README.md](README.md); for the design reasoning behind how these work see
[CLAUDE.md](CLAUDE.md).

All commands are run from the repo root. On Windows, any command that clicks
or presses keys (not pure screenshotting) must run elevated via
`run_admin.ps1` (see below) — the game runs as Administrator. On macOS, grant
Screen Recording + Accessibility once to your terminal (see README's "macOS
setup") — no per-run elevation needed.

**The Screen Recording grant is per terminal *app*, not global or per-user.**
If `calibrate.py list`/`shot` runs without error but returns an empty window
list, that's not a bug — it means the specific app you're running the command
from (Terminal.app, iTerm2, VS Code, ...) hasn't been granted Screen Recording
yet: macOS still returns window entries without it, but blanks out every
other process's window title, and `list_windows()` filters out blank titles.
Fix: System Settings → Privacy & Security → Screen Recording → enable that
exact app (add it with **+** if it's not listed) → **fully quit and relaunch
it** (⌘Q, not just closing the window — a new grant only takes effect after
the app restarts) → retry.


## Activate the Python env first

```
source /Users/curisu/dev/fgf-watcher/.venv/bin/activate
```

**Required on macOS** — an unqualified `python` typically resolves to the
system's ancient `/usr/local/bin/python` (Python 2.7), which can't even parse
this codebase (fails with `SyntaxError` on the first `-> str` return
annotation it hits, not a real bug). Activating the venv puts its Python 3.14
first on `PATH`. If you don't have a `.venv` yet: `python3 -m venv .venv &&
source .venv/bin/activate && pip install -r requirements.txt`.


## Current platform status

| Tool | Windows | macOS |
|---|---|---|
| `calibrate.py` | ✅ works | ✅ works |
| `tracker.py` | ✅ works (legacy fallback profile) | ⚠️ needs a calibrated region profile in your config |
| `collect_all_flagships.py` | ✅ works (legacy fallback profile) | ⚠️ needs a calibrated `UILayout`/fingerprint profile |

"Needs a calibrated profile" means the tool will fail immediately with a
clear error (listing what it detected vs. what's known) rather than silently
reading/clicking the wrong pixels — see "Adding a display profile" in
README.md.

---

## 1. `calibrate.py` — find your window and confirm pixel coordinates

```
python src/calibrate.py list
python src/calibrate.py shot "substring of window title"
python src/calibrate.py zoom X Y [radius] [source]
```

- **`list`** — prints the title of every visible top-level window, so you can
  find the exact substring to target.
- **`shot "title"`** — screenshots that window, saves a 50px-gridded
  `data/calibration.png` (for reading off approximate coordinates) and an
  ungridded `data/calibration_raw.png`, and prints:
  - the exact `(platform, (width, height))` profile key for this window —
    copy this when adding a new profile to `src/profiles/ui_layout.py`/
    `src/profiles/fingerprints.py`/a region config;
  - a display-scale diagnostic (Windows DPI% or macOS Retina/"looks like"
    resolution) for your own reference.
- **`zoom X Y [radius] [source]`** — crops a 10px-gridded close-up around
  `(X, Y)` from the last `shot` (or `source`, a specific PNG path) into
  `data/zoom.png`. **Always confirm a coordinate this way before clicking
  it** — reading positions off the full downscaled screenshot is the single
  biggest source of wrong clicks in this project's history.

`shot` brings the game to the foreground itself before capturing (via
`focus_window()`), so you don't have to manually switch to it first — this
means `shot` now goes through the same window-activation path as
click()/press_key(), which on Windows may require running via
`run_admin.ps1` if the game (elevated as Administrator) refuses a
non-elevated `SetForegroundWindow` call — not yet confirmed live. If `shot`
fails oddly on Windows, try `powershell -File run_admin.ps1 src\calibrate.py
shot "window title"`.
macOS: `python src/calibrate.py shot "Galactic Frontier"` — no elevation
concept, confirmed working without manually switching windows first.

## 2. `tracker.py` — poll region values and log changes

```
python src/tracker.py config/regions.json
```

Loads a region config (see `config/regions.example.json` for the schema —
`window_title` + a `profiles` array keyed by platform/window size), finds the
matching profile for the game's current window, then polls every named
region on a 2-second interval, OCRs it, and appends a row to `data/log.csv`
(`timestamp, region, value`) whenever a value changes. Runs until Ctrl+C.

Windows: `powershell -File run_admin.ps1 src\tracker.py config\regions.json`
only needed if you also want to drive input elsewhere in the same session —
`tracker.py` itself only screenshots, so it doesn't require elevation on its
own.

## 3. `collect_all_flagships.py` — full stat capture for every owned ship

```
python src/collect_all_flagships.py
```

No arguments — the window title and all UI coordinates come from
`ui_layout.get_layout()`/hardcoded constants, not a config file. Opens the
fleet list, pages through all 1-4 owned ships via the ship detail view's
left/right arrows, runs the full "Attribute Details" scroll-and-OCR capture
on each one (`attribute_details.read_attribute_details()`), cross-validates
and self-heals each section's total against its own sub-row math, and writes
one `data/attributes/{ship name}.json` per ship
(`{"ship", "attributes", "validation"}`). Prints a summary of how many ships
were collected when done.

Windows: `powershell -File run_admin.ps1 src\collect_all_flagships.py`
(clicks/drags require elevation).
macOS: `python src/collect_all_flagships.py` (after granting Accessibility).

### Related library modules (no standalone CLI)

These are called by `collect_all_flagships.py` (or usable interactively from
a Python shell with `hwnd = capture.find_window(...)`), not run directly:

- **`flagships.read_owned_flagships(hwnd)`** — just the ship *names* (no
  stats), by paging through the fleet list the same way.
- **`attribute_details.read_attribute_details(hwnd)`** — one ship's full stat
  breakdown; assumes you're already on that ship's detail view.
- **`nav.goto(hwnd, screen_name)` / `nav.back(hwnd)`** — menu navigation
  building blocks (`fingerprints.py` verifies arrival where a fingerprint is
  catalogued).
- **`fingerprints.current_screen(hwnd)`** — which catalogued screen (if any)
  is currently showing, by pixel-color fingerprint.

## Troubleshooting: "No game window matching '...' found"

Means the window-title substring search came up empty at the moment the tool
ran. Before assuming the title string is wrong, check whether the game
itself was actually visible on the current screen right then — this error
fires the same way whether the game isn't running, is minimized, or (macOS
only) is in fullscreen or on a different virtual desktop/Space, since none of
those are visible to on-screen window enumeration. Bring the game to the
foreground on your current Space/desktop in windowed mode, then retry.

## Adding a new display profile

If `tracker.py` or `collect_all_flagships.py` raises "No calibrated ... for
this window" (expected today on macOS, and on any Windows machine/monitor
that isn't the original 125%-scaled setup), see "Adding a display profile" in
[README.md](README.md) — run `calibrate.py shot` for the exact profile key,
confirm coordinates with `zoom`, and add entries to `src/profiles/ui_layout.py` /
`src/profiles/fingerprints.py` / your region config.
