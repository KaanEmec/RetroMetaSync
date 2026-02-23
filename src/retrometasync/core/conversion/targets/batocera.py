from __future__ import annotations

from pathlib import Path


def plan_paths(output_root: Path, system_id: str, system_display: str, rom_name: str, stem: str) -> dict[str, Path]:
    _ = system_display
    system_root = output_root / "roms" / system_id
    return {
        "rom": system_root / rom_name,
        "gamelist": system_root / "gamelist.xml",
        "image": system_root / "images" / f"{stem}-image",
        "thumbnail": system_root / "images" / f"{stem}-thumb",
        "marquee": system_root / "images" / f"{stem}-marquee",
        "bezel": system_root / "images" / f"{stem}-bezel",
        "video": system_root / "videos" / f"{stem}-video",
        "manual": system_root / "manuals" / stem,
    }
