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
    rom_root = output_root / "roms" / effective_system_id
    media_root = output_root / "downloaded_media" / effective_system_id
    return {
        "rom": rom_root / rom_name,
        "gamelist": output_root / "gamelists" / effective_system_id / "gamelist.xml",
        "image": media_root / "covers" / stem,
        "thumbnail": media_root / "screenshots" / stem,
        "marquee": media_root / "marquees" / stem,
        "video": media_root / "videos" / stem,
        "manual": media_root / "manuals" / stem,
        "bezel": media_root / "fanart" / stem,
    }
