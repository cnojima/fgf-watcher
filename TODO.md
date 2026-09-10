# TODO

Future considerations, not yet scheduled or committed to.

## If this app is ever distributed: package as a signed .app bundle

Currently every tool here runs as a loose script (`python src/foo.py`), so
macOS's Screen Recording/Accessibility permissions get attributed to whatever
terminal app happens to spawn `python` (Terminal.app, iTerm2, VS Code, ...) —
confirmed directly: the same command returned an empty window list in iTerm2
until Screen Recording was granted to iTerm2 specifically, separately from
VS Code already having it. That's fine for solo dev use (grant it once per
terminal you use), but doesn't hold up for distribution to other people.

**If distributed, requirements would be:**
- Package as a proper signed `.app` bundle (e.g. PyInstaller `--windowed
  --onedir`, or `py2app`) with a stable bundle identifier, so Screen
  Recording/Accessibility grants attach to the app's own identity instead of
  the ambient terminal — and so users grant permissions once, to one
  recognizable app, rather than needing to know this per-terminal-app gotcha
  themselves.
- Bundle the Python runtime + all deps into that build — EasyOCR's `torch`
  dependency in particular makes this a large bundle; worth checking whether
  the `ocr_easy.py` fallback path is used often enough in practice to justify
  shipping it, or whether it could become an optional/lazy download instead.
- Developer ID code signing + notarization, not just ad-hoc signing — an
  ad-hoc/unsigned build can get a new TCC identity on every rebuild, forcing
  every user to re-grant permissions after every update.
- Re-verify the whole macOS backend (`src/mac/capture_mac.py`,
  `src/mac/input_control_mac.py`) still behaves the same way when run from
  inside an app bundle instead of a terminal-spawned script — window
  enumeration/CGEvent posting should be identical, but this hasn't actually
  been tested that way yet.
- Windows side would need the equivalent: today `run_admin.ps1` triggers a
  UAC prompt per invocation, which is fine for personal use but a rough user
  experience for distribution — likely wants a proper installed/signed
  executable requesting elevation via an embedded manifest instead.
