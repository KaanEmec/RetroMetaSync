from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET


GAME_TAGS: tuple[str, ...] = (
    "path",
    "name",
    "sortname",
    "desc",
    "image",
    "thumbnail",
    "fanart",
    "marquee",
    "video",
    "manual",
    "developer",
    "publisher",
    "genre",
    "lang",
    "region",
    "players",
    "favorite",
    "hidden",
    "playcount",
    "lastplayed",
    "rating",
    "releasedate",
)


def read_gamelist(gamelist_path: Path) -> list[dict[str, str]]:
    if not gamelist_path.exists():
        return []
    root = ET.parse(gamelist_path).getroot()
    entries: list[dict[str, str]] = []
    for game_node in root.findall("game"):
        item: dict[str, str] = {}
        for tag in GAME_TAGS:
            value = game_node.findtext(tag)
            if value:
                item[tag] = value
        if item:
            entries.append(item)
    return entries


def write_gamelist(gamelist_path: Path, games: list[dict[str, str]]) -> None:
    gamelist_path.parent.mkdir(parents=True, exist_ok=True)

    root = ET.Element("gameList")
    for game_data in games:
        game_node = ET.SubElement(root, "game")
        for tag in GAME_TAGS:
            _add_text(game_node, tag, game_data.get(tag))

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(gamelist_path, encoding="utf-8", xml_declaration=True)


def _add_text(parent: ET.Element, tag: str, value: str | None) -> None:
    if value is None or value == "":
        return
    node = ET.SubElement(parent, tag)
    node.text = value
