from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET


def write_gamelist(gamelist_path: Path, games: list[dict[str, str]]) -> None:
    gamelist_path.parent.mkdir(parents=True, exist_ok=True)

    root = ET.Element("gameList")
    for game_data in games:
        game_node = ET.SubElement(root, "game")
        _add_text(game_node, "path", game_data.get("path"))
        _add_text(game_node, "name", game_data.get("name"))
        _add_text(game_node, "sortname", game_data.get("sortname"))
        _add_text(game_node, "desc", game_data.get("desc"))
        _add_text(game_node, "image", game_data.get("image"))
        _add_text(game_node, "thumbnail", game_data.get("thumbnail"))
        _add_text(game_node, "fanart", game_data.get("fanart"))
        _add_text(game_node, "marquee", game_data.get("marquee"))
        _add_text(game_node, "video", game_data.get("video"))
        _add_text(game_node, "manual", game_data.get("manual"))
        _add_text(game_node, "developer", game_data.get("developer"))
        _add_text(game_node, "publisher", game_data.get("publisher"))
        _add_text(game_node, "genre", game_data.get("genre"))
        _add_text(game_node, "lang", game_data.get("lang"))
        _add_text(game_node, "region", game_data.get("region"))
        _add_text(game_node, "players", game_data.get("players"))
        _add_text(game_node, "favorite", game_data.get("favorite"))
        _add_text(game_node, "hidden", game_data.get("hidden"))
        _add_text(game_node, "playcount", game_data.get("playcount"))
        _add_text(game_node, "lastplayed", game_data.get("lastplayed"))
        _add_text(game_node, "rating", game_data.get("rating"))
        _add_text(game_node, "releasedate", game_data.get("releasedate"))

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(gamelist_path, encoding="utf-8", xml_declaration=True)


def _add_text(parent: ET.Element, tag: str, value: str | None) -> None:
    if value is None or value == "":
        return
    node = ET.SubElement(parent, tag)
    node.text = value
