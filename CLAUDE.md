# CLAUDE.md

Guidance for Claude Code sessions working in this repo. See [README.md](README.md) for
setup and usage — this file is about *how* to work here, based on mistakes already made
and fixed during development.

## When OCR misreads something: capture evidence before tuning anything

Don't guess at preprocessing tweaks (threshold, upscale, PSM mode) blind. Save the exact
crop that was OCR'd and look at it, alongside the mistaken output:

```python
crop = screenshot_region(hwnd, box)
crop.save("data/_debug_ocr_fail.png")
print(f"misread: {read_text(crop)!r}")
```

Then actually read the saved image before changing code. Every OCR failure investigated
this session turned out to be a bug in the crop itself, not an engine/font limitation:

- A box cropped to `y: 10-65` clipped the descenders off `g/j/p/q/y` — "Opportunity" read
  as "Opportunitv", "Gungnir" came back garbled. Widening to `y: 5-80` fixed both engines
  (Tesseract *and* EasyOCR) instantly. This was mistaken for a font-rendering limitation
  and nearly caused a switch to a much heavier OCR engine for no reason.
- The one *genuine* font limitation found (the "FLAGSHIP" screen title — heavy tracking,
  gradient fill) was confirmed by inspecting a correctly-bounded crop that still read as
  garbage under every PSM mode and both engines. That's the bar for calling something an
  engine/font limit rather than a cropping bug: the crop has to be visibly correct first.

## Never click a coordinate estimated by eye

Read off an approximate position from `python src/calibrate.py shot`, then **always**
confirm with `python src/calibrate.py zoom X Y [radius]` before clicking or defining a box.
Eyeballing position on the full downscaled screenshot was the single biggest source of
wasted effort during development — wrong clicks, empty crops, misjudged coordinates by
100-400px more than once, including guessing "roughly the same spot" between two different
screens that turned out to differ by hundreds of pixels.

- **A whole batch of `component_details.py`'s boxes were once derived from a stale
  reference image** — `calibrate.py zoom` was run against an old `calibration_raw.png`
  without first confirming a fresh `shot` had actually been taken against the current
  screen. Every box came out wrong by 150-450px, in a way that looked like ordinary
  miscalibration error rather than "wrong source image entirely" until the pixel values
  were compared directly against a genuinely fresh shot. Confirm the screenshot you're
  about to `zoom` into is actually current, not just present.
- **`calibrate.py shot` needs the game to be the foreground window at the moment it
  captures, but running it from a terminal makes the terminal foreground instead** — this
  isn't a bug to work around, it's `screenshot_window()`'s own foreground check (see
  "Other load-bearing fixes" below) doing its job. `shot` now takes an optional `[delay]`
  (default 3s) and prints a countdown before capturing, so there's a window to alt-tab back
  to the game first. `zoom` never touches the live game (it only re-crops the already-saved
  `calibration_raw.png`), so it never needed this and can be run anytime after a `shot`.

## This game runs elevated (Administrator)

Windows blocks synthetic input from a lower-integrity process to a higher-integrity window
(UIPI). Any script that calls `click()`/`press_key()` must run via `run_admin.ps1`
(triggers one UAC prompt per invocation — there's no way around that, don't try). Pure
screenshotting/OCR does not need elevation.

**Disabling Windows' UAC consent prompts does not remove this requirement — it only
removes the dialog.** With prompts disabled system-wide, `run_admin.ps1`'s elevation
request goes through silently, but a plain, non-elevated `python.exe` invocation still
cannot reach the (elevated) game at all — confirmed directly (`IsInRole(Administrator)`
came back `False` for it, and its clicks/keys silently didn't land, no error raised).
Every script that clicks or presses keys still needs to actually run from an elevated
process, UAC prompt or not.

## Scrolling and merging multi-capture data: lessons from `attribute_details.py`

Reading a scrollable list (more content than fits in one screenshot) took many iterations
to get right. In rough order of what actually mattered:

- **This game's lists scroll only via click-drag-hold-release, never a scroll wheel or
  keys.** `pydirectinput` has no `scroll()` at all (no `MOUSEEVENTF_WHEEL` wrapper) - use
  `input_control.drag()` (mouseDown, move through intermediate points, hold briefly, then
  mouseUp) as a touchscreen swipe-up.
- **When measuring scroll distance by comparing pixels between two captures, exclude any
  static UI chrome from the compared region.** A comparison strip that included this
  modal's fixed "Overview/Details" tab bar always scored a "perfect match" at offset=0
  regardless of how far the actual list content had moved, because that chrome never
  changes - making the scroll mechanism look completely broken (10 drags in a row measured
  as zero movement) when it was working fine. Confirmed by saving the raw crop and looking
  at what was actually being compared, not by re-tuning the drag itself.
- **Merging OCR *text* across multiple overlapping captures is fragile in a way that's very
  hard to fix by tuning scroll distance.** Every value influences two failure modes at
  once: too little overlap between captures loses rows outright (never fully visible in
  any single capture); too much overlap means the same row can resurface many captures
  after its own section header was last seen, and simple "carry the current section
  forward" state gets confidently wrong (attributes it to whatever section was *most
  recently* seen, not the one the row actually belongs to). No single distance satisfies
  both. **The fix that actually worked was to stop merging text and stitch the *images*
  instead**: align each new capture against the previous one by actual pixel content
  (`_content_offset`, not the requested drag distance - touch-scroll physics doesn't
  guarantee that distance exactly), splice only the genuinely new slice onto one growing
  composite, and OCR the whole thing exactly once. With no cross-capture merge step,
  cross-capture misattribution isn't possible by construction.
- **A parsing regex that requires the *entire* line to be clean fails completely on a
  single stray OCR character, not just partially.** `"ATTACK 23,725"` misread as
  `"ATTACK 23,/25"` (one digit swapped for a symbol) made the whole line fail to match
  when the pattern required no digits after the number - silently dropping the entire row,
  including section headers, whose sub-rows then fell through to whichever section was
  previously active. Match the value as the first plausible number token and ignore
  whatever comes after, rather than anchoring to end-of-line.
- **When a field is redundantly determined by other fields, use that redundancy to correct
  OCR errors, not just detect them.** A section's header total equals a known function of
  its own sub-rows (confirmed against the game's real numbers by the user directly - see
  `validate_sections`'s docstring for the formula). When the sub-rows were read correctly
  but the header's own total was misread (a single wrong digit, or a symbol substitution
  truncating it), `heal_totals` replaces the total with the value computed from the
  sub-rows rather than leaving the known-wrong OCR'd number in place - confirmed correct by
  cross-checking the healed value against a direct screenshot of the real total twice.

## Paging between ships: lessons from `collect_all_flagships.py`

- **Paging with the side arrows does not reset which tab is active.** Whichever of
  Overview/Component/Promote was showing for the previous ship is still showing after
  arrow-paging to the next one. Confirmed live — assumed otherwise at first, which caused
  a real navigation bug (reading the wrong tab's content for ship 2 onward, since only
  ship 1 was freshly opened from the fleet list and actually started on Overview). Fixed
  by explicitly clicking the target tab at the start of every per-ship read rather than
  assuming a starting state.
- **`back()` closes one level, but "one level" depends on which sub-view you're actually
  in — don't assume a fixed depth without confirming from the specific state you're
  leaving.** From a component's *detail* view (opened by clicking one of the 5 equipped-
  component icons), one `back()` lands on the Component tab's own grid-of-5-icons view —
  not Overview, not the fleet list. This was corrected mid-session: it was first reported
  as needing two `back()` calls, then corrected to one once the actual landing screen
  (the grid, not the fleet list) was identified directly.
- **This game's "locked but still viewable" UI metaphor shows up repeatedly — check for a
  presence/absence signal specific to that pattern before assuming an empty read means "not
  real."** A locked/not-yet-unlocked ship slot renders a full Overview tab (ship model,
  stat panel) but *without* the "Level NN" badge an unlocked ship gets — confirmed directly
  by the user, who named this as the general pattern behind multiple parts of this UI, not
  a one-off. Checking for that badge's presence is both more correct and far cheaper than
  detecting a locked slot by noticing `read_attribute_details()` came back empty, which
  wastes a full scroll-and-OCR pass on every locked slot before finding out.
- **A short badge can need a different PSM mode than the multi-line stat blocks elsewhere
  in this codebase.** The "Level NN" badge above came back empty under `--psm 6` (this
  codebase's usual default) every time, despite the crop being visibly correct; `--psm 11`
  (sparse text) read it reliably. Even at 11, the word "Level" itself still didn't
  reliably come through — only the digits did, which was enough for a presence check. If a
  correctly-cropped short/isolated piece of text reads empty, try a different PSM before
  assuming the crop is wrong (see "capture evidence before tuning anything" above — this
  is the one case so far where the fix genuinely was a preprocessing/engine setting, not
  the crop).

## One screen can have two structurally different layouts: lessons from `promotion_details.py`

The Promote tab's current-level badge is calibrated against a *fixed box* — this works for
a ship that can still be promoted (levels 0-5), but completely breaks for a maxed ship
(level 6), because the maxed layout drops an entire "current → next" progress row that a
non-maxed ship shows above the badge. Removing that row shifts everything below it —
*including the badge itself* — to a different position. A box confirmed correct against a
level-0 or level-I ship simply doesn't contain the badge at all once a ship is maxed.

This was not an OCR problem (no misread, no wrong PSM) — it was "the icon isn't in this box
on this screen," which looks identical to an OCR failure (empty string back) until you
actually compare full screenshots of both layouts side by side. Confirmed by capturing real
reference screenshots of a level-0 ship, a level-I ship, and a maxed ship, rather than
assuming a box calibrated on one ship's Promote tab generalizes to every ship's.

**The fix: find a different element that's confirmed to occupy the same position in both
layouts, and read that instead for the distinction the moved element could no longer
make.** Here, the PROMOTE/PROMOTED button sits in the same place whether a ship is maxed or
not (only its text and enabled/disabled styling change) — so `read_promotion_level()` reads
the numeral badge first (covers levels 0-5), and only falls back to OCRing the button text
("PROMOTED" vs "PROMOTE") to tell level 0 apart from level 6, since the badge alone can't
make that distinction once it's moved out from under a fixed box. More generally: before
assuming a badge/box calibrated on one state of a screen also applies to a visually or
functionally distinct state of the *same* screen (not-maxed vs. maxed, locked vs. unlocked,
etc.), get a real reference screenshot of that other state first.

## Other load-bearing fixes already in place — don't undo them

- `capture.py` sets per-monitor DPI awareness at import time. Without it, `win32gui`
  coordinates land in a virtualized logical-pixel space that doesn't match the physical
  pixels `mss`/`SetCursorPos` use on a scaled display — silently misaligns every capture
  and click by the scale factor.
- `screenshot_window()` refuses to capture unless the target window is actually the
  foreground window. `mss` grabs a screen *region*, not the window's content directly, so
  an occluded/alt-tabbed-away window would otherwise silently return whatever's covering
  it instead of raising an error.
- `ocr.py`'s `preprocess()` does **not** binarize/threshold by default. It looks cleaner to
  a human eye but destroys anti-aliased UI text for OCR. Only pass `threshold=` after
  confirming it measurably helps a specific noisy-background region.
- `nav.py` never uses ESC for closing overlays or resetting state, even though it looks
  like the obvious "back" key. It's "Quit game" from a base view, and per a known game bug
  can also trigger a full quit from certain overlays instead of closing just that overlay.
  Use `back(hwnd)` (clicks the on-screen back arrow) instead.
- `run_admin.ps1` launches the elevated Python process with `-WindowStyle Hidden`.
  Without it, Windows shows a visible console window for the elevated `python.exe` (it's a
  console app) that can render on top of the game - it's a fresh window and topmost when
  it spawns - and intercept clicks/drags meant for the game underneath it, degrading
  results (fewer sections captured, garbled data) without raising any error, since the
  game itself was still technically the foreground window. Confirmed by the user directly
  observing the console overlapping the game on screen.
