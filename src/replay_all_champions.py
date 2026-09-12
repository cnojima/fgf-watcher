"""Replay a champion capture directory without accessing the game window."""
import argparse
import logging
from pathlib import Path

from PIL import Image

import champion_attributes
import champion_info
import champion_star_level
import champion_weapon
import orange_kid_ocr
import paddle_ocr
import paddle_ocr_blocks
from champion_ability import ABILITY_SLOTS
from champion_weapon import BONUS_SLOTS
from icon_match import match_icon
from profiles.champion_layout import get_champion_layout_for_profile, require_field
from replay_common import crop, load_frame, load_manifest, write_json
from scroll_stitch import stitch_frames

log = logging.getLogger(__name__)


def _read_info(image: Image.Image, layout) -> dict:
    name = champion_info._match_known_name(paddle_ocr.read_text(crop(image, layout.name_box)))
    title = paddle_ocr.read_text(crop(image, layout.title_box))
    quality = champion_info._match_quality(paddle_ocr.read_text(crop(image, layout.quality_box)))
    element = match_icon(crop(image, layout.element_icon_box), "elements")
    champion_type = match_icon(crop(image, layout.type_icon_box), "champion_types")
    level = orange_kid_ocr.read_level(crop(image, layout.level_box))
    power = champion_info._normalize_power(
        champion_info._clean_leading_noise(paddle_ocr.read_text(crop(image, layout.power_box)))
    )
    return {
        "name": name, "title": title, "quality": quality, "element": element,
        "type": champion_type, "level": level, "power": power,
    }


def _stitch_weapon_stats_frames(images: list[Image.Image], layout) -> Image.Image:
    """images are full-window captures (see capture_all_champions.py's
    _save) - crop each to the scrollable stats region before stitching, so
    every frame stitch_frames sees depicts the same box (see
    replay_all_flagships._stitch_attribute_frames for the bug this avoids:
    passing a full-window frame straight through silently garbles the
    composite)."""
    stats_box = require_field(layout.weapon_stats_box, "weapon_stats_box")
    stats_frames = [image.crop(stats_box) for image in images]
    return stitch_frames(stats_frames, static_header_height=0, expected_offset=layout.weapon_stats_expected_scroll_offset)


def _read_weapon(weapon_image: Image.Image, stats_images: list[Image.Image], bonus_images: dict, layout) -> dict:
    name_box = require_field(layout.weapon_name_box, "weapon_name_box")
    name = champion_weapon._normalize_weapon_name(paddle_ocr.read_text(crop(weapon_image, name_box)))
    badge_box = require_field(layout.weapon_element_type_box, "weapon_element_type_box")
    badge_text = paddle_ocr.read_text(crop(weapon_image, badge_box))
    element = champion_weapon._find_keyword(badge_text, champion_weapon._ELEMENTS)
    weapon_type = champion_weapon._find_keyword(badge_text, champion_weapon._TYPES)
    level = orange_kid_ocr.read_level(crop(weapon_image, layout.weapon_level_box))

    stats_composite = _stitch_weapon_stats_frames(stats_images, layout)
    stats = champion_weapon.parse_weapon_stats(paddle_ocr_blocks.read_text_block(stats_composite))

    bonuses = {
        slot: paddle_ocr_blocks.read_text_block(crop(image, layout.weapon_bonus_info_box))
        for slot, image in bonus_images.items()
    }

    return {"name": name, "element": element, "type": weapon_type, "level": level, "stats": stats, "bonuses": bonuses}


def _stitch_ability_body_frames(images: list[Image.Image], layout) -> Image.Image:
    """Same full-window-frame crop-before-stitch requirement as
    _stitch_weapon_stats_frames above."""
    scroll_frames = [image.crop(layout.ability_scroll_box) for image in images]
    return stitch_frames(scroll_frames, static_header_height=0, expected_offset=layout.ability_expected_scroll_offset)


def _read_ability(images: list[Image.Image], layout) -> str:
    """images are full-window frames for one ability slot, in sequence
    order - see capture_all_champions.py's _capture_ability_frames. Mirrors
    champion_ability._read_ability_card, reading from already-captured
    frames instead of a live screenshot+scroll."""
    header = paddle_ocr_blocks.read_text_block(crop(images[0], layout.ability_header_box))
    body = paddle_ocr_blocks.read_text_block(_stitch_ability_body_frames(images, layout))
    return f"{header}\n{body}"


def replay(root: Path, output: Path) -> dict:
    manifest = load_manifest(root)
    profile = (manifest["platform"], tuple(manifest["window_size"]))
    layout = get_champion_layout_for_profile(profile)
    output.mkdir(parents=True, exist_ok=True)

    by_champion: dict[int, list[dict]] = {}
    for entry in manifest["frames"]:
        by_champion.setdefault(entry["ship_index"], []).append(entry)

    results = {}
    for champion_index, champion_entries in by_champion.items():
        if champion_index is None:
            continue
        raw_dir = output / "raw" / f"champion-{champion_index:03d}"
        by_kind: dict[str, list[dict]] = {}
        for entry in champion_entries:
            by_kind.setdefault(entry["kind"], []).append(entry)

        info_entries = by_kind.get("info")
        if not info_entries:
            continue
        info_image = load_frame(root, info_entries[0])
        info = _read_info(info_image, layout)
        write_json(raw_dir / "info.json", info)

        star_level = champion_star_level.classify_star_level(crop(info_image, layout.star_level_pips_box))

        def _read_flat(kind: str) -> dict[str, str]:
            entries = by_kind.get(kind)
            if not entries:
                return {}
            image = load_frame(root, entries[0])
            text = paddle_ocr_blocks.read_text_block(crop(image, layout.attribute_modal_box))
            return champion_attributes.parse_flat_list(text)

        attributes = {"space_combat": _read_flat("attribute-space"), "ground_combat": _read_flat("attribute-ground")}
        write_json(raw_dir / "attributes.json", attributes)

        weapon = None
        weapon_entries = by_kind.get("weapon")
        if weapon_entries:
            weapon_image = load_frame(root, weapon_entries[0])
            stats_entries = sorted(by_kind.get("weapon-stats", []), key=lambda e: e["sequence"])
            stats_images = [load_frame(root, e) for e in stats_entries]
            bonus_images = {
                slot: load_frame(root, by_kind[f"weapon-bonus-{slot}"][0])
                for slot in BONUS_SLOTS if by_kind.get(f"weapon-bonus-{slot}")
            }
            weapon = _read_weapon(weapon_image, stats_images, bonus_images, layout)
            write_json(raw_dir / "weapon.json", weapon)

        abilities = {}
        for slot in ABILITY_SLOTS:
            slot_entries = sorted(by_kind.get(f"ability-{slot}", []), key=lambda e: e["sequence"])
            if not slot_entries:
                continue
            slot_images = [load_frame(root, e) for e in slot_entries]
            abilities[slot] = _read_ability(slot_images, layout)
        if abilities:
            write_json(raw_dir / "abilities.json", abilities)
        else:
            # Mirrors collect_all_champions.collect_champion's own "lost
            # navigation state mid-champion" sentinel - no ability frames at
            # all means capture skipped this champion's ability read (see
            # capture_all_champions._capture_champion's post-weapon check).
            abilities = None

        results[str(champion_index)] = {
            "info": info,
            "star_level": star_level,
            "attributes": attributes,
            "weapon": weapon,
            "abilities": abilities,
        }

    write_json(output / "results.json", results)
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
