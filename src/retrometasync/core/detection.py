from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from retrometasync.config.ecosystems import ECOSYSTEMS, SIGNATURE_HINTS
from retrometasync.core.models import Library, MetadataSource, System

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

ASSET_DIRECTORY_HINTS: set[str] = {
    "images",
    "videos",
    "manuals",
    "downloaded_images",
    "downloaded_videos",
    "downloaded_media",
    "media",
    "thumbnails",
    "screenshots",
    "covers",
    "miximages",
}


@dataclass(slots=True)
class DetectionResult:
    source_root: Path
    detected_ecosystem: str
    detected_family: str
    confidence: float
    ecosystem_scores: dict[str, float] = field(default_factory=dict)
    systems: list[System] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_library(self) -> Library:
        systems_map = {system.system_id: system for system in self.systems}
        return Library(
            source_root=self.source_root,
            systems=systems_map,
            detected_ecosystem=self.detected_ecosystem,
            confidence=self.confidence,
        )


@dataclass(slots=True)
class _ScanFacts:
    has_lpl: bool = False
    has_pegasus_metadata: bool = False
    has_attract_cfg: bool = False
    has_romlists_dir: bool = False
    has_launchbox_platforms: bool = False
    has_launchbox_images: bool = False
    has_es_de_gamelists: bool = False
    has_es_de_downloaded_media: bool = False
    has_retrobat_ini: bool = False
    has_miyoo_gamelist: bool = False
    has_muos_catalogue: bool = False
    has_gamelist_xml: bool = False
    has_emulationstation_home: bool = False
    has_userdata_roms: bool = False
    has_onion_imgs_dir: bool = False
    has_batocera_suffix_media: bool = False
    has_retrobat_deep_images: bool = False


class LibraryDetector:
    """Detect a retro library ecosystem and enumerate system roots."""

    def __init__(self) -> None:
        self._progress_callback = None

    def detect(
        self,
        source_root: Path,
        progress_callback: Callable[[str], None] | None = None,
    ) -> DetectionResult:
        self._progress_callback = progress_callback
        root = source_root.expanduser().resolve()
        self._emit(progress_callback, f"[detect] Scanning root: {root}")
        facts = self._scan_facts(root)
        scores = self._score_ecosystems(root, facts)
        ecosystem = self._classify_ecosystem(facts, scores)
        family = self._family_for_ecosystem(ecosystem)
        confidence = self._confidence_for(ecosystem, scores)
        systems = self._enumerate_systems(root, ecosystem, facts)
        warnings = self._build_warnings(facts, ecosystem)
        self._emit(
            progress_callback,
            f"[detect] Ecosystem={ecosystem}, family={family}, confidence={confidence}, systems={len(systems)}",
        )

        return DetectionResult(
            source_root=root,
            detected_ecosystem=ecosystem,
            detected_family=family,
            confidence=confidence,
            ecosystem_scores=scores,
            systems=systems,
            warnings=warnings,
        )

    def _scan_facts(self, root: Path) -> _ScanFacts:
        facts = _ScanFacts()

        facts.has_lpl = self._has_any(root, "*.lpl")
        facts.has_pegasus_metadata = self._has_any(root, "metadata.pegasus.txt")
        facts.has_attract_cfg = self._has_any(root, "attract.cfg")
        facts.has_romlists_dir = self._path_exists(root / "romlists")
        facts.has_launchbox_platforms = self._path_exists(root / "LaunchBox" / "Data" / "Platforms")
        facts.has_launchbox_images = self._path_exists(root / "LaunchBox" / "Images")
        facts.has_es_de_gamelists = self._path_exists(root / "ES-DE" / "gamelists")
        facts.has_es_de_downloaded_media = self._path_exists(root / "ES-DE" / "downloaded_media")
        facts.has_retrobat_ini = self._has_any(root, "retrobat.ini")
        facts.has_miyoo_gamelist = self._has_any(root, "miyoogamelist.xml")
        facts.has_muos_catalogue = self._path_exists(root / "MUOS" / "info" / "catalogue")
        facts.has_gamelist_xml = self._has_any(root, "gamelist.xml")
        facts.has_emulationstation_home = self._path_exists(root / ".emulationstation")
        facts.has_userdata_roms = self._path_exists(root / "userdata" / "roms")
        facts.has_onion_imgs_dir = self._path_exists(root / "Roms") and self._has_dir_named(root / "Roms", "Imgs")
        facts.has_batocera_suffix_media = self._has_any(root, "*-image.png") or self._has_any(
            root, "*-marquee.png"
        )
        facts.has_retrobat_deep_images = self._path_exists(root / "roms") and (
            self._has_dir_named(root / "roms", "boxart") or self._has_dir_named(root / "roms", "wheel")
        )

        return facts

    def _score_ecosystems(self, root: Path, facts: _ScanFacts) -> dict[str, float]:
        scores = {ecosystem: 0.0 for ecosystem in ECOSYSTEMS}

        for ecosystem, hints in SIGNATURE_HINTS.items():
            for hint in hints:
                if self._hint_matches(root, hint):
                    scores[ecosystem] += 1.0

        if facts.has_retrobat_ini:
            scores["retrobat"] += 4.0
        if facts.has_es_de_downloaded_media:
            scores["es_de"] += 4.0
        if facts.has_launchbox_platforms:
            scores["launchbox"] += 4.0
        if facts.has_attract_cfg and facts.has_romlists_dir:
            scores["attract_mode"] += 4.0
        if facts.has_miyoo_gamelist and facts.has_onion_imgs_dir:
            scores["onionos"] += 4.0
        if facts.has_muos_catalogue:
            scores["muos"] += 4.0
        if facts.has_lpl:
            scores["retroarch"] += 3.0
        if facts.has_gamelist_xml:
            scores["es_classic"] += 1.5
            scores["batocera"] += 1.5
            scores["knulli"] += 1.0
            scores["amberelec"] += 1.0
            scores["jelos_rocknix"] += 1.0
            scores["arkos"] += 1.0
            scores["retrobat"] += 0.5
        if facts.has_batocera_suffix_media:
            scores["batocera"] += 3.0
        if facts.has_retrobat_deep_images:
            scores["retrobat"] += 2.5
        if facts.has_userdata_roms:
            scores["batocera"] += 2.0
        if facts.has_emulationstation_home:
            scores["es_classic"] += 2.0

        return scores

    def _classify_ecosystem(self, facts: _ScanFacts, scores: dict[str, float]) -> str:
        # Priority follows the detection guide decision tree.
        if facts.has_lpl:
            return "retroarch"
        if facts.has_pegasus_metadata:
            return "pegasus"
        if facts.has_attract_cfg and facts.has_romlists_dir:
            return "attract_mode"
        if facts.has_launchbox_platforms:
            return "launchbox"
        if facts.has_es_de_downloaded_media:
            return "es_de"
        if facts.has_retrobat_ini:
            return "retrobat"
        if facts.has_miyoo_gamelist and facts.has_onion_imgs_dir:
            return "onionos"
        if facts.has_muos_catalogue:
            return "muos"
        if facts.has_gamelist_xml:
            if facts.has_batocera_suffix_media or facts.has_userdata_roms:
                return "batocera"
            if facts.has_retrobat_deep_images:
                return "retrobat"
            if facts.has_emulationstation_home:
                return "es_classic"
            return "es_classic"

        # Final fallback: use highest score.
        return max(scores.items(), key=lambda item: item[1])[0]

    def _family_for_ecosystem(self, ecosystem: str) -> str:
        if ecosystem in {"es_classic", "batocera", "knulli", "amberelec", "jelos_rocknix", "arkos", "retrobat"}:
            return "es_family"
        if ecosystem in {"es_de", "emudeck", "retrodeck"}:
            return "es_de_family"
        if ecosystem == "launchbox":
            return "windows_launcher"
        if ecosystem == "attract_mode":
            return "arcade_frontend"
        if ecosystem == "pegasus":
            return "pegasus"
        if ecosystem == "retroarch":
            return "retroarch_playlist"
        if ecosystem in {"onionos", "muos"}:
            return "handheld_minimal"
        return "unknown"

    def _confidence_for(self, ecosystem: str, scores: dict[str, float]) -> float:
        if not scores:
            return 0.0

        sorted_scores = sorted(scores.values(), reverse=True)
        top = sorted_scores[0]
        second = sorted_scores[1] if len(sorted_scores) > 1 else 0.0
        margin = max(top - second, 0.0)
        selected = scores.get(ecosystem, 0.0)

        # Confidence combines absolute selected score and margin against runner-up.
        confidence = min(1.0, (selected / 8.0) + (margin / 10.0))
        return round(max(0.05, confidence), 2)

    def _enumerate_systems(self, root: Path, ecosystem: str, facts: _ScanFacts) -> list[System]:
        if ecosystem == "launchbox":
            return self._systems_from_launchbox(root)
        if ecosystem == "es_de":
            return self._systems_from_es_de(root)
        if ecosystem == "retroarch":
            return self._systems_from_retroarch(root)
        if ecosystem == "attract_mode":
            return self._systems_from_attract_mode(root)
        if ecosystem == "onionos":
            return self._systems_from_onion(root)
        if ecosystem == "muos":
            return self._systems_from_muos(root)
        if ecosystem == "pegasus":
            return self._systems_from_pegasus(root)

        # Default: ES-family detection by per-system gamelist folders.
        return self._systems_from_es_family(root, facts)

    def _systems_from_es_family(self, root: Path, facts: _ScanFacts) -> list[System]:
        systems: list[System] = []
        seen_ids: set[str] = set()

        gamelist_files = list(root.rglob("gamelist.xml"))
        if gamelist_files:
            self._emit(self._progress_callback, f"[detect] Found {len(gamelist_files)} gamelist.xml files.")
        for gamelist_path in gamelist_files:
            system_dir = gamelist_path.parent
            if system_dir.name.lower() in {"gamelists", "metadata"}:
                continue

            system_id = system_dir.name.lower()
            if system_id in seen_ids:
                continue
            seen_ids.add(system_id)

            systems.append(
                System(
                    system_id=system_id,
                    display_name=system_dir.name,
                    rom_root=system_dir,
                    metadata_source=MetadataSource.GAMELIST_XML,
                    metadata_paths=[gamelist_path],
                    detected_ecosystem="batocera" if facts.has_batocera_suffix_media else "es_classic",
                )
            )

        # Also include metadata-light systems inferred from real directories.
        for roms_root in self._candidate_rom_roots(root):
            self._emit(self._progress_callback, f"[detect] Scanning candidate ROM root: {roms_root}")
            for child in sorted(path for path in roms_root.iterdir() if path.is_dir()):
                if not self._looks_like_system_dir(child):
                    continue
                if child.name.lower() in {"images", "videos", "manuals"}:
                    continue
                system_id = child.name.lower()
                if system_id in seen_ids:
                    continue
                seen_ids.add(system_id)
                systems.append(
                    System(
                        system_id=system_id,
                        display_name=child.name,
                        rom_root=child,
                        metadata_source=MetadataSource.NONE,
                        detected_ecosystem="es_classic",
                    )
                )
                self._emit(self._progress_callback, f"[detect] Detected system folder: {child}")
        return sorted(systems, key=lambda item: item.system_id)

    def _systems_from_es_de(self, root: Path) -> list[System]:
        systems: list[System] = []
        seen_ids: set[str] = set()
        gamelists_root = root / "ES-DE" / "gamelists"
        if gamelists_root.exists():
            self._emit(self._progress_callback, f"[detect] ES-DE gamelist root found: {gamelists_root}")
            for system_dir in sorted(path for path in gamelists_root.iterdir() if path.is_dir()):
                gamelist_path = system_dir / "gamelist.xml"
                system_id = system_dir.name.lower()
                seen_ids.add(system_id)
                systems.append(
                    System(
                        system_id=system_id,
                        display_name=system_dir.name,
                        rom_root=system_dir,
                        metadata_source=MetadataSource.GAMELIST_XML,
                        metadata_paths=[gamelist_path] if gamelist_path.exists() else [],
                        detected_ecosystem="es_de",
                    )
                )

        for roms_root in self._candidate_rom_roots(root):
            self._emit(self._progress_callback, f"[detect] ES-DE fallback ROM scan root: {roms_root}")
            for child in sorted(path for path in roms_root.iterdir() if path.is_dir()):
                if not self._looks_like_system_dir(child):
                    continue
                system_id = child.name.lower()
                if system_id in seen_ids:
                    continue
                seen_ids.add(system_id)
                systems.append(
                    System(
                        system_id=system_id,
                        display_name=child.name,
                        rom_root=child,
                        metadata_source=MetadataSource.NONE,
                        detected_ecosystem="es_de",
                    )
                )
        return sorted(systems, key=lambda item: item.system_id)

    def _systems_from_launchbox(self, root: Path) -> list[System]:
        systems: list[System] = []
        platforms_root = root / "LaunchBox" / "Data" / "Platforms"
        if not platforms_root.exists():
            return systems

        for xml_path in sorted(platforms_root.glob("*.xml")):
            system_name = xml_path.stem
            systems.append(
                System(
                    system_id=system_name.lower().replace(" ", "_"),
                    display_name=system_name,
                    rom_root=root / "LaunchBox",
                    metadata_source=MetadataSource.LAUNCHBOX_XML,
                    metadata_paths=[xml_path],
                    detected_ecosystem="launchbox",
                )
            )
        return systems

    def _systems_from_retroarch(self, root: Path) -> list[System]:
        systems: list[System] = []
        for lpl_path in sorted(root.rglob("*.lpl")):
            system_name = lpl_path.stem
            systems.append(
                System(
                    system_id=system_name.lower().replace(" ", "_"),
                    display_name=system_name,
                    rom_root=lpl_path.parent,
                    metadata_source=MetadataSource.RETROARCH_LPL,
                    metadata_paths=[lpl_path],
                    detected_ecosystem="retroarch",
                )
            )
        return systems

    def _systems_from_attract_mode(self, root: Path) -> list[System]:
        systems: list[System] = []
        romlists_root = root / "romlists"
        if not romlists_root.exists():
            return systems

        for txt_path in sorted(romlists_root.glob("*.txt")):
            system_name = txt_path.stem
            systems.append(
                System(
                    system_id=system_name.lower().replace(" ", "_"),
                    display_name=system_name,
                    rom_root=root,
                    metadata_source=MetadataSource.ROMLIST_TXT,
                    metadata_paths=[txt_path],
                    detected_ecosystem="attract_mode",
                )
            )
        return systems

    def _systems_from_onion(self, root: Path) -> list[System]:
        systems: list[System] = []
        roms_root = root / "Roms"
        if not roms_root.exists():
            return systems

        for system_dir in sorted(path for path in roms_root.iterdir() if path.is_dir()):
            miyoo_path = system_dir / "miyoogamelist.xml"
            systems.append(
                System(
                    system_id=system_dir.name.lower(),
                    display_name=system_dir.name,
                    rom_root=system_dir,
                    metadata_source=MetadataSource.MIYOO_GAMELIST,
                    metadata_paths=[miyoo_path] if miyoo_path.exists() else [],
                    detected_ecosystem="onionos",
                )
            )
        return systems

    def _systems_from_muos(self, root: Path) -> list[System]:
        systems: list[System] = []
        catalogue_root = root / "MUOS" / "info" / "catalogue"
        if not catalogue_root.exists():
            return systems

        for system_dir in sorted(path for path in catalogue_root.iterdir() if path.is_dir()):
            systems.append(
                System(
                    system_id=system_dir.name.lower(),
                    display_name=system_dir.name,
                    rom_root=root,
                    metadata_source=MetadataSource.NONE,
                    metadata_paths=[],
                    detected_ecosystem="muos",
                )
            )
        return systems

    def _systems_from_pegasus(self, root: Path) -> list[System]:
        systems: list[System] = []
        for metadata_file in sorted(root.rglob("metadata.pegasus.txt")):
            system_dir = metadata_file.parent
            systems.append(
                System(
                    system_id=system_dir.name.lower(),
                    display_name=system_dir.name,
                    rom_root=system_dir,
                    metadata_source=MetadataSource.METADATA_PEGASUS,
                    metadata_paths=[metadata_file],
                    detected_ecosystem="pegasus",
                )
            )
        return systems

    def _build_warnings(self, facts: _ScanFacts, ecosystem: str) -> list[str]:
        warnings: list[str] = []
        if facts.has_lpl and facts.has_gamelist_xml:
            warnings.append("Both RetroArch playlists and gamelist.xml were found; library may be hybrid.")
        if ecosystem == "es_classic" and not facts.has_emulationstation_home and facts.has_gamelist_xml:
            warnings.append("ES-family detected without .emulationstation root; using generic ES-classic fallback.")
        return warnings

    @staticmethod
    def _path_exists(path: Path) -> bool:
        return path.exists()

    @staticmethod
    def _has_any(root: Path, pattern: str) -> bool:
        return next(root.rglob(pattern), None) is not None

    @staticmethod
    def _has_dir_named(root: Path, directory_name: str) -> bool:
        directory_name = directory_name.lower()
        for path in root.rglob("*"):
            if path.is_dir() and path.name.lower() == directory_name:
                return True
        return False

    def _hint_matches(self, root: Path, hint: str) -> bool:
        if "/" in hint:
            return (root / hint).exists()
        if "*" in hint:
            return self._has_any(root, hint)
        return self._has_any(root, hint) or (root / hint).exists()

    @staticmethod
    def _emit(callback: Callable[[str], None] | None, message: str) -> None:
        if callback is not None:
            callback(message)

    @staticmethod
    def _candidate_rom_roots(root: Path) -> list[Path]:
        candidates = [root / "roms", root / "Roms", root]
        seen: set[str] = set()
        unique: list[Path] = []
        for candidate in candidates:
            key = candidate.as_posix().lower()
            if key in seen or not candidate.exists() or not candidate.is_dir():
                continue
            seen.add(key)
            unique.append(candidate)
        return unique

    def _looks_like_system_dir(self, path: Path) -> bool:
        if (path / "gamelist.xml").exists():
            return True
        if path.name.lower() in ASSET_DIRECTORY_HINTS:
            return False
        for file_path in path.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() in ROM_EXTENSIONS:
                return True
        return False
