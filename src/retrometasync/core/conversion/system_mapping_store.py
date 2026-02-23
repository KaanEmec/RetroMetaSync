from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re


_STORE_DIRNAME = ".retrometasync"
_STORE_FILENAME = "system_mapping.json"


@dataclass(slots=True)
class DestinationSystemsSnapshot:
    """Existing destination system names discovered for one target/output root."""

    target_ecosystem: str
    output_root: Path
    systems: list[str]


def mapping_storage_path(output_root: Path) -> Path:
    return output_root / _STORE_DIRNAME / _STORE_FILENAME


def load_system_mapping(output_root: Path, target_ecosystem: str) -> dict[str, str]:
    path = mapping_storage_path(output_root)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    key = _mapping_bucket_key(target_ecosystem)
    bucket = payload.get(key, {})
    if not isinstance(bucket, dict):
        return {}
    mapping: dict[str, str] = {}
    for source_system, destination_system in bucket.items():
        if not isinstance(source_system, str) or not isinstance(destination_system, str):
            continue
        src = source_system.strip()
        dst = destination_system.strip()
        if src and dst:
            mapping[src] = dst
    return mapping


def save_system_mapping(output_root: Path, target_ecosystem: str, mapping: dict[str, str]) -> None:
    path = mapping_storage_path(output_root)
    path.parent.mkdir(parents=True, exist_ok=True)

    existing_payload: dict[str, object] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing_payload = loaded
        except Exception:  # noqa: BLE001
            existing_payload = {}

    key = _mapping_bucket_key(target_ecosystem)
    existing_payload[key] = {
        source_system: destination_system
        for source_system, destination_system in sorted(mapping.items())
        if source_system.strip() and destination_system.strip()
    }
    path.write_text(json.dumps(existing_payload, indent=2, sort_keys=True), encoding="utf-8")


def discover_destination_systems(output_root: Path, target_ecosystem: str) -> DestinationSystemsSnapshot:
    systems: set[str] = set()
    target = target_ecosystem.lower().strip()

    if target in {"batocera", "es_classic", "es_de", "retrobat"}:
        roms_root = output_root / "roms"
        if roms_root.exists():
            systems.update(_child_dir_names(roms_root))

    if target == "es_de":
        gamelist_root = output_root / "gamelists"
        if gamelist_root.exists():
            systems.update(_child_dir_names(gamelist_root))
    elif target == "launchbox":
        games_root = output_root / "Games"
        if games_root.exists():
            systems.update(_child_dir_names(games_root))
        platforms_root = output_root / "Data" / "Platforms"
        if platforms_root.exists():
            for xml_path in sorted(platforms_root.glob("*.xml")):
                if xml_path.stem.strip():
                    systems.add(xml_path.stem.strip())

    return DestinationSystemsSnapshot(
        target_ecosystem=target_ecosystem,
        output_root=output_root,
        systems=sorted(systems, key=lambda value: value.lower()),
    )


def suggest_system_mapping(
    source_systems: list[str],
    destination_systems: list[str],
    previous_mapping: dict[str, str] | None = None,
) -> dict[str, str]:
    previous = previous_mapping or {}
    suggestions: dict[str, str] = {}
    destination_lookup_exact = {value.lower(): value for value in destination_systems}
    destination_lookup_normalized = {normalize_name(value): value for value in destination_systems}

    for source_system in source_systems:
        source = source_system.strip()
        if not source:
            continue
        if source in previous and previous[source].strip():
            suggestions[source] = previous[source].strip()
            continue
        exact = destination_lookup_exact.get(source.lower())
        if exact:
            suggestions[source] = exact
            continue
        normalized = destination_lookup_normalized.get(normalize_name(source))
        if normalized:
            suggestions[source] = normalized

    return suggestions


def normalize_name(value: str) -> str:
    text = value.lower().strip()
    text = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", text)
    text = re.sub(r"[_\-]+", " ", text)
    text = re.sub(r"[^a-z0-9 ]+", "", text)
    text = re.sub(r"\b(v\d+|ver\s*\d+|version\s*\d+|rev\s*[a-z0-9]+)\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _child_dir_names(root: Path) -> set[str]:
    names: set[str] = set()
    for child in root.iterdir():
        if child.is_dir() and child.name.strip():
            names.add(child.name.strip())
    return names


def _mapping_bucket_key(target_ecosystem: str) -> str:
    return target_ecosystem.strip().lower()
