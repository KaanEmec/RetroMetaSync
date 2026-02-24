from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import hashlib
import os
import re
import zlib
import xml.etree.ElementTree as ET

from retrometasync.config.ecosystems import PRELOADED_METADATA_PROFILE_BY_SYSTEM, PRELOADED_METADATA_SOURCE_CATALOG
from retrometasync.config.system_aliases import canonicalize_system_id
from retrometasync.core.models import Game, Library


@dataclass(frozen=True, slots=True)
class DatRomHash:
    name: str
    crc: str | None = None
    sha1: str | None = None


@dataclass(frozen=True, slots=True)
class DatGameMetadata:
    set_name: str
    title: str | None = None
    year: int | None = None
    manufacturer: str | None = None
    cloneof: str | None = None
    rom_hashes: tuple[DatRomHash, ...] = ()


@dataclass(slots=True)
class DatIndex:
    by_set_name: dict[str, DatGameMetadata]
    by_crc: dict[str, DatGameMetadata]
    by_sha1: dict[str, DatGameMetadata]


@dataclass(slots=True)
class PreloadedMetadataResult:
    enriched_games: int = 0
    sources_used: set[Path] | None = None
    warnings: list[str] | None = None


def enrich_library_with_preloaded_metadata(
    library: Library,
    source_root: Path,
    metadata_root: Path | None = None,
    compute_missing_hashes: bool = False,
    progress_callback=None,
    dat_override_by_system: dict[str, Path] | None = None,
) -> PreloadedMetadataResult:
    target_system_ids = list(library.games_by_system.keys())
    return enrich_library_systems_with_preloaded_metadata(
        library=library,
        source_root=source_root,
        target_system_ids=target_system_ids,
        metadata_root=metadata_root,
        compute_missing_hashes=compute_missing_hashes,
        progress_callback=progress_callback,
        dat_override_by_system=dat_override_by_system,
    )


def enrich_library_systems_with_preloaded_metadata(
    library: Library,
    source_root: Path,
    target_system_ids: list[str],
    metadata_root: Path | None = None,
    compute_missing_hashes: bool = False,
    progress_callback=None,
    dat_override_by_system: dict[str, Path] | None = None,
) -> PreloadedMetadataResult:
    resolver = _PreloadedMetadataResolver(
        source_root=source_root,
        metadata_root=metadata_root,
        dat_override_by_system=dat_override_by_system,
    )
    warnings: list[str] = []
    enriched = 0
    sources_used: set[Path] = set()
    hash_cache: dict[str, tuple[str, str]] = {}

    target_pairs: list[tuple[str, str]] = []
    seen_targets: set[str] = set()
    for raw_system_id in target_system_ids:
        raw = raw_system_id.strip().lower()
        if not raw:
            continue
        canonical = canonicalize_system_id(raw)
        if canonical in seen_targets:
            continue
        seen_targets.add(canonical)
        target_pairs.append((raw, canonical))

    for raw_system_id, canonical_system_id in target_pairs:
        games = library.games_by_system.get(canonical_system_id, [])
        if not games and raw_system_id != canonical_system_id:
            games = library.games_by_system.get(raw_system_id, [])
        index, source_path = resolver.resolve_for_system(canonical_system_id)
        if index is None or source_path is None:
            continue
        sources_used.add(source_path)
        for game in games:
            if _apply_metadata(game, index, compute_missing_hashes=compute_missing_hashes, hash_cache=hash_cache):
                enriched += 1
        if progress_callback is not None and games:
            progress_callback(
                f"[metadata] {canonical_system_id}: preloaded source '{source_path.name}' checked for {len(games)} games"
            )

    warnings.extend(resolver.warnings)
    return PreloadedMetadataResult(enriched_games=enriched, sources_used=sources_used, warnings=warnings)


def _apply_metadata(
    game: Game,
    index: DatIndex,
    *,
    compute_missing_hashes: bool,
    hash_cache: dict[str, tuple[str, str]],
) -> bool:
    before = (
        game.title,
        game.release_date,
        game.developer,
        game.publisher,
        game.crc,
        game.sha1,
    )
    entry = _match_entry(game, index)
    if entry is None and compute_missing_hashes:
        _ensure_game_hashes(game, hash_cache)
        entry = _match_entry(game, index)
    if entry is None:
        return False

    if _is_placeholder_title(game):
        if entry.title:
            game.title = entry.title

    if game.release_date is None and entry.year is not None:
        game.release_date = datetime(entry.year, 1, 1)

    if entry.manufacturer:
        if not game.publisher:
            game.publisher = entry.manufacturer
        if not game.developer:
            game.developer = entry.manufacturer

    rom_hash = _find_hash_for_rom(game, entry)
    if rom_hash is not None:
        if not game.crc and rom_hash.crc:
            game.crc = rom_hash.crc
        if not game.sha1 and rom_hash.sha1:
            game.sha1 = rom_hash.sha1

    after = (
        game.title,
        game.release_date,
        game.developer,
        game.publisher,
        game.crc,
        game.sha1,
    )
    return before != after


def _match_entry(game: Game, index: DatIndex) -> DatGameMetadata | None:
    rom_set_name = _normalize_set_name(game.rom_basename)
    if rom_set_name in index.by_set_name:
        return index.by_set_name[rom_set_name]

    if game.crc:
        crc = _normalize_hex(game.crc)
        if crc and crc in index.by_crc:
            return index.by_crc[crc]
    if game.sha1:
        sha1 = _normalize_hex(game.sha1)
        if sha1 and sha1 in index.by_sha1:
            return index.by_sha1[sha1]
    return None


def _find_hash_for_rom(game: Game, entry: DatGameMetadata) -> DatRomHash | None:
    if not entry.rom_hashes:
        return None
    normalized_rom_filename = game.rom_filename.lower()
    for rom_hash in entry.rom_hashes:
        if rom_hash.name.lower() == normalized_rom_filename:
            return rom_hash
    if len(entry.rom_hashes) == 1:
        return entry.rom_hashes[0]
    return None


def _is_placeholder_title(game: Game) -> bool:
    title = (game.title or "").strip().lower()
    if not title:
        return True
    rom_stem = game.rom_basename.strip().lower()
    if title == rom_stem:
        return True
    return title.replace("_", " ").replace("-", " ") == rom_stem.replace("_", " ").replace("-", " ")


def _normalize_hex(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    return normalized or None


def _normalize_set_name(value: str) -> str:
    return value.strip().lower()


class _PreloadedMetadataResolver:
    def __init__(
        self,
        source_root: Path,
        metadata_root: Path | None = None,
        dat_override_by_system: dict[str, Path] | None = None,
    ) -> None:
        self.source_root = source_root
        self.metadata_root = metadata_root
        self.dat_override_by_system = {
            canonicalize_system_id(key): value for key, value in (dat_override_by_system or {}).items() if key.strip()
        }
        self._index_by_path: dict[Path, DatIndex] = {}
        self._resolved_by_system: dict[str, tuple[DatIndex | None, Path | None]] = {}
        self.warnings: list[str] = []

    def resolve_for_system(self, system_id: str) -> tuple[DatIndex | None, Path | None]:
        normalized_system_id = canonicalize_system_id(system_id)
        if normalized_system_id in self._resolved_by_system:
            return self._resolved_by_system[normalized_system_id]

        override_path = self.dat_override_by_system.get(normalized_system_id)
        if override_path is not None and override_path.exists() and override_path.is_file():
            index = self._load_index(override_path)
            if index is not None:
                value = (index, override_path)
                self._resolved_by_system[normalized_system_id] = value
                return value

        source_keys = PRELOADED_METADATA_PROFILE_BY_SYSTEM.get(normalized_system_id, ())
        for source_key in source_keys:
            dat_path = self._resolve_source_path(source_key)
            if dat_path is None:
                continue
            index = self._load_index(dat_path)
            if index is not None:
                value = (index, dat_path)
                self._resolved_by_system[normalized_system_id] = value
                return value

        value = (None, None)
        self._resolved_by_system[normalized_system_id] = value
        return value

    def _resolve_source_path(self, source_key: str) -> Path | None:
        candidates = PRELOADED_METADATA_SOURCE_CATALOG.get(source_key, ())
        if not candidates:
            return None
        for root in _metadata_search_roots(self.source_root, self.metadata_root):
            for candidate in candidates:
                path = root / candidate
                if path.exists() and path.is_file():
                    return path
        return None

    def _load_index(self, dat_path: Path) -> DatIndex | None:
        if dat_path in self._index_by_path:
            return self._index_by_path[dat_path]
        try:
            index = parse_clrmamepro_dat(dat_path)
        except (ET.ParseError, OSError, ValueError) as exc:
            self.warnings.append(f"Failed to read DAT '{dat_path}': {exc}")
            return None
        self._index_by_path[dat_path] = index
        return index


def _metadata_search_roots(source_root: Path, metadata_root: Path | None = None) -> list[Path]:
    env_root = os.environ.get("RETROMETASYNC_PRELOADED_METADATA_ROOT", "").strip()
    roots: list[Path] = []
    if metadata_root is not None:
        roots.append(metadata_root.expanduser())
    if env_root:
        roots.append(Path(env_root).expanduser())
    roots.extend(
        [
            source_root / ".retrometasync" / "dats",
            source_root / "metadata" / "dats",
            source_root / "dats",
        ]
    )
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = root.as_posix().lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


def parse_clrmamepro_dat_xml(dat_path: Path) -> DatIndex:
    tree = ET.parse(dat_path)
    root = tree.getroot()

    by_set_name: dict[str, DatGameMetadata] = {}
    by_crc: dict[str, DatGameMetadata] = {}
    by_sha1: dict[str, DatGameMetadata] = {}

    game_nodes = list(root.findall("game")) + list(root.findall("machine"))
    if not game_nodes:
        game_nodes = list(root.findall("./datafile/game")) + list(root.findall("./datafile/machine"))

    for game_node in game_nodes:
        set_name = _normalize_set_name((game_node.get("name") or "").strip())
        if not set_name:
            continue
        title = _safe_text(game_node.find("description"))
        manufacturer = _safe_text(game_node.find("manufacturer"))
        cloneof = game_node.get("cloneof")
        year = _parse_year(_safe_text(game_node.find("year")))
        hashes = _parse_rom_hashes(game_node)
        entry = DatGameMetadata(
            set_name=set_name,
            title=title,
            year=year,
            manufacturer=manufacturer,
            cloneof=cloneof,
            rom_hashes=hashes,
        )
        by_set_name[set_name] = entry
        for rom_hash in hashes:
            if rom_hash.crc and rom_hash.crc not in by_crc:
                by_crc[rom_hash.crc] = entry
            if rom_hash.sha1 and rom_hash.sha1 not in by_sha1:
                by_sha1[rom_hash.sha1] = entry
    if not by_set_name:
        raise ValueError(f"No machine/game entries found in DAT: {dat_path}")
    return DatIndex(by_set_name=by_set_name, by_crc=by_crc, by_sha1=by_sha1)


def parse_clrmamepro_dat(dat_path: Path) -> DatIndex:
    # Support both XML DATs and clrmamepro text DATs.
    with dat_path.open("rb") as handle:
        sniff = handle.read(2048)
    if sniff.lstrip().startswith(b"<"):
        return parse_clrmamepro_dat_xml(dat_path)
    return parse_clrmamepro_dat_text(dat_path)


def parse_clrmamepro_dat_text(dat_path: Path) -> DatIndex:
    by_set_name: dict[str, DatGameMetadata] = {}
    by_crc: dict[str, DatGameMetadata] = {}
    by_sha1: dict[str, DatGameMetadata] = {}

    game_name: str | None = None
    game_year: int | None = None
    game_manufacturer: str | None = None
    cloneof: str | None = None
    rom_hashes: list[DatRomHash] = []
    in_game = False

    with dat_path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            lower = line.lower()

            if lower.startswith("game") and "(" in line:
                in_game = True
                game_name = None
                game_year = None
                game_manufacturer = None
                cloneof = None
                rom_hashes = []
                continue

            if not in_game:
                continue

            if line == ")":
                _commit_text_game(
                    by_set_name=by_set_name,
                    by_crc=by_crc,
                    by_sha1=by_sha1,
                    game_name=game_name,
                    game_year=game_year,
                    game_manufacturer=game_manufacturer,
                    cloneof=cloneof,
                    rom_hashes=rom_hashes,
                )
                in_game = False
                continue

            if lower.startswith("name "):
                game_name = _strip_dat_value(line[5:].strip())
                continue

            if lower.startswith("year "):
                game_year = _parse_year(_strip_dat_value(line[5:].strip()))
                continue

            if lower.startswith("manufacturer ") or lower.startswith("developer "):
                value = line.split(" ", 1)[1].strip()
                game_manufacturer = _strip_dat_value(value)
                continue

            if lower.startswith("cloneof "):
                cloneof = _strip_dat_value(line[8:].strip())
                continue

            if lower.startswith("rom "):
                parsed_rom = _parse_text_dat_rom_line(line)
                if parsed_rom is not None:
                    rom_hashes.append(parsed_rom)
                continue

    if not by_set_name:
        raise ValueError(f"No machine/game entries found in DAT: {dat_path}")
    return DatIndex(by_set_name=by_set_name, by_crc=by_crc, by_sha1=by_sha1)


def _commit_text_game(
    *,
    by_set_name: dict[str, DatGameMetadata],
    by_crc: dict[str, DatGameMetadata],
    by_sha1: dict[str, DatGameMetadata],
    game_name: str | None,
    game_year: int | None,
    game_manufacturer: str | None,
    cloneof: str | None,
    rom_hashes: list[DatRomHash],
) -> None:
    if not game_name and not rom_hashes:
        return
    set_name = _set_name_from_text_game(game_name, rom_hashes)
    if not set_name:
        return
    entry = DatGameMetadata(
        set_name=set_name,
        title=game_name,
        year=game_year,
        manufacturer=game_manufacturer,
        cloneof=cloneof,
        rom_hashes=tuple(rom_hashes),
    )
    by_set_name[set_name] = entry
    for rom_hash in rom_hashes:
        if rom_hash.crc and rom_hash.crc not in by_crc:
            by_crc[rom_hash.crc] = entry
        if rom_hash.sha1 and rom_hash.sha1 not in by_sha1:
            by_sha1[rom_hash.sha1] = entry


def _set_name_from_text_game(game_name: str | None, rom_hashes: list[DatRomHash]) -> str | None:
    if rom_hashes:
        rom_name = rom_hashes[0].name.strip()
        if rom_name:
            return _normalize_set_name(Path(rom_name).stem)
    if game_name:
        return _normalize_set_name(game_name)
    return None


def _parse_text_dat_rom_line(line: str) -> DatRomHash | None:
    match = re.search(r"rom\s*\((.*)\)\s*$", line, flags=re.IGNORECASE)
    if not match:
        return None
    attrs = _parse_text_dat_attrs(match.group(1))
    name = attrs.get("name", "").strip()
    if not name:
        return None
    return DatRomHash(
        name=name,
        crc=_normalize_hex(attrs.get("crc")),
        sha1=_normalize_hex(attrs.get("sha1")),
    )


def _parse_text_dat_attrs(text: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    # Key/value parser for tokens like: key "quoted value" OR key bare_value
    for match in re.finditer(r"([A-Za-z0-9_]+)\s+(\"[^\"]*\"|\S+)", text):
        key = match.group(1).strip().lower()
        value = _strip_dat_value(match.group(2).strip())
        attrs[key] = value
    return attrs


def _strip_dat_value(value: str) -> str:
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def _safe_text(node: ET.Element | None) -> str | None:
    if node is None or node.text is None:
        return None
    value = node.text.strip()
    return value or None


def _parse_year(value: str | None) -> int | None:
    if not value:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) < 4:
        return None
    try:
        return int(digits[:4])
    except ValueError:
        return None


def _parse_rom_hashes(game_node: ET.Element) -> tuple[DatRomHash, ...]:
    hashes: list[DatRomHash] = []
    for rom in game_node.findall("rom"):
        name = (rom.get("name") or "").strip()
        if not name:
            continue
        hashes.append(
            DatRomHash(
                name=name,
                crc=_normalize_hex(rom.get("crc")),
                sha1=_normalize_hex(rom.get("sha1")),
            )
        )
    return tuple(hashes)


def _ensure_game_hashes(game: Game, hash_cache: dict[str, tuple[str, str]]) -> None:
    if game.crc and game.sha1:
        return
    rom_path = game.rom_path
    if not rom_path.exists() or not rom_path.is_file():
        return
    cache_key = rom_path.resolve().as_posix().lower()
    if cache_key not in hash_cache:
        hash_cache[cache_key] = _hash_file(rom_path)
    crc, sha1 = hash_cache[cache_key]
    if not game.crc:
        game.crc = crc
    if not game.sha1:
        game.sha1 = sha1


def _hash_file(path: Path) -> tuple[str, str]:
    crc = 0
    sha1 = hashlib.sha1()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            crc = zlib.crc32(chunk, crc)
            sha1.update(chunk)
    return f"{crc & 0xFFFFFFFF:08x}", sha1.hexdigest()
