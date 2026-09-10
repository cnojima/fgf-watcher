# Packaging as a standalone application

Not started — revisit once the app itself is feature-complete. This captures what
packaging into a self-executable would require on each platform, based on how the
codebase is actually structured today.

## Shared blockers (both platforms)

- **Tesseract is an external binary, not a Python dependency.** `ocr.py` shells out to
  `tesseract.exe`/`tesseract` (`shutil.which("tesseract")`, falling back to the
  UB-Mannheim Windows install path). Packaging either bundles the Tesseract binary +
  language data (~50-80MB) alongside the app, or keeps it as a one-time separate install
  the user does themselves (`brew install tesseract` / the Windows installer).
- **EasyOCR pulls in PyTorch.** Used only for ship-name text (`ocr_easy.py`). PyTorch is
  hundreds of MB, and EasyOCR downloads its detection/recognition models to
  `~/.EasyOCR` on first use — bundling means a much larger app; not bundling means the
  packaged app needs network access on first run. Worth deciding whether this one OCR
  call is worth the weight, or should move to Tesseract instead.
- **Hardcoded relative data paths.** Several modules resolve `data/` and `src/icons/`
  via `Path(__file__).resolve().parent...` (`tracker.py`, `icon_match.py`,
  `collect_all_flagships.py`, `attribute_details.py`, `component_details.py`,
  `calibrate.py`, `logging_setup.py`). Under a frozen build these need to split into:
  read-only bundled assets (icons) resolved via the packaging tool's bundle-relative
  path, and writable output (`data/attributes/*.json`, `app.log`) resolved to a
  proper per-user writable location instead of a path next to the source tree.
- **No single entry point.** Today this is several standalone scripts
  (`tracker.py`, `calibrate.py`, `collect_all_flagships.py`), each with its own
  `if __name__ == "__main__"`. Packaging needs either a small CLI dispatcher, a minimal
  GUI, or one built executable per script.

## Windows

- **Elevation**: the game runs as Administrator, so all input-driving code needs to run
  elevated too (see CLAUDE.md - UIPI blocks synthetic input across integrity levels).
  Today that's `run_admin.ps1`'s `Start-Process -Verb RunAs`, re-triggering a UAC prompt
  per script invocation, plus a `-WindowStyle Hidden` workaround so the console doesn't
  render on top of the game. A packaged exe can embed a `requireAdministrator` manifest
  (PyInstaller's `--uac-admin`) instead — one clean UAC prompt at launch, and the hidden
  console hack goes away since the build's console mode is controlled directly.
- **Recommended tool**: PyInstaller with `--uac-admin`.

## macOS

- No Windows-style elevation, but screen capture and synthetic input are gated behind
  **per-app TCC permissions** instead — the macOS analogue of the UIPI problem:
  - **Screen Recording** — required for `CGWindowListCopyWindowInfo`/`mss.grab()`
    (`capture_mac.py`) to see window content instead of a black image.
  - **Accessibility** — required for `CGEventPost` synthetic clicks/keys
    (`input_control_mac.py`) to reach another app.
  - **Automation** — `focus_window()` shells out to `osascript ... activate`
    (`input_control_mac.py`), which needs per-target-app Automation consent.
  - All three are tied to the *exact signed binary*, not "Python" in general. They're
    presumably currently granted to Terminal/the dev's IDE. A packaged `.app` is a new
    identity to macOS: all three prompts fire again on first launch, and an unsigned,
    unnotarized app may not cleanly be able to request them at all (Gatekeeper
    quarantine) unless self-signed with a local dev cert (fine for personal use, still
    needs a one-time right-click-Open bypass) or properly notarized with an Apple
    Developer ID (needed to run on a machine other than the one that built it).
  - Unlike Windows' `--uac-admin`, there's no way to script past these prompts — a user
    grants each once manually, and rebuilding without stable code signing invalidates
    the grant.
- pyobjc frameworks (PyObjC, AppKit, Quartz) add real bundle size on top of whatever
  packaging tool is used.
- **Recommended tool**: `py2app` over PyInstaller — it's the macOS-native bundler and
  handles the `.app`/`Info.plist` more naturally, which is needed anyway to carry the
  usage-description strings the TCC prompts display.
