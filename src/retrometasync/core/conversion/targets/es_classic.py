from __future__ import annotations

from pathlib import Path


def plan_paths(output_root: Path, system_id: str, system_display: str, rom_name: str, stem: str) -> dict[str, Path]:
    _ = system_display
    system_root = output_root / "roms" / system_id
    return {
        "rom": system_root / rom_name,
        "gamelist": system_root / "gamelist.xml",
        "image": system_root / "images" / stem,
        "thumbnail": system_root / "images" / f"{stem}-thumb",
        "marquee": system_root / "images" / f"{stem}-marquee",
        "video": system_root / "videos" / stem,
        "manual": system_root / "manuals" / stem,
    }
