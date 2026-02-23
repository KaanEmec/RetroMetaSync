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
    _ = system_id, destination_system_id
    system_name = (destination_system_display or system_display or "Unknown").strip() or "Unknown"
    return {
        "rom": output_root / "Games" / system_name / rom_name,
        "platform_xml": output_root / "Data" / "Platforms" / f"{system_name}.xml",
        "image": output_root / "Images" / system_name / "Box - Front" / stem,
        "thumbnail": output_root / "Images" / system_name / "Screenshot - Gameplay" / stem,
        "marquee": output_root / "Images" / system_name / "Clear Logo" / stem,
        "video": output_root / "Videos" / system_name / stem,
        "manual": output_root / "Manuals" / system_name / stem,
    }
