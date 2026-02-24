from __future__ import annotations

from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

from retrometasync.config.ecosystems import (
    BATOCERA_SUFFIX_TO_ASSET_TYPE,
    ES_DE_MEDIA_FOLDER_TO_ASSET_TYPE,
    ES_FAMILY_TAG_TO_ASSET_TYPE,
    MEDIA_SUFFIX_HEURISTIC_GROUPS,
    MEDIA_SUFFIX_ORDERED,
    RETROARCH_THUMBNAIL_FOLDER_TO_ASSET_TYPE,
)
from retrometasync.config.system_aliases import canonicalize_system_id
from retrometasync.core.loaders.base import BaseLoader, LoaderInput, LoaderResult
from retrometasync.core.models import Asset, AssetType, AssetVerificationState, Game, MetadataSource, System

ROM_EXTENSIONS: set[str] = {
    ".zip",
    ".7z",
    ".rar",
    ".chd",
    ".cue",
    ".iso",
    ".bin",
    ".img",
    ".mdf",
    ".pbp",
    ".nes",
    ".unf",
    ".sfc",
    ".smc",
    ".fig",
    ".gba",
    ".gb",
    ".gbc",
    ".nds",
    ".3ds",
    ".n64",
    ".z64",
    ".v64",
    ".sms",
    ".gg",
    ".gen",
    ".md",
    ".32x",
    ".a26",
    ".a78",
    ".pce",
    ".sg",
    ".ngp",
    ".ngc",
    ".ws",
    ".wsc",
    ".lnx",
    ".m3u",
}

ASSET_EXTENSIONS: set[str] = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".bmp",
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".pdf",
    ".cbz",
    ".cbr",
}

ASSET_DIRECTORY_HINTS: set[str] = {
    "images",
    "videos",
    "manuals",
    "downloaded_images",
    "downloaded_videos",
    "downloaded_media",
    "covers",
    "screenshots",
    "miximages",
    "3dboxes",
    "backcovers",
    "titlescreens",
    "marquees",
    "fanart",
    "wheel",
    "boxart",
    "snaps",
    "named_boxarts",
    "named_snaps",
    "named_titles",
    "thumbnails",
    "imgs",
    "media",
}


class ESGamelistLoader(BaseLoader):
    ecosystem = "es_family"
    QUICK_SCAN_ROM_LIMIT = 60000

    def load(self, load_input: LoaderInput) -> LoaderResult:
        systems = list(load_input.systems)
        warnings: list[str] = []
        games_by_system: dict[str, list[Game]] = {}
        progress = load_input.progress_callback
        scan_mode = (load_input.scan_mode or "deep").strip().lower()
        force_mode = scan_mode == "force"
        meta_mode = scan_mode == "meta"
        quick_mode = scan_mode == "quick"
        metadata_only_mode = meta_mode or quick_mode

        if not systems:
            systems = (
                self._discover_systems_meta(load_input.source_root)
                if metadata_only_mode
                else self._discover_systems(load_input.source_root)
            )
            self._emit(progress, f"[scan] Discovered {len(systems)} systems from filesystem.")

        for system in systems:
            self._emit(progress, f"[scan] Reading system '{system.system_id}' at {system.rom_root}")
            rom_roots = self._rom_scan_roots(load_input.source_root, system)
            asset_roots = self._asset_scan_roots(load_input.source_root, system)

            if force_mode:
                games_by_system[system.system_id] = self._scan_games_without_metadata(
                    system,
                    include_assets=True,
                    max_asset_index_files=load_input.max_asset_index_files,
                    progress_callback=progress,
                    rom_roots=rom_roots,
                    asset_roots=asset_roots,
                )
                continue

            gamelist_path = self._resolve_gamelist_path(system)
            if gamelist_path and gamelist_path.exists():
                if gamelist_path not in system.metadata_paths:
                    system.metadata_paths.append(gamelist_path)
                system.metadata_source = MetadataSource.GAMELIST_XML

                try:
                    games_by_system[system.system_id] = self._parse_gamelist(
                        system,
                        gamelist_path,
                        deep_mode=not metadata_only_mode,
                        max_asset_index_files=load_input.max_asset_index_files,
                        progress_callback=progress,
                        rom_roots=rom_roots,
                        asset_roots=asset_roots,
                    )
                except ET.ParseError as exc:
                    warnings.append(f"Failed to parse {gamelist_path}: {exc}")
                    if meta_mode:
                        games_by_system[system.system_id] = []
                    else:
                        games_by_system[system.system_id] = self._scan_games_without_metadata(
                            system,
                            include_assets=not quick_mode,
                            max_asset_index_files=load_input.max_asset_index_files,
                            progress_callback=progress,
                            rom_roots=rom_roots,
                            asset_roots=asset_roots,
                        )
            else:
                warnings.append(f"Missing gamelist.xml for system '{system.system_id}'.")
                if meta_mode:
                    games_by_system[system.system_id] = []
                else:
                    games_by_system[system.system_id] = self._scan_games_without_metadata(
                        system,
                        include_assets=not quick_mode,
                        max_asset_index_files=load_input.max_asset_index_files,
                        progress_callback=progress,
                        rom_roots=rom_roots,
                        asset_roots=asset_roots,
                    )

        return LoaderResult(systems=systems, games_by_system=games_by_system, warnings=warnings)

    def _discover_systems(self, source_root: Path) -> list[System]:
        systems: list[System] = []
        seen: set[str] = set()

        for gamelist_path in self._collect_matches(source_root, "gamelist.xml", max_results=6000):
            system_dir = gamelist_path.parent
            system_id = canonicalize_system_id(system_dir.name)
            if system_id in seen:
                continue
            seen.add(system_id)
            systems.append(
                System(
                    system_id=system_id,
                    display_name=system_dir.name,
                    rom_root=system_dir,
                    metadata_source=MetadataSource.GAMELIST_XML,
                    metadata_paths=[gamelist_path],
                )
            )

        return sorted(systems, key=lambda item: item.system_id)

    def _discover_systems_meta(self, source_root: Path) -> list[System]:
        systems: list[System] = []
        seen: set[str] = set()
        candidates = [
            source_root,
            source_root / "roms",
            source_root / "Roms",
            source_root / "ES-DE" / "gamelists",
            source_root / ".emulationstation" / "gamelists",
        ]
        for candidate in candidates:
            if not candidate.exists() or not candidate.is_dir():
                continue
            direct = candidate / "gamelist.xml"
            if direct.exists():
                system_dir = direct.parent
                system_id = canonicalize_system_id(system_dir.name)
                if system_id not in seen:
                    seen.add(system_id)
                    systems.append(
                        System(
                            system_id=system_id,
                            display_name=system_dir.name,
                            rom_root=system_dir,
                            metadata_source=MetadataSource.GAMELIST_XML,
                            metadata_paths=[direct],
                        )
                    )
            for child in sorted(path for path in candidate.iterdir() if path.is_dir()):
                gamelist_path = child / "gamelist.xml"
                if not gamelist_path.exists():
                    continue
                system_id = canonicalize_system_id(child.name)
                if system_id in seen:
                    continue
                seen.add(system_id)
                systems.append(
                    System(
                        system_id=system_id,
                        display_name=child.name,
                        rom_root=child,
                        metadata_source=MetadataSource.GAMELIST_XML,
                        metadata_paths=[gamelist_path],
                    )
                )
        return sorted(systems, key=lambda item: item.system_id)

    @staticmethod
    def _resolve_gamelist_path(system: System) -> Path | None:
        if system.metadata_paths:
            for metadata_path in system.metadata_paths:
                if metadata_path.name.lower() == "gamelist.xml":
                    return metadata_path
            return system.metadata_paths[0]

        fallback = system.rom_root / "gamelist.xml"
        return fallback

    def _parse_gamelist(
        self,
        system: System,
        gamelist_path: Path,
        deep_mode: bool,
        max_asset_index_files: int,
        progress_callback=None,
        rom_roots: list[Path] | None = None,
        asset_roots: list[Path] | None = None,
    ) -> list[Game]:
        tree = ET.parse(gamelist_path)
        root = tree.getroot()
        games_by_rom: dict[str, Game] = {}
        self._emit(progress_callback, f"[scan] Parsing metadata: {gamelist_path}")

        for game_node in root.findall("game"):
            rom_ref = self._safe_text(game_node.find("path"))
            if not rom_ref:
                continue

            rom_path = self._resolve_path(rom_ref, rom_root=system.rom_root, metadata_dir=gamelist_path.parent)
            title = self._safe_text(game_node.find("name")) or rom_path.stem
            release_date = self._parse_release_date(self._safe_text(game_node.find("releasedate")))
            rating = self._parse_rating(self._safe_text(game_node.find("rating")))
            genres = self._split_multi(self._safe_text(game_node.find("genre")))

            game = Game(
                rom_path=rom_path,
                system_id=system.system_id,
                title=title,
                sort_title=self._safe_text(game_node.find("sortname")),
                release_date=release_date,
                developer=self._safe_text(game_node.find("developer")),
                publisher=self._safe_text(game_node.find("publisher")),
                rating=rating,
                genres=genres,
                regions=self._split_multi(self._safe_text(game_node.find("region"))),
                languages=self._split_multi(self._safe_text(game_node.find("lang"))),
                description=self._safe_text(game_node.find("desc")),
                favorite=self._parse_bool(self._safe_text(game_node.find("favorite"))),
                hidden=self._parse_bool(self._safe_text(game_node.find("hidden"))),
                players=self._safe_text(game_node.find("players")),
                playcount=self._parse_int(self._safe_text(game_node.find("playcount"))),
                last_played=self._parse_last_played(self._safe_text(game_node.find("lastplayed"))),
            )

            self._attach_assets_from_es_tags(
                game,
                game_node,
                system.rom_root,
                gamelist_path.parent,
                verify_paths=deep_mode,
            )
            games_by_rom[self._game_key(rom_path)] = game

        if not deep_mode:
            self._emit(
                progress_callback,
                f"[scan] Meta mode: skipping ROM and asset reconciliation for '{system.system_id}'.",
            )
            return sorted(games_by_rom.values(), key=lambda game: game.rom_filename.lower())

        # File-system reconciliation: add missing ROMs and discover assets not referenced in XML.
        scanned_games = self._scan_games_without_metadata(
            system,
            include_assets=True,
            max_asset_index_files=max_asset_index_files,
            progress_callback=progress_callback,
            rom_roots=rom_roots,
            asset_roots=asset_roots,
        )
        scanned_by_rom = {self._game_key(game.rom_path): game for game in scanned_games}

        for rom_key, scanned_game in scanned_by_rom.items():
            if rom_key not in games_by_rom:
                games_by_rom[rom_key] = scanned_game
                continue

            existing = games_by_rom[rom_key]
            known_assets = {asset.file_path.resolve().as_posix().lower() for asset in existing.assets}
            for asset in scanned_game.assets:
                key = asset.file_path.resolve().as_posix().lower()
                if key not in known_assets:
                    existing.assets.append(asset)
                    known_assets.add(key)

        return sorted(games_by_rom.values(), key=lambda game: game.rom_filename.lower())

    def _attach_assets_from_es_tags(
        self,
        game: Game,
        game_node: ET.Element,
        rom_root: Path,
        metadata_dir: Path,
        verify_paths: bool,
    ) -> None:
        for xml_tag, asset_type in ES_FAMILY_TAG_TO_ASSET_TYPE.items():
            value = self._safe_text(game_node.find(xml_tag))
            if not value:
                continue

            path = self._resolve_path(value, rom_root=rom_root, metadata_dir=metadata_dir)
            verification_state = AssetVerificationState.UNCHECKED
            if verify_paths:
                verification_state = (
                    AssetVerificationState.VERIFIED_EXISTS if path.exists() else AssetVerificationState.VERIFIED_MISSING
                )
            game.assets.append(
                Asset(
                    asset_type=asset_type,
                    file_path=path,
                    format=path.suffix.lower().lstrip(".") or None,
                    match_key="explicit_path",
                    verification_state=verification_state,
                )
            )

    def _scan_games_without_metadata(
        self,
        system: System,
        include_assets: bool,
        max_asset_index_files: int,
        progress_callback=None,
        rom_roots: list[Path] | None = None,
        asset_roots: list[Path] | None = None,
    ) -> list[Game]:
        effective_rom_roots = rom_roots or [system.rom_root]
        self._emit(progress_callback, f"[scan] Scanning ROM files under: {', '.join(str(p) for p in effective_rom_roots)}")
        games: list[Game] = []
        roms = self._scan_rom_files(effective_rom_roots)
        self._emit(progress_callback, f"[scan] Found {len(roms)} ROM files for system '{system.system_id}'.")
        asset_index: dict[str, list[Path]] = {}
        if include_assets:
            effective_asset_roots = asset_roots or [system.rom_root]
            asset_index = self._build_asset_index(
                effective_asset_roots,
                max_files=max_asset_index_files,
                progress_callback=progress_callback,
            )
        else:
            self._emit(progress_callback, f"[scan] Meta mode: asset indexing skipped for '{system.system_id}'.")
        for rom_path in roms:
            game = Game(
                rom_path=rom_path,
                system_id=system.system_id,
                title=rom_path.stem,
            )
            if asset_index:
                for asset in self._discover_assets_for_rom(rom_path, asset_index):
                    game.assets.append(asset)
            games.append(game)
        return sorted(games, key=lambda game: game.rom_filename.lower())

    def _scan_rom_files(self, rom_roots: list[Path]) -> list[Path]:
        roms: list[Path] = []
        seen: set[str] = set()
        for rom_root in rom_roots:
            if not rom_root.exists() or not rom_root.is_dir():
                continue
            if rom_root.name.lower() in ASSET_DIRECTORY_HINTS:
                continue
            for path in rom_root.rglob("*"):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in ROM_EXTENSIONS:
                    continue
                if self._is_under_asset_dir(path, rom_root):
                    continue
                key = path.resolve().as_posix().lower()
                if key in seen:
                    continue
                seen.add(key)
                roms.append(path.resolve())
        return roms

    def _discover_assets_for_rom(self, rom_path: Path, asset_index: dict[str, list[Path]]) -> list[Asset]:
        assets: list[Asset] = []
        basename = rom_path.stem.lower()
        for path in asset_index.get(basename, []):
            asset_type = self._infer_asset_type(path)
            assets.append(
                Asset(
                    asset_type=asset_type,
                    file_path=path.resolve(),
                    format=path.suffix.lower().lstrip(".") or None,
                    match_key=f"same_basename:{path.parent.name.lower()}",
                    verification_state=AssetVerificationState.VERIFIED_EXISTS,
                )
            )

        # De-duplicate while preserving order.
        unique: list[Asset] = []
        seen: set[str] = set()
        for asset in assets:
            key = asset.file_path.as_posix().lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(asset)
        return unique

    def _build_asset_index(self, asset_roots: list[Path], max_files: int, progress_callback=None) -> dict[str, list[Path]]:
        self._emit(progress_callback, f"[scan] Indexing assets under {len(asset_roots)} roots.")
        index: dict[str, list[Path]] = {}
        scanned = 0
        seen: set[str] = set()
        for asset_root in asset_roots:
            if not asset_root.exists() or not asset_root.is_dir():
                continue
            root_is_asset_dir = asset_root.name.lower() in ASSET_DIRECTORY_HINTS
            for path in asset_root.rglob("*"):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in ASSET_EXTENSIONS:
                    continue
                if not root_is_asset_dir and not self._is_under_asset_dir(path, asset_root):
                    continue
                key = path.resolve().as_posix().lower()
                if key in seen:
                    continue
                seen.add(key)
                scanned += 1
                stem_lower = path.stem.lower()
                normalized_stem = self._strip_asset_suffix(stem_lower)
                index.setdefault(normalized_stem, []).append(path.resolve())
                if scanned % 500 == 0:
                    self._emit(progress_callback, f"[scan] Indexed {scanned} asset files...")
                if scanned >= max_files:
                    self._emit(progress_callback, f"[scan] Asset index budget reached ({max_files}); stopping early.")
                    break
            if scanned >= max_files:
                break
        self._emit(progress_callback, f"[scan] Indexed {scanned} asset files total.")
        return index

    def _estimate_rom_count(self, rom_root: Path, budget: int) -> int:
        count = 0
        for path in rom_root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in ROM_EXTENSIONS:
                continue
            if self._is_under_asset_dir(path, rom_root):
                continue
            count += 1
            if count >= budget:
                break
        return count

    @staticmethod
    def _collect_matches(root: Path, pattern: str, max_results: int) -> list[Path]:
        results: list[Path] = []
        for path in root.rglob(pattern):
            results.append(path)
            if len(results) >= max_results:
                break
        return sorted(results)

    def _infer_asset_type(self, path: Path) -> AssetType:
        stem = path.stem.lower()
        parent = path.parent.name.lower()
        for suffix in MEDIA_SUFFIX_ORDERED:
            if stem.endswith(suffix):
                return BATOCERA_SUFFIX_TO_ASSET_TYPE[suffix]
        for asset_type, suffix_tokens in MEDIA_SUFFIX_HEURISTIC_GROUPS.items():
            for token in suffix_tokens:
                if stem.endswith(f"-{token}") or stem.endswith(f"_{token}"):
                    return asset_type
        suffix = path.suffix.lower()
        parent_lower_map = {name.lower(): value for name, value in ES_DE_MEDIA_FOLDER_TO_ASSET_TYPE.items()}
        if parent in parent_lower_map:
            return parent_lower_map[parent]
        retroarch_parent_map = {name.lower(): value for name, value in RETROARCH_THUMBNAIL_FOLDER_TO_ASSET_TYPE.items()}
        if parent in retroarch_parent_map:
            return retroarch_parent_map[parent]

        if suffix in {".mp4", ".mkv", ".avi", ".mov"} or "video" in parent:
            return AssetType.VIDEO
        if suffix in {".pdf", ".cbz", ".cbr"} or "manual" in parent:
            return AssetType.MANUAL
        if "marquee" in parent or "wheel" in parent:
            return AssetType.MARQUEE
        if "thumb" in parent or "screenshot" in parent:
            return AssetType.SCREENSHOT_GAMEPLAY
        if "bezel" in parent:
            return AssetType.BEZEL
        if "fanart" in parent:
            return AssetType.FANART
        return AssetType.BOX_FRONT

    @staticmethod
    def _strip_asset_suffix(stem: str) -> str:
        for suffix in MEDIA_SUFFIX_ORDERED:
            if stem.endswith(suffix):
                return stem[: -len(suffix)]
        for suffix_tokens in MEDIA_SUFFIX_HEURISTIC_GROUPS.values():
            for token in suffix_tokens:
                for separator in ("-", "_"):
                    candidate = f"{separator}{token}"
                    if stem.endswith(candidate):
                        return stem[: -len(candidate)]
        return stem

    @staticmethod
    def _unique_paths(paths: list[Path]) -> list[Path]:
        unique: list[Path] = []
        seen: set[str] = set()
        for path in paths:
            key = path.resolve().as_posix().lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(path)
        return unique

    def _rom_scan_roots(self, source_root: Path, system: System) -> list[Path]:
        roots = [system.rom_root]
        if system.detected_ecosystem == "es_de":
            roots.extend(
                [
                    source_root / "roms" / system.display_name,
                    source_root / "roms" / system.system_id,
                    source_root / "Roms" / system.display_name,
                    source_root / "Roms" / system.system_id,
                ]
            )
        return self._unique_paths(roots)

    def _asset_scan_roots(self, source_root: Path, system: System) -> list[Path]:
        roots = [system.rom_root]
        if system.detected_ecosystem == "es_de":
            roots.extend(
                [
                    source_root / "ES-DE" / "downloaded_media" / system.display_name,
                    source_root / "ES-DE" / "downloaded_media" / system.system_id,
                ]
            )
        if system.detected_ecosystem == "retroarch":
            roots.extend(
                [
                    source_root / "thumbnails" / system.display_name,
                    source_root / "thumbnails" / system.system_id,
                ]
            )
        return self._unique_paths(roots)

    @staticmethod
    def _is_under_asset_dir(path: Path, rom_root: Path) -> bool:
        try:
            relative = path.relative_to(rom_root)
        except ValueError:
            return False
        return any(part.lower() in ASSET_DIRECTORY_HINTS for part in relative.parts[:-1])

    @staticmethod
    def _game_key(path: Path) -> str:
        return path.resolve().as_posix().lower()

    @staticmethod
    def _emit(callback, message: str) -> None:
        if callback is not None:
            callback(message)

    @staticmethod
    def _resolve_path(path_value: str, rom_root: Path, metadata_dir: Path) -> Path:
        raw = Path(path_value)

        if path_value.startswith("~/"):
            return Path.home() / path_value[2:]
        if path_value.startswith("./"):
            return (rom_root / path_value[2:]).resolve()
        if raw.is_absolute():
            return raw
        return (metadata_dir / raw).resolve()

    @staticmethod
    def _safe_text(node: ET.Element | None) -> str | None:
        if node is None or node.text is None:
            return None
        value = node.text.strip()
        return value or None

    @staticmethod
    def _parse_release_date(value: str | None) -> datetime | None:
        if not value:
            return None

        # Common ES format: YYYYMMDDT000000
        try:
            return datetime.strptime(value, "%Y%m%dT%H%M%S")
        except ValueError:
            pass

        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None

    @classmethod
    def _parse_last_played(cls, value: str | None) -> datetime | None:
        if not value:
            return None
        # lastplayed commonly follows same ES datetime shape.
        parsed = cls._parse_release_date(value)
        if parsed is not None:
            return parsed
        for fmt in ("%Y%m%dT%H%M%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_rating(value: str | None) -> float | None:
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    @staticmethod
    def _parse_int(value: str | None) -> int | None:
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    @staticmethod
    def _parse_bool(value: str | None) -> bool:
        if not value:
            return False
        return value.strip().lower() in {"1", "true", "yes", "y"}

    @staticmethod
    def _split_multi(value: str | None) -> list[str]:
        if not value:
            return []
        normalized = value.replace(";", ",").replace("|", ",")
        return [item.strip() for item in normalized.split(",") if item.strip()]

