from __future__ import annotations

from pathlib import Path


def plan_paths(
    output_root: Path,
    system_id: str,
    system_display: str,
    rom_name: str,
    stem: str,
    destination_system_id: str | None = None,
    destination_system_display: str | None = None,
) -> dict[str, Path]:
    _ = system_display, destination_system_display
    effective_system_id = (destination_system_id or system_id).strip() or system_id
    system_root = output_root / "roms" / effective_system_id
    return {
        "rom": system_root / rom_name,
        "gamelist": system_root / "gamelist.xml",
        "images_root": system_root / "images",
        "image": system_root / "images" / stem,
        "thumbnail": system_root / "images" / f"{stem}-thumb",
        "marquee": system_root / "images" / f"{stem}-marquee",
        "video": system_root / "videos" / stem,
        "manual": system_root / "manuals" / stem,
    }
