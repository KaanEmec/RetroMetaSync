from __future__ import annotations

from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

from retrometasync.config.system_aliases import canonicalize_system_id
from retrometasync.core.loaders.base import BaseLoader, LoaderInput, LoaderResult
from retrometasync.core.models import Asset, AssetType, AssetVerificationState, Game, MetadataSource, System


class LaunchBoxXmlLoader(BaseLoader):
    ecosystem = "launchbox"

    def load(self, load_input: LoaderInput) -> LoaderResult:
        source_root = load_input.source_root
        warnings: list[str] = []
        systems = list(load_input.systems) or self._discover_systems(source_root)
        games_by_system: dict[str, list[Game]] = {}
        progress = load_input.progress_callback
        if progress is not None:
            progress(f"[scan] LaunchBox systems discovered: {len(systems)}")

        for system in systems:
            if progress is not None:
                progress(f"[scan] Reading LaunchBox platform '{system.display_name}'")
            xml_path = self._resolve_platform_xml(system, source_root)
            if xml_path is None or not xml_path.exists():
                warnings.append(f"Missing LaunchBox platform XML for '{system.system_id}'.")
                games_by_system[system.system_id] = []
                continue

            if xml_path not in system.metadata_paths:
                system.metadata_paths.append(xml_path)
            system.metadata_source = MetadataSource.LAUNCHBOX_XML

            try:
                games_by_system[system.system_id] = self._parse_platform_xml(
                    system,
                    xml_path,
                    source_root,
                    progress_callback=progress,
                )
            except ET.ParseError as exc:
                warnings.append(f"Failed to parse {xml_path}: {exc}")
                games_by_system[system.system_id] = []

        return LoaderResult(systems=systems, games_by_system=games_by_system, warnings=warnings)

    def _discover_systems(self, source_root: Path) -> list[System]:
        systems: list[System] = []
        launchbox_root = self._launchbox_root(source_root)
        platforms_root = launchbox_root / "Data" / "Platforms"
        if not platforms_root.exists():
            return systems

        for xml_path in sorted(platforms_root.glob("*.xml")):
            display_name = xml_path.stem
            systems.append(
                System(
                    system_id=self._to_system_id(display_name),
                    display_name=display_name,
                    rom_root=launchbox_root,
                    metadata_source=MetadataSource.LAUNCHBOX_XML,
                    metadata_paths=[xml_path],
                    detected_ecosystem="launchbox",
                )
            )
        return systems

    @staticmethod
    def _resolve_platform_xml(system: System, source_root: Path) -> Path | None:
        if system.metadata_paths:
            return system.metadata_paths[0]

        launchbox_root = LaunchBoxXmlLoader._launchbox_root(source_root)
        candidate = launchbox_root / "Data" / "Platforms" / f"{system.display_name}.xml"
        return candidate if candidate.exists() else None

    def _parse_platform_xml(
        self,
        system: System,
        xml_path: Path,
        source_root: Path,
        progress_callback=None,
    ) -> list[Game]:
        games: list[Game] = []
        launchbox_root = self._launchbox_root(source_root)
        parsed = 0

        for event, game_node in ET.iterparse(xml_path, events=("end",)):
            if event != "end" or game_node.tag != "Game":
                continue
            app_path_text = self._safe_text(game_node.find("ApplicationPath"))
            if not app_path_text:
                game_node.clear()
                continue

            rom_path = self._resolve_path(app_path_text, launchbox_root)
            title = self._safe_text(game_node.find("Title")) or rom_path.stem
            game = Game(
                rom_path=rom_path,
                system_id=system.system_id,
                title=title,
                sort_title=self._safe_text(game_node.find("SortTitle")),
                release_date=self._parse_release_date(self._safe_text(game_node.find("ReleaseDate"))),
                developer=self._safe_text(game_node.find("Developer")),
                publisher=self._safe_text(game_node.find("Publisher")),
                rating=self._parse_rating(
                    self._safe_text(game_node.find("CommunityStarRating"))
                    or self._safe_text(game_node.find("StarRating"))
                ),
                genres=self._split_genre(self._safe_text(game_node.find("Genre"))),
                regions=self._split_genre(self._safe_text(game_node.find("Region"))),
                languages=self._split_genre(self._safe_text(game_node.find("Language"))),
                description=self._safe_text(game_node.find("Notes")),
                favorite=self._parse_bool(self._safe_text(game_node.find("Favorite"))),
                playcount=self._parse_int(
                    self._safe_text(game_node.find("PlayCount")) or self._safe_text(game_node.find("PlayCounter"))
                ),
                last_played=self._parse_release_date(
                    self._safe_text(game_node.find("LastPlayedDate")) or self._safe_text(game_node.find("LastPlayed"))
                ),
            )

            manual_path = self._safe_text(game_node.find("ManualPath"))
            if manual_path:
                manual_resolved = self._resolve_path(manual_path, launchbox_root)
                game.assets.append(
                    Asset(
                        asset_type=AssetType.MANUAL,
                        file_path=manual_resolved,
                        format=manual_resolved.suffix.lower().lstrip(".") or None,
                        match_key="explicit_path",
                        verification_state=AssetVerificationState.UNCHECKED,
                    )
                )

            self._append_asset_if_present(game, launchbox_root, game_node, "FrontImagePath", AssetType.BOX_FRONT)
            self._append_asset_if_present(game, launchbox_root, game_node, "BackgroundImagePath", AssetType.FANART)
            self._append_asset_if_present(game, launchbox_root, game_node, "ScreenshotImagePath", AssetType.SCREENSHOT_GAMEPLAY)
            self._append_asset_if_present(game, launchbox_root, game_node, "VideoPath", AssetType.VIDEO)
            self._append_asset_if_present(game, launchbox_root, game_node, "LogoImagePath", AssetType.LOGO)

            games.append(game)
            parsed += 1
            if progress_callback is not None and parsed % 500 == 0:
                progress_callback(f"[scan] {system.display_name}: parsed {parsed} LaunchBox entries")
            game_node.clear()

        return games

    @staticmethod
    def _resolve_path(path_value: str, launchbox_root: Path) -> Path:
        normalized = path_value.strip().strip('"')
        if normalized.startswith(("\\", "/")):
            return launchbox_root / normalized.lstrip("\\/")
        candidate = Path(normalized)
        if candidate.is_absolute() and getattr(candidate, "drive", ""):
            return candidate
        parts = list(candidate.parts)
        if parts and parts[0].lower() == "launchbox":
            candidate = Path(*parts[1:])
        return launchbox_root / candidate

    @staticmethod
    def _launchbox_root(source_root: Path) -> Path:
        if (source_root / "Data" / "Platforms").exists():
            return source_root
        if (source_root / "LaunchBox" / "Data" / "Platforms").exists():
            return source_root / "LaunchBox"
        if source_root.name.lower() == "data" and (source_root / "Platforms").exists():
            return source_root.parent
        return source_root

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
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%m/%d/%Y", "%Y"):
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
    def _split_genre(value: str | None) -> list[str]:
        if not value:
            return []
        return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]

    @staticmethod
    def _parse_bool(value: str | None) -> bool:
        if not value:
            return False
        return value.strip().lower() in {"1", "true", "yes", "y"}

    @staticmethod
    def _parse_int(value: str | None) -> int | None:
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def _append_asset_if_present(
        self,
        game: Game,
        source_root: Path,
        game_node: ET.Element,
        xml_tag: str,
        asset_type: AssetType,
    ) -> None:
        value = self._safe_text(game_node.find(xml_tag))
        if not value:
            return
        resolved = self._resolve_path(value, source_root)
        game.assets.append(
            Asset(
                asset_type=asset_type,
                file_path=resolved,
                format=resolved.suffix.lower().lstrip(".") or None,
                match_key="explicit_path",
                verification_state=AssetVerificationState.UNCHECKED,
            )
        )

    @staticmethod
    def _to_system_id(display_name: str) -> str:
        return canonicalize_system_id(display_name)

