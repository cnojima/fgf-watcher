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

## This game runs elevated (Administrator)

Windows blocks synthetic input from a lower-integrity process to a higher-integrity window
(UIPI). Any script that calls `click()`/`press_key()` must run via `run_admin.ps1`
(triggers one UAC prompt per invocation — there's no way around that, don't try). Pure
screenshotting/OCR does not need elevation.

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
