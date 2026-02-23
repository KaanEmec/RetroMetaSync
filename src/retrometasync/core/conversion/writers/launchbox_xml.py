from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET


def write_launchbox_platform_xml(platform_xml_path: Path, games: list[dict[str, str]]) -> None:
    platform_xml_path.parent.mkdir(parents=True, exist_ok=True)

    root = ET.Element("LaunchBox")
    for game_data in games:
        game_node = ET.SubElement(root, "Game")
        _add_text(game_node, "Title", game_data.get("title"))
        _add_text(game_node, "SortTitle", game_data.get("sort_title"))
        _add_text(game_node, "ApplicationPath", game_data.get("application_path"))
        _add_text(game_node, "ManualPath", game_data.get("manual_path"))
        _add_text(game_node, "FrontImagePath", game_data.get("front_image_path"))
        _add_text(game_node, "ScreenshotImagePath", game_data.get("screenshot_image_path"))
        _add_text(game_node, "BackgroundImagePath", game_data.get("background_image_path"))
        _add_text(game_node, "LogoImagePath", game_data.get("logo_image_path"))
        _add_text(game_node, "VideoPath", game_data.get("video_path"))
        _add_text(game_node, "Platform", game_data.get("platform"))
        _add_text(game_node, "Developer", game_data.get("developer"))
        _add_text(game_node, "Publisher", game_data.get("publisher"))
        _add_text(game_node, "Genre", game_data.get("genre"))
        _add_text(game_node, "Language", game_data.get("language"))
        _add_text(game_node, "Region", game_data.get("region"))
        _add_text(game_node, "Favorite", game_data.get("favorite"))
        _add_text(game_node, "PlayCount", game_data.get("play_count"))
        _add_text(game_node, "LastPlayedDate", game_data.get("last_played_date"))
        _add_text(game_node, "CommunityStarRating", game_data.get("community_star_rating"))
        _add_text(game_node, "StarRating", game_data.get("star_rating"))
        _add_text(game_node, "Notes", game_data.get("notes"))
        _add_text(game_node, "ReleaseDate", game_data.get("release_date"))

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(platform_xml_path, encoding="utf-8", xml_declaration=True)


def _add_text(parent: ET.Element, tag: str, value: str | None) -> None:
    if value is None or value == "":
        return
    node = ET.SubElement(parent, tag)
    node.text = value
