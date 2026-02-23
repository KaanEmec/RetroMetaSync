from __future__ import annotations

from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

from retrometasync.config.ecosystems import ES_FAMILY_TAG_TO_ASSET_TYPE
from retrometasync.core.loaders.base import BaseLoader, LoaderInput, LoaderResult
from retrometasync.core.models import Asset, Game, MetadataSource, System


class ESGamelistLoader(BaseLoader):
    ecosystem = "es_family"

    def load(self, load_input: LoaderInput) -> LoaderResult:
        systems = list(load_input.systems)
        warnings: list[str] = []
        games_by_system: dict[str, list[Game]] = {}

        if not systems:
            systems = self._discover_systems(load_input.source_root)

        for system in systems:
            gamelist_path = self._resolve_gamelist_path(system)
            if not gamelist_path or not gamelist_path.exists():
                warnings.append(f"Missing gamelist.xml for system '{system.system_id}'.")
                games_by_system[system.system_id] = []
                continue

            if gamelist_path not in system.metadata_paths:
                system.metadata_paths.append(gamelist_path)
            system.metadata_source = MetadataSource.GAMELIST_XML

            try:
                games_by_system[system.system_id] = self._parse_gamelist(system, gamelist_path)
            except ET.ParseError as exc:
                warnings.append(f"Failed to parse {gamelist_path}: {exc}")
                games_by_system[system.system_id] = []

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

    def _parse_gamelist(self, system: System, gamelist_path: Path) -> list[Game]:
        tree = ET.parse(gamelist_path)
        root = tree.getroot()
        games: list[Game] = []

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
            games.append(game)

        return games

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

