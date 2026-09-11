"""Replay a flagship capture directory without accessing the game window."""
import argparse
import logging
from pathlib import Path

from PIL import Image

import attribute_details
import component_details
import empowerment_details
import paddle_ocr
import paddle_ocr_blocks
import promotion_badge_ocr
import promotion_details
from icon_match import match_icon
from profiles.ui_layout import get_layout_for_profile
from replay_common import crop as _crop
from replay_common import load_frame as _load_frame
from replay_common import load_manifest as _load_manifest
from replay_common import write_json as _write_json
from scroll_stitch import stitch_frames

log = logging.getLogger(__name__)


def _read_component(image: Image.Image, layout) -> dict:
    name = component_details._normalize_name(
        paddle_ocr.read_text(_crop(image, layout.component_name_box))
    )
    rarity = paddle_ocr.read_text(_crop(image, layout.component_rarity_box)).rstrip(" _")
    level = paddle_ocr.read_text(_crop(image, layout.component_level_box))
    stats_text = paddle_ocr_blocks.read_text_block(_crop(image, layout.component_stats_box))
    stats = component_details.parse_component_stats(stats_text)
    set_bonus = paddle_ocr_blocks.read_text_block(_crop(image, layout.component_set_bonus_box))
    return {"name": name, "rarity": rarity, "level": level, "stats": stats, "set_bonus": set_bonus}


def _stitch_attribute_frames(images: list[Image.Image], layout) -> Image.Image:
    """Frames are full-window captures (see capture_all_flagships.py's
    _save) - crop each to the scrollable table region before stitching, so
    every frame stitch_frames sees depicts the same box. Passing full-window
    frames straight through here previously produced a garbled composite
    (the first slice was the whole window, not the table)."""
    if not images:
        raise RuntimeError("No attribute frames found")
    table_frames = [image.crop(layout.table_box) for image in images]
    return stitch_frames(table_frames, layout.table_tab_bar_height, layout.expected_scroll_offset)


def replay(root: Path, output: Path) -> dict:
    manifest = _load_manifest(root)
    profile = (manifest["platform"], tuple(manifest["window_size"]))
    layout = get_layout_for_profile(profile)
    output.mkdir(parents=True, exist_ok=True)
    entries = manifest["frames"]
    by_ship = {}
    for entry in entries:
        by_ship.setdefault(entry["ship_index"], []).append(entry)

    results = {}
    for ship_index, ship_entries in by_ship.items():
        if ship_index is None:
            continue
        raw_dir = output / "raw" / f"ship-{ship_index:03d}"
        images = {entry["kind"]: _load_frame(root, entry) for entry in ship_entries if entry["kind"] != "attribute"}
        overview = images.get("overview-ready") or images.get("overview")
        if overview is None:
            continue
        name = paddle_ocr.read_text(_crop(overview, layout.name_box))
        _write_json(raw_dir / "name.json", {"text": name})
        element = match_icon(_crop(overview, layout.element_icon_box), "elements")
        empowerment_text = paddle_ocr.read_text(_crop(overview, layout.empowerment_box))
        empowerment = empowerment_details.parse_empowerment(empowerment_text)
        _write_json(raw_dir / "empowerment.json", {"text": empowerment_text, "value": empowerment})

        attribute_entries = [entry for entry in ship_entries if entry["kind"] == "attribute"]
        attribute_images = [_load_frame(root, entry) for entry in sorted(attribute_entries, key=lambda item: item["sequence"])]
        composite = _stitch_attribute_frames(attribute_images, layout)
        composite.save(raw_dir / "attribute-stitch.png")
        attribute_text = paddle_ocr_blocks.read_text_block(composite)
        (raw_dir / "attribute.txt").write_text(attribute_text + "\n", encoding="utf-8")
        attributes = {}
        attribute_details._parse(attribute_text, attributes, [None])
        attributes = attribute_details.heal_totals(attributes)
        validation = attribute_details.validate_sections(attributes)

        components = []
        for entry in sorted((item for item in ship_entries if item["kind"] == "component"), key=lambda item: item["sequence"]):
            component_image = _load_frame(root, entry)
            component = _read_component(component_image, layout)
            _write_json(raw_dir / f"component-{entry['sequence']:03d}.json", component)
            components.append(component)

        promotion_image = images.get("promotion")
        promotion = None
        if promotion_image is not None:
            button_text = paddle_ocr.read_text(_crop(promotion_image, layout.promote_button_box))
            badge_text = "" if "PROMOTED" in button_text.upper() else promotion_badge_ocr.read_promotion_badge(
                _crop(promotion_image, layout.promotion_badge_box)
            )
            level = promotion_details.classify_promotion(button_text, badge_text)
            _write_json(raw_dir / "promotion.json", {"button": button_text, "badge": badge_text, "level": level})
            promotion = {"level": level}

        results[str(ship_index)] = {
            "ship": name,
            "element": element,
            "empowerment": empowerment,
            "attributes": attributes,
            "validation": validation,
            "components": components,
            "promotion": promotion,
        }

    _write_json(output / "results.json", results)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    output = args.output or args.capture / "replay"
    replay(args.capture, output)
    log.info("Replay written to %s", output)


if __name__ == "__main__":
    main()