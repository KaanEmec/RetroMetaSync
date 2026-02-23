from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET


GAME_TAGS: tuple[tuple[str, str], ...] = (
    ("title", "Title"),
    ("sort_title", "SortTitle"),
    ("application_path", "ApplicationPath"),
    ("manual_path", "ManualPath"),
    ("front_image_path", "FrontImagePath"),
    ("screenshot_image_path", "ScreenshotImagePath"),
    ("background_image_path", "BackgroundImagePath"),
    ("logo_image_path", "LogoImagePath"),
    ("video_path", "VideoPath"),
    ("platform", "Platform"),
    ("developer", "Developer"),
    ("publisher", "Publisher"),
    ("genre", "Genre"),
    ("language", "Language"),
    ("region", "Region"),
    ("favorite", "Favorite"),
    ("play_count", "PlayCount"),
    ("last_played_date", "LastPlayedDate"),
    ("community_star_rating", "CommunityStarRating"),
    ("star_rating", "StarRating"),
    ("notes", "Notes"),
    ("release_date", "ReleaseDate"),
)


def read_launchbox_platform_xml(platform_xml_path: Path) -> list[dict[str, str]]:
    if not platform_xml_path.exists():
        return []
    root = ET.parse(platform_xml_path).getroot()
    entries: list[dict[str, str]] = []
    for game_node in root.findall("Game"):
        item: dict[str, str] = {}
        for key, tag in GAME_TAGS:
            value = game_node.findtext(tag)
            if value:
                item[key] = value
        if item:
            entries.append(item)
    return entries


def write_launchbox_platform_xml(platform_xml_path: Path, games: list[dict[str, str]]) -> None:
    platform_xml_path.parent.mkdir(parents=True, exist_ok=True)

    root = ET.Element("LaunchBox")
    for game_data in games:
        game_node = ET.SubElement(root, "Game")
        for key, tag in GAME_TAGS:
            _add_text(game_node, tag, game_data.get(key))

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(platform_xml_path, encoding="utf-8", xml_declaration=True)


def _add_text(parent: ET.Element, tag: str, value: str | None) -> None:
    if value is None or value == "":
        return
    node = ET.SubElement(parent, tag)
    node.text = value
