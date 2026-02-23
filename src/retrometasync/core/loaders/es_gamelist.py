from __future__ import annotations

from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

from retrometasync.config.ecosystems import ES_FAMILY_TAG_TO_ASSET_TYPE
from retrometasync.core.loaders.base import BaseLoader, LoaderInput, LoaderResult
from retrometasync.core.models import Asset, AssetType, Game, MetadataSource, System

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
    "thumbnails",
    "imgs",
    "media",
}


class ESGamelistLoader(BaseLoader):
    ecosystem = "es_family"

    def load(self, load_input: LoaderInput) -> LoaderResult:
        systems = list(load_input.systems)
        warnings: list[str] = []
        games_by_system: dict[str, list[Game]] = {}
        progress = load_input.progress_callback

        if not systems:
            systems = self._discover_systems(load_input.source_root)
            self._emit(progress, f"[scan] Discovered {len(systems)} systems from filesystem.")

        for system in systems:
            self._emit(progress, f"[scan] Reading system '{system.system_id}' at {system.rom_root}")
            gamelist_path = self._resolve_gamelist_path(system)
            if gamelist_path and gamelist_path.exists():
                if gamelist_path not in system.metadata_paths:
                    system.metadata_paths.append(gamelist_path)
                system.metadata_source = MetadataSource.GAMELIST_XML

                try:
                    games_by_system[system.system_id] = self._parse_gamelist(
                        system,
                        gamelist_path,
                        progress_callback=progress,
                    )
                except ET.ParseError as exc:
                    warnings.append(f"Failed to parse {gamelist_path}: {exc}")
                    games_by_system[system.system_id] = self._scan_games_without_metadata(system, progress_callback=progress)
            else:
                warnings.append(f"Missing gamelist.xml for system '{system.system_id}'. Falling back to file scan.")
                games_by_system[system.system_id] = self._scan_games_without_metadata(system, progress_callback=progress)

        return LoaderResult(systems=systems, games_by_system=games_by_system, warnings=warnings)

    def _discover_systems(self, source_root: Path) -> list[System]:
        systems: list[System] = []
        seen: set[str] = set()

        for gamelist_path in source_root.rglob("gamelist.xml"):
            system_dir = gamelist_path.parent
            system_id = system_dir.name.lower()
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
        progress_callback=None,
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

            self._attach_assets_from_es_tags(game, game_node, system.rom_root, gamelist_path.parent)
            games_by_rom[self._game_key(rom_path)] = game

        # File-system reconciliation: add missing ROMs and discover assets not referenced in XML.
        scanned_games = self._scan_games_without_metadata(system, progress_callback=progress_callback)
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
        self, game: Game, game_node: ET.Element, rom_root: Path, metadata_dir: Path
    ) -> None:
        for xml_tag, asset_type in ES_FAMILY_TAG_TO_ASSET_TYPE.items():
            value = self._safe_text(game_node.find(xml_tag))
            if not value:
                continue

            path = self._resolve_path(value, rom_root=rom_root, metadata_dir=metadata_dir)
            game.assets.append(
                Asset(
                    asset_type=asset_type,
                    file_path=path,
                    format=path.suffix.lower().lstrip(".") or None,
                    match_key="explicit_path",
                )
            )

    def _scan_games_without_metadata(self, system: System, progress_callback=None) -> list[Game]:
        self._emit(progress_callback, f"[scan] Scanning ROM files under: {system.rom_root}")
        games: list[Game] = []
        roms = self._scan_rom_files(system.rom_root)
        self._emit(progress_callback, f"[scan] Found {len(roms)} ROM files for system '{system.system_id}'.")
        asset_index = self._build_asset_index(system.rom_root, progress_callback=progress_callback)
        for rom_path in roms:
            game = Game(
                rom_path=rom_path,
                system_id=system.system_id,
                title=rom_path.stem,
            )
            for asset in self._discover_assets_for_rom(rom_path, asset_index):
                game.assets.append(asset)
            games.append(game)
        return sorted(games, key=lambda game: game.rom_filename.lower())

    def _scan_rom_files(self, rom_root: Path) -> list[Path]:
        roms: list[Path] = []
        for path in rom_root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in ROM_EXTENSIONS:
                continue
            if self._is_under_asset_dir(path, rom_root):
                continue
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
                    match_key="same_basename",
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

    def _build_asset_index(self, rom_root: Path, progress_callback=None) -> dict[str, list[Path]]:
        self._emit(progress_callback, f"[scan] Indexing assets under: {rom_root}")
        index: dict[str, list[Path]] = {}
        scanned = 0
        for path in rom_root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in ASSET_EXTENSIONS:
                continue
            if not self._is_under_asset_dir(path, rom_root):
                continue
            scanned += 1
            stem_lower = path.stem.lower()
            normalized_stem = self._strip_asset_suffix(stem_lower)
            index.setdefault(normalized_stem, []).append(path.resolve())
            if scanned % 500 == 0:
                self._emit(progress_callback, f"[scan] Indexed {scanned} asset files...")
        self._emit(progress_callback, f"[scan] Indexed {scanned} asset files total.")
        return index

    def _infer_asset_type(self, path: Path) -> AssetType:
        stem = path.stem.lower()
        parent = path.parent.name.lower()
        suffix = path.suffix.lower()

        if suffix in {".mp4", ".mkv", ".avi", ".mov"} or "video" in parent:
            return AssetType.VIDEO
        if suffix in {".pdf", ".cbz", ".cbr"} or "manual" in parent:
            return AssetType.MANUAL
        if stem.endswith("-marquee") or "marquee" in parent or "wheel" in parent:
            return AssetType.MARQUEE
        if stem.endswith("-thumb") or "thumb" in parent or "screenshot" in parent:
            return AssetType.SCREENSHOT_GAMEPLAY
        if stem.endswith("-bezel"):
            return AssetType.BEZEL
        if "fanart" in parent:
            return AssetType.FANART
        return AssetType.BOX_FRONT

    @staticmethod
    def _strip_asset_suffix(stem: str) -> str:
        for suffix in ("-image", "-thumb", "-marquee", "-video", "-bezel", "-fanart", "-manual"):
            if stem.endswith(suffix):
                return stem[: -len(suffix)]
        return stem

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

