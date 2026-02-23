from __future__ import annotations

from pathlib import Path


def plan_paths(output_root: Path, system_id: str, system_display: str, rom_name: str, stem: str) -> dict[str, Path]:
    _ = system_display
    rom_root = output_root / "roms" / system_id
    media_root = output_root / "downloaded_media" / system_id
    return {
        "rom": rom_root / rom_name,
        "gamelist": output_root / "gamelists" / system_id / "gamelist.xml",
        "image": media_root / "covers" / stem,
        "thumbnail": media_root / "screenshots" / stem,
        "marquee": media_root / "marquees" / stem,
        "video": media_root / "videos" / stem,
        "manual": media_root / "manuals" / stem,
        "bezel": media_root / "fanart" / stem,
    }
