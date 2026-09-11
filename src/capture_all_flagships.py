"""Capture flagship screens for later, offline OCR replay.

This phase performs navigation and input only. The saved full-window frames are
the source of truth for OCR tuning; replay code can recrop them repeatedly.
"""
import argparse
import logging
import sys
import time
from pathlib import Path

import paddle_ocr
from capture import find_window, screenshot_region, screenshot_window
from capture_run import CaptureRun
from collect_all_flagships import MAX_SHIPS
from input_control import click, focus_window, press_key
from logging_setup import configure_logging
from nav import back, goto
from profiles.fingerprints import current_screen
from profiles.ui_layout import get_layout, require_field

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "captures"


def _save(run, hwnd, layout, name, kind, ship_index, sequence=0):
    relative = f"ship-{ship_index:03d}/{name}-{sequence:03d}.png"
    return run.save_image(
        screenshot_window(hwnd), relative, kind=kind,
        ship_index=ship_index, sequence=sequence,
    )


def _capture_attribute_frames(run, hwnd, layout, ship_index):
    click(hwnd, *layout.overview_tab)
    time.sleep(0.2)
    click(hwnd, *layout.hamburger_icon)
    time.sleep(0.2)
    click(hwnd, *layout.details_tab)
    time.sleep(0.2)

    for sequence in range(46):
        _save(run, hwnd, layout, "attribute", "attribute", ship_index, sequence)
        if sequence == 45:
            log.warning("Attribute capture reached maximum frame count")
            break
        from scroll_stitch import content_offset

        before = screenshot_region(hwnd, layout.table_box)
        # The next screenshot is saved before measuring movement, so the
        # replay has exactly the same frames as the live run.
        from input_control import drag
        drag(hwnd, *layout.drag_from, *layout.drag_to)
        time.sleep(0.7)
        after = screenshot_region(hwnd, layout.table_box)
        offset = content_offset(
            before, after, layout.table_tab_bar_height,
            layout.expected_scroll_offset,
        )
        if offset <= 5:
            break

    press_key(hwnd, "esc")
    time.sleep(0.2)


def capture_all_flagships(hwnd, output: Path) -> Path:
    run = CaptureRun(output)
    layout = get_layout(hwnd)
    focus_window(hwnd)

    for _ in range(3):
        if current_screen(hwnd) in ("system_map", "city_view"):
            break
        back(hwnd)
        time.sleep(0.2)

    goto(hwnd, "fleet_list")
    click(hwnd, *layout.first_card_click)
    time.sleep(0.6)

    seen_names: set[str] = set()
    for ship_index in range(MAX_SHIPS):
        _save(run, hwnd, layout, "overview", "overview", ship_index)
        name = paddle_ocr.read_text(screenshot_region(hwnd, layout.name_box))
        if not name:
            time.sleep(0.3)
            name = paddle_ocr.read_text(screenshot_region(hwnd, layout.name_box))
        if not name:
            log.warning("Ship %d has no readable name; stopping capture", ship_index)
            break
        if name in seen_names:
            log.debug("Ship name %r already seen - wrapped around fleet list", name)
            break
        seen_names.add(name)

        click(hwnd, *layout.overview_tab)
        time.sleep(0.6)
        _save(run, hwnd, layout, "overview-ready", "overview-ready", ship_index)
        level_text = paddle_ocr.read_text(screenshot_region(hwnd, layout.level_badge_box))
        if not any(char.isdigit() for char in level_text):
            log.info("%s appears locked; stopping capture", name)
            break

        _capture_attribute_frames(run, hwnd, layout, ship_index)

        click(hwnd, *layout.component_tab)
        time.sleep(0.2)
        _save(run, hwnd, layout, "component-grid", "component-grid", ship_index)
        click(hwnd, *require_field(layout.first_grid_icon, "first_grid_icon"))
        time.sleep(0.2)
        for component_index, position in enumerate(require_field(layout.thumbnail_positions, "thumbnail_positions")):
            click(hwnd, *position)
            time.sleep(0.2)
            _save(run, hwnd, layout, f"component-{component_index:03d}", "component", ship_index, component_index)

        back(hwnd)
        time.sleep(0.2)
        click(hwnd, *layout.promote_tab)
        time.sleep(0.2)
        _save(run, hwnd, layout, "promotion", "promotion", ship_index)

        click(hwnd, *layout.right_arrow)
        time.sleep(0.6)

    if not run.frames:
        raise RuntimeError("Capture produced no frames")
    run.write_manifest(
        platform=sys.platform,
        window_size=[run.frames[0]["width"], run.frames[0]["height"]],
    )
    return run.root / "manifest.json"


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Capture every owned flagship's screens (overview, attribute details, "
            "components, promotion) as full-window PNG frames plus a manifest, for "
            "offline OCR replay via replay_all_flagships.py. Navigation and input "
            "only - no OCR happens during capture."
        ),
    )
    parser.add_argument(
        "output", type=Path, nargs="?", default=None,
        help=f"directory to write the capture run to (default: {DATA_DIR}/<timestamp>)",
    )
    args = parser.parse_args()
    output = args.output or DATA_DIR / time.strftime("%Y%m%d-%H%M%S")
    configure_logging()
    hwnd = find_window()
    start = time.monotonic()
    manifest = capture_all_flagships(hwnd, output)
    log.info("Capture manifest: %s (%.1fs)", manifest, time.monotonic() - start)


if __name__ == "__main__":
    main()