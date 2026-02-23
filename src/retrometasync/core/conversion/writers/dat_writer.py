from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import zlib
import xml.etree.ElementTree as ET


def write_dat(dat_path: Path, dat_name: str, games: list[dict[str, object]]) -> None:
    """Write a simple Logiqx-style DAT file with ROM hashes."""
    dat_path.parent.mkdir(parents=True, exist_ok=True)

    root = ET.Element("datafile")
    header = ET.SubElement(root, "header")
    _add_text(header, "name", dat_name)
    _add_text(header, "description", f"RetroMetaSync export: {dat_name}")
    _add_text(header, "version", datetime.now(timezone.utc).strftime("%Y.%m.%d"))
    _add_text(header, "author", "RetroMetaSync")

    for game in games:
        machine_name = str(game.get("machine_name") or "unknown")
        rom_path = game.get("rom_path")
        if not isinstance(rom_path, Path):
            continue
        if not rom_path.exists():
            continue

        machine = ET.SubElement(root, "machine", {"name": machine_name})
        size, crc_hex, sha1_hex = _hash_file(rom_path)
        ET.SubElement(
            machine,
            "rom",
            {
                "name": rom_path.name,
                "size": str(size),
                "crc": crc_hex,
                "sha1": sha1_hex,
            },
        )

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(dat_path, encoding="utf-8", xml_declaration=True)


def _hash_file(path: Path) -> tuple[int, str, str]:
    size = 0
    crc = 0
    sha1 = hashlib.sha1()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            crc = zlib.crc32(chunk, crc)
            sha1.update(chunk)
    crc_hex = f"{crc & 0xFFFFFFFF:08x}"
    return size, crc_hex, sha1.hexdigest()


def _add_text(parent: ET.Element, tag: str, value: str | None) -> None:
    if value is None or value == "":
        return
    node = ET.SubElement(parent, tag)
    node.text = value
