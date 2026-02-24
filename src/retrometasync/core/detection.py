from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from retrometasync.config.ecosystems import BATOCERA_SUFFIX_TO_ASSET_TYPE, ECOSYSTEMS, SIGNATURE_HINTS
from retrometasync.config.system_aliases import canonicalize_system_id
from retrometasync.core.models import Library, MetadataSource, System


class DetectionCancelled(Exception):
    """Raised when library detection is cancelled by the user."""


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
    scan_mode: str = "deep"

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
    launchbox_root: Path | None = None


class LibraryDetector:
    """Detect a retro library ecosystem and enumerate system roots."""

    def __init__(self) -> None:
        self._progress_callback = None
        self._cancel_requested: Callable[[], bool] | None = None
        self._has_any_cache: dict[tuple[str, str], bool] = {}
        self._has_dir_named_cache: dict[tuple[str, str], bool] = {}
        self._system_dir_scan_cache: dict[str, bool] = {}

    def detect(
        self,
        source_root: Path,
        progress_callback: Callable[[str], None] | None = None,
        preferred_ecosystem: str | None = None,
        scan_mode: str = "deep",
        cancel_requested: Callable[[], bool] | None = None,
    ) -> DetectionResult:
        self._progress_callback = progress_callback
        self._cancel_requested = cancel_requested
        self._has_any_cache.clear()
        self._has_dir_named_cache.clear()
        self._system_dir_scan_cache.clear()
        selected_root = source_root.expanduser().resolve()
        normalized_scan_mode = (scan_mode or "deep").strip().lower()
        preferred = (preferred_ecosystem or "").strip().lower() or None
        self._check_cancel()

        if normalized_scan_mode == "single_rom_folder":
            return self._single_rom_folder_result(selected_root, normalized_scan_mode)

        launchbox_root = self._launchbox_root_from_selected(selected_root)
        if normalized_scan_mode == "meta":
            root = launchbox_root or selected_root
            self._emit(progress_callback, f"[detect] Metadata-only scan root: {root}")
            facts = self._scan_facts_meta(root)
            scores = self._score_ecosystems(root, facts)
            ecosystem = self._classify_ecosystem(facts, scores)
            family = self._family_for_ecosystem(ecosystem)
            confidence = self._confidence_for(ecosystem, scores)
            systems = self._enumerate_systems_meta(root, ecosystem, facts)
            warnings = self._build_warnings(facts, ecosystem)
            self._emit(
                progress_callback,
                f"[detect] Meta ecosystem={ecosystem}, family={family}, confidence={confidence}, systems={len(systems)}",
            )
            return DetectionResult(
                source_root=root,
                detected_ecosystem=ecosystem,
                detected_family=family,
                confidence=confidence,
                ecosystem_scores=scores,
                systems=systems,
                warnings=warnings,
                scan_mode=normalized_scan_mode,
            )

        self._check_cancel()
        preferred_result = self._detect_from_preference(selected_root, preferred)
        if preferred_result is not None:
            self._emit(progress_callback, f"[detect] Preferred source mode '{preferred}' accepted.")
            preferred_result.scan_mode = normalized_scan_mode
            return preferred_result

        # If caller explicitly picks LaunchBox mode, trust that hint and bypass heavy generic probing.
        if (preferred_ecosystem == "launchbox" or normalized_scan_mode == "launchbox") and launchbox_root is not None:
            root = launchbox_root
            self._emit(progress_callback, f"[detect] LaunchBox mode enabled. Using root: {root}")
            facts = _ScanFacts(
                has_launchbox_platforms=True,
                has_launchbox_images=self._path_exists(root / "Images"),
                launchbox_root=root,
            )
            scores = {ecosystem: 0.0 for ecosystem in ECOSYSTEMS}
            scores["launchbox"] = 10.0
            ecosystem = "launchbox"
            family = self._family_for_ecosystem(ecosystem)
            confidence = 1.0
            systems = self._enumerate_systems(root, ecosystem, facts)
            warnings = self._build_warnings(facts, ecosystem)
            return DetectionResult(
                source_root=root,
                detected_ecosystem=ecosystem,
                detected_family=family,
                confidence=confidence,
                ecosystem_scores=scores,
                systems=systems,
                warnings=warnings,
                scan_mode=normalized_scan_mode,
            )

        root = launchbox_root or selected_root
        self._check_cancel()
        quick_result = self._auto_fast_detect(root)
        if quick_result is not None:
            ecosystem, quick_facts = quick_result
            self._emit(progress_callback, f"[detect] Fast-path ecosystem match: {ecosystem}")
            scores = {name: 0.0 for name in ECOSYSTEMS}
            scores[ecosystem] = 10.0
            systems = self._enumerate_systems(root, ecosystem, quick_facts)
            return DetectionResult(
                source_root=root,
                detected_ecosystem=ecosystem,
                detected_family=self._family_for_ecosystem(ecosystem),
                confidence=1.0,
                ecosystem_scores=scores,
                systems=systems,
                warnings=self._build_warnings(quick_facts, ecosystem),
                scan_mode=normalized_scan_mode,
            )

        self._emit(progress_callback, f"[detect] Scanning root: {root}")
        self._check_cancel()
        facts = self._scan_facts(root)
        self._check_cancel()
        scores = self._score_ecosystems(root, facts)
        ecosystem = self._classify_ecosystem(facts, scores)
        family = self._family_for_ecosystem(ecosystem)
        confidence = self._confidence_for(ecosystem, scores)
        self._check_cancel()
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
            scan_mode=normalized_scan_mode,
        )

    def _single_rom_folder_result(self, source_root: Path, scan_mode: str) -> DetectionResult:
        system_id = canonicalize_system_id(source_root.name)
        system = System(
            system_id=system_id,
            display_name=source_root.name,
            rom_root=source_root,
            metadata_source=MetadataSource.NONE,
            metadata_paths=[],
            detected_ecosystem="es_classic",
        )
        scores = {name: 0.0 for name in ECOSYSTEMS}
        scores["es_classic"] = 10.0
        return DetectionResult(
            source_root=source_root,
            detected_ecosystem="es_classic",
            detected_family="es_family",
            confidence=1.0,
            ecosystem_scores=scores,
            systems=[system],
            warnings=[],
            scan_mode=scan_mode,
        )

    def _scan_facts(self, root: Path) -> _ScanFacts:
        facts = _ScanFacts()
        self._check_cancel()

        # LaunchBox fast-path: avoid deep recursive scans for huge NAS roots.
        launchbox_root = self._launchbox_root_from_selected(root)
        if launchbox_root is not None:
            facts.has_launchbox_platforms = True
            facts.has_launchbox_images = self._path_exists(launchbox_root / "Images")
            facts.launchbox_root = launchbox_root
            return facts

        # Cheap top-level checks first.
        facts.has_romlists_dir = self._path_exists(root / "romlists")
        facts.has_es_de_gamelists = self._path_exists(root / "ES-DE" / "gamelists")
        facts.has_es_de_downloaded_media = self._path_exists(root / "ES-DE" / "downloaded_media")
        facts.has_muos_catalogue = self._path_exists(root / "MUOS" / "info" / "catalogue")
        facts.has_emulationstation_home = self._path_exists(root / ".emulationstation")
        facts.has_userdata_roms = self._path_exists(root / "userdata" / "roms")

        facts.has_lpl = self._has_any(root, "*.lpl")
        facts.has_pegasus_metadata = self._has_any(root, "metadata.pegasus.txt")
        facts.has_attract_cfg = self._has_any(root, "attract.cfg")
        facts.has_retrobat_ini = self._has_any(root, "retrobat.ini")
        facts.has_miyoo_gamelist = self._has_any(root, "miyoogamelist.xml")
        facts.has_gamelist_xml = self._has_any(root, "gamelist.xml")
        facts.has_onion_imgs_dir = self._path_exists(root / "Roms") and self._has_dir_named(root / "Roms", "Imgs")
        facts.has_batocera_suffix_media = any(
            self._has_any(root, f"*{suffix}.*") for suffix in BATOCERA_SUFFIX_TO_ASSET_TYPE
        )
        facts.has_retrobat_deep_images = self._path_exists(root / "roms") and (
            self._has_dir_named(root / "roms", "boxart") or self._has_dir_named(root / "roms", "wheel")
        )

        return facts

    def _scan_facts_meta(self, root: Path) -> _ScanFacts:
        facts = _ScanFacts()
        self._check_cancel()

        launchbox_root = self._launchbox_root_from_selected(root)
        if launchbox_root is not None:
            facts.has_launchbox_platforms = True
            facts.has_launchbox_images = self._path_exists(launchbox_root / "Images")
            facts.launchbox_root = launchbox_root
            return facts

        facts.has_romlists_dir = self._path_exists(root / "romlists")
        facts.has_es_de_gamelists = self._path_exists(root / "ES-DE" / "gamelists")
        facts.has_es_de_downloaded_media = self._path_exists(root / "ES-DE" / "downloaded_media")
        facts.has_muos_catalogue = self._path_exists(root / "MUOS" / "info" / "catalogue")
        facts.has_emulationstation_home = self._path_exists(root / ".emulationstation")
        facts.has_userdata_roms = self._path_exists(root / "userdata" / "roms")
        facts.has_attract_cfg = self._path_exists(root / "attract.cfg")
        facts.has_retrobat_ini = self._path_exists(root / "retrobat.ini")

        roms_root = root / "Roms"
        facts.has_onion_imgs_dir = self._path_exists(roms_root / "Imgs")
        facts.has_miyoo_gamelist = self._any_glob(roms_root, "*/miyoogamelist.xml")
        facts.has_lpl = self._any_glob(root / "playlists", "*.lpl") or self._any_glob(root, "*.lpl")
        facts.has_pegasus_metadata = self._path_exists(root / "metadata.pegasus.txt") or self._any_glob(
            root, "*/metadata.pegasus.txt"
        )
        facts.has_gamelist_xml = bool(self._collect_gamelists_meta(root))
        return facts

    def _detect_from_preference(self, selected_root: Path, preferred_ecosystem: str | None) -> DetectionResult | None:
        if preferred_ecosystem is None:
            return None
        if preferred_ecosystem == "launchbox":
            root = self._launchbox_root_from_selected(selected_root)
            if root is None:
                return None
            facts = _ScanFacts(
                has_launchbox_platforms=True,
                has_launchbox_images=self._path_exists(root / "Images"),
                launchbox_root=root,
            )
            return self._preferred_detection_result(root, "launchbox", facts)

        preferred_map: dict[str, str] = {
            "es family": "es_classic",
            "es_family": "es_classic",
            "es_family (gamelist)": "es_classic",
            "es_de": "es_de",
            "retrobat": "retrobat",
            "retroarch": "retroarch",
            "retroarch/playlist": "retroarch",
            "attractmode": "attract_mode",
            "attract_mode": "attract_mode",
            "pegasus": "pegasus",
            "onionos": "onionos",
            "muos": "muos",
        }
        target_ecosystem = preferred_map.get(preferred_ecosystem, preferred_ecosystem)
        if not self._preferred_hint_matches(selected_root, target_ecosystem):
            return None
        facts = self._scan_facts(selected_root)
        return self._preferred_detection_result(selected_root, target_ecosystem, facts)

    def _preferred_detection_result(self, root: Path, ecosystem: str, facts: _ScanFacts) -> DetectionResult:
        scores = {name: 0.0 for name in ECOSYSTEMS}
        if ecosystem in scores:
            scores[ecosystem] = 10.0
        systems = self._enumerate_systems(root, ecosystem, facts)
        return DetectionResult(
            source_root=root,
            detected_ecosystem=ecosystem,
            detected_family=self._family_for_ecosystem(ecosystem),
            confidence=1.0,
            ecosystem_scores=scores,
            systems=systems,
            warnings=self._build_warnings(facts, ecosystem),
        )

    def _preferred_hint_matches(self, root: Path, ecosystem: str) -> bool:
        if ecosystem == "es_de":
            return self._path_exists(root / "ES-DE" / "gamelists")
        if ecosystem == "retrobat":
            return self._path_exists(root / "retrobat.ini")
        if ecosystem == "retroarch":
            return self._has_any(root, "*.lpl")
        if ecosystem == "attract_mode":
            return self._path_exists(root / "romlists") and self._path_exists(root / "attract.cfg")
        if ecosystem == "pegasus":
            return self._has_any(root, "metadata.pegasus.txt")
        if ecosystem == "onionos":
            return self._path_exists(root / "Roms")
        if ecosystem == "muos":
            return self._path_exists(root / "MUOS" / "info" / "catalogue")
        if ecosystem == "es_classic":
            return (
                self._path_exists(root / "roms")
                or self._path_exists(root / ".emulationstation")
                or self._has_any(root, "gamelist.xml")
            )
        return False

    def _auto_fast_detect(self, root: Path) -> tuple[str, _ScanFacts] | None:
        if self._path_exists(root / "ES-DE" / "gamelists") and self._path_exists(root / "ES-DE" / "downloaded_media"):
            return "es_de", _ScanFacts(has_es_de_gamelists=True, has_es_de_downloaded_media=True)
        if self._path_exists(root / "MUOS" / "info" / "catalogue"):
            return "muos", _ScanFacts(has_muos_catalogue=True)
        if self._path_exists(root / "romlists") and self._path_exists(root / "attract.cfg"):
            return "attract_mode", _ScanFacts(has_attract_cfg=True, has_romlists_dir=True)
        if self._path_exists(root / "retrobat.ini"):
            return "retrobat", _ScanFacts(has_retrobat_ini=True)
        if self._path_exists(root / "Roms") and self._has_any(root / "Roms", "miyoogamelist.xml"):
            return "onionos", _ScanFacts(has_miyoo_gamelist=True, has_onion_imgs_dir=True)
        if self._has_any(root, "metadata.pegasus.txt"):
            return "pegasus", _ScanFacts(has_pegasus_metadata=True)
        if self._has_any(root, "*.lpl"):
            return "retroarch", _ScanFacts(has_lpl=True)
        return None

    def _score_ecosystems(self, root: Path, facts: _ScanFacts) -> dict[str, float]:
        scores = {ecosystem: 0.0 for ecosystem in ECOSYSTEMS}

        # Avoid duplicate expensive recursive checks here by only evaluating cheap path hints.
        for ecosystem, hints in SIGNATURE_HINTS.items():
            for hint in hints:
                if "/" not in hint:
                    continue
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

    def _enumerate_systems_meta(self, root: Path, ecosystem: str, facts: _ScanFacts) -> list[System]:
        if ecosystem == "launchbox":
            return self._systems_from_launchbox(root)
        if ecosystem == "es_de":
            return self._systems_from_es_de(root)
        if ecosystem == "retroarch":
            return self._systems_from_retroarch_meta(root)
        if ecosystem == "attract_mode":
            return self._systems_from_attract_mode(root)
        if ecosystem == "onionos":
            return self._systems_from_onion_meta(root)
        if ecosystem == "muos":
            return self._systems_from_muos(root)
        if ecosystem == "pegasus":
            return self._systems_from_pegasus_meta(root)
        return self._systems_from_es_family_meta(root, facts)

    def _systems_from_es_family(self, root: Path, facts: _ScanFacts) -> list[System]:
        systems: list[System] = []
        seen_ids: set[str] = set()

        gamelist_files = self._collect_matches(root, "gamelist.xml", max_results=6000)
        if gamelist_files:
            self._emit(self._progress_callback, f"[detect] Found {len(gamelist_files)} gamelist.xml files.")
        for gamelist_path in gamelist_files:
            self._check_cancel()
            system_dir = gamelist_path.parent
            if system_dir.name.lower() in {"gamelists", "metadata"}:
                continue

            system_id = canonicalize_system_id(system_dir.name)
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
            self._check_cancel()
            self._emit(self._progress_callback, f"[detect] Scanning candidate ROM root: {roms_root}")
            for child in sorted(path for path in roms_root.iterdir() if path.is_dir()):
                self._check_cancel()
                if not self._looks_like_system_dir(child):
                    continue
                if child.name.lower() in {"images", "videos", "manuals"}:
                    continue
                system_id = canonicalize_system_id(child.name)
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

    def _systems_from_es_family_meta(self, root: Path, facts: _ScanFacts) -> list[System]:
        systems: list[System] = []
        seen_ids: set[str] = set()
        gamelist_files = self._collect_gamelists_meta(root)
        if gamelist_files:
            self._emit(self._progress_callback, f"[detect] Meta scan found {len(gamelist_files)} gamelist.xml files.")
        for gamelist_path in gamelist_files:
            system_dir = gamelist_path.parent
            if system_dir.name.lower() in {"gamelists", "metadata"}:
                continue
            system_id = canonicalize_system_id(system_dir.name)
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
        return sorted(systems, key=lambda item: item.system_id)

    def _systems_from_es_de(self, root: Path) -> list[System]:
        systems: list[System] = []
        seen_ids: set[str] = set()
        gamelists_root = root / "ES-DE" / "gamelists"
        if gamelists_root.exists():
            self._emit(self._progress_callback, f"[detect] ES-DE gamelist root found: {gamelists_root}")
            for system_dir in sorted(path for path in gamelists_root.iterdir() if path.is_dir()):
                self._check_cancel()
                gamelist_path = system_dir / "gamelist.xml"
                system_id = canonicalize_system_id(system_dir.name)
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
            self._check_cancel()
            self._emit(self._progress_callback, f"[detect] ES-DE fallback ROM scan root: {roms_root}")
            for child in sorted(path for path in roms_root.iterdir() if path.is_dir()):
                self._check_cancel()
                if not self._looks_like_system_dir(child):
                    continue
                system_id = canonicalize_system_id(child.name)
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
        launchbox_root = self._launchbox_root_from_selected(root)
        if launchbox_root is None:
            return systems
        platforms_root = launchbox_root / "Data" / "Platforms"
        if not platforms_root.exists() or not platforms_root.is_dir():
            return systems

        for xml_path in sorted(platforms_root.glob("*.xml")):
            self._check_cancel()
            system_name = xml_path.stem
            systems.append(
                System(
                    system_id=canonicalize_system_id(system_name),
                    display_name=system_name,
                    rom_root=launchbox_root,
                    metadata_source=MetadataSource.LAUNCHBOX_XML,
                    metadata_paths=[xml_path],
                    detected_ecosystem="launchbox",
                )
            )
        return systems

    def _systems_from_retroarch(self, root: Path) -> list[System]:
        systems: list[System] = []
        for lpl_path in self._collect_matches(root, "*.lpl", max_results=3000):
            self._check_cancel()
            system_name = lpl_path.stem
            systems.append(
                System(
                    system_id=canonicalize_system_id(system_name),
                    display_name=system_name,
                    rom_root=lpl_path.parent,
                    metadata_source=MetadataSource.RETROARCH_LPL,
                    metadata_paths=[lpl_path],
                    detected_ecosystem="retroarch",
                )
            )
        return systems

    def _systems_from_retroarch_meta(self, root: Path) -> list[System]:
        systems: list[System] = []
        for lpl_path in self._collect_retroarch_playlists_meta(root):
            system_name = lpl_path.stem
            systems.append(
                System(
                    system_id=canonicalize_system_id(system_name),
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
            self._check_cancel()
            system_name = txt_path.stem
            systems.append(
                System(
                    system_id=canonicalize_system_id(system_name),
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
            self._check_cancel()
            miyoo_path = system_dir / "miyoogamelist.xml"
            systems.append(
                System(
                    system_id=canonicalize_system_id(system_dir.name),
                    display_name=system_dir.name,
                    rom_root=system_dir,
                    metadata_source=MetadataSource.MIYOO_GAMELIST,
                    metadata_paths=[miyoo_path] if miyoo_path.exists() else [],
                    detected_ecosystem="onionos",
                )
            )
        return systems

    def _systems_from_onion_meta(self, root: Path) -> list[System]:
        systems: list[System] = []
        roms_root = root / "Roms"
        if not roms_root.exists():
            return systems

        for system_dir in sorted(path for path in roms_root.iterdir() if path.is_dir()):
            self._check_cancel()
            miyoo_path = system_dir / "miyoogamelist.xml"
            if not miyoo_path.exists():
                continue
            systems.append(
                System(
                    system_id=canonicalize_system_id(system_dir.name),
                    display_name=system_dir.name,
                    rom_root=system_dir,
                    metadata_source=MetadataSource.MIYOO_GAMELIST,
                    metadata_paths=[miyoo_path],
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
            self._check_cancel()
            systems.append(
                System(
                    system_id=canonicalize_system_id(system_dir.name),
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
        for metadata_file in self._collect_matches(root, "metadata.pegasus.txt", max_results=3000):
            self._check_cancel()
            system_dir = metadata_file.parent
            systems.append(
                System(
                    system_id=canonicalize_system_id(system_dir.name),
                    display_name=system_dir.name,
                    rom_root=system_dir,
                    metadata_source=MetadataSource.METADATA_PEGASUS,
                    metadata_paths=[metadata_file],
                    detected_ecosystem="pegasus",
                )
            )
        return systems

    def _systems_from_pegasus_meta(self, root: Path) -> list[System]:
        systems: list[System] = []
        for metadata_file in self._collect_pegasus_metadata_meta(root):
            system_dir = metadata_file.parent
            systems.append(
                System(
                    system_id=canonicalize_system_id(system_dir.name),
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
    def _launchbox_root_from_selected(selected_root: Path) -> Path | None:
        """Resolve selected path to LaunchBox root for root/Data/parent-of-LaunchBox inputs."""
        # Case: user selected parent folder that contains LaunchBox/
        if (selected_root / "LaunchBox" / "Data" / "Platforms").exists():
            return selected_root / "LaunchBox"
        # Case: user selected LaunchBox root directly
        if (selected_root / "Data" / "Platforms").exists():
            return selected_root
        # Case: user selected LaunchBox/Data directly
        if selected_root.name.lower() == "data" and (selected_root / "Platforms").exists():
            return selected_root.parent
        return None

    def _has_any(self, root: Path, pattern: str) -> bool:
        cache_key = (root.resolve().as_posix().lower(), pattern)
        if cache_key in self._has_any_cache:
            return self._has_any_cache[cache_key]
        value = False
        for _ in root.rglob(pattern):
            self._check_cancel()
            value = True
            break
        self._has_any_cache[cache_key] = value
        return value

    def _has_dir_named(self, root: Path, directory_name: str) -> bool:
        cache_key = (root.resolve().as_posix().lower(), directory_name.lower())
        if cache_key in self._has_dir_named_cache:
            return self._has_dir_named_cache[cache_key]
        directory_name = directory_name.lower()
        for path in root.rglob("*"):
            self._check_cancel()
            if path.is_dir() and path.name.lower() == directory_name:
                self._has_dir_named_cache[cache_key] = True
                return True
        self._has_dir_named_cache[cache_key] = False
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
        cache_key = path.resolve().as_posix().lower()
        if cache_key in self._system_dir_scan_cache:
            return self._system_dir_scan_cache[cache_key]
        if (path / "gamelist.xml").exists():
            self._system_dir_scan_cache[cache_key] = True
            return True
        if path.name.lower() in ASSET_DIRECTORY_HINTS:
            self._system_dir_scan_cache[cache_key] = False
            return False
        file_budget = 2500
        scanned = 0
        for file_path in path.rglob("*"):
            self._check_cancel()
            if not file_path.is_file():
                continue
            scanned += 1
            if file_path.suffix.lower() in ROM_EXTENSIONS:
                self._system_dir_scan_cache[cache_key] = True
                return True
            if scanned >= file_budget:
                break
        self._system_dir_scan_cache[cache_key] = False
        return False

    def _collect_matches(self, root: Path, pattern: str, max_results: int) -> list[Path]:
        results: list[Path] = []
        for path in root.rglob(pattern):
            self._check_cancel()
            results.append(path)
            if len(results) >= max_results:
                break
        return sorted(results)

    def _collect_gamelists_meta(self, root: Path) -> list[Path]:
        candidates = [
            root,
            root / "roms",
            root / "Roms",
            root / "ES-DE" / "gamelists",
            root / ".emulationstation" / "gamelists",
        ]
        seen: set[str] = set()
        matches: list[Path] = []
        for candidate in candidates:
            if not candidate.exists() or not candidate.is_dir():
                continue
            direct = candidate / "gamelist.xml"
            if direct.exists():
                key = direct.resolve().as_posix().lower()
                if key not in seen:
                    seen.add(key)
                    matches.append(direct.resolve())
            for child in sorted(path for path in candidate.iterdir() if path.is_dir()):
                self._check_cancel()
                gamelist = child / "gamelist.xml"
                if not gamelist.exists():
                    continue
                key = gamelist.resolve().as_posix().lower()
                if key in seen:
                    continue
                seen.add(key)
                matches.append(gamelist.resolve())
        return sorted(matches)

    def _collect_retroarch_playlists_meta(self, root: Path) -> list[Path]:
        seen: set[str] = set()
        matches: list[Path] = []
        for candidate in (root / "playlists", root):
            if not candidate.exists() or not candidate.is_dir():
                continue
            for lpl_path in sorted(candidate.glob("*.lpl")):
                self._check_cancel()
                key = lpl_path.resolve().as_posix().lower()
                if key in seen:
                    continue
                seen.add(key)
                matches.append(lpl_path.resolve())
        return matches

    def _collect_pegasus_metadata_meta(self, root: Path) -> list[Path]:
        seen: set[str] = set()
        matches: list[Path] = []
        direct = root / "metadata.pegasus.txt"
        if direct.exists():
            key = direct.resolve().as_posix().lower()
            seen.add(key)
            matches.append(direct.resolve())
        if root.exists() and root.is_dir():
            for child in sorted(path for path in root.iterdir() if path.is_dir()):
                self._check_cancel()
                metadata_file = child / "metadata.pegasus.txt"
                if not metadata_file.exists():
                    continue
                key = metadata_file.resolve().as_posix().lower()
                if key in seen:
                    continue
                seen.add(key)
                matches.append(metadata_file.resolve())
        return matches

    @staticmethod
    def _any_glob(root: Path, pattern: str) -> bool:
        if not root.exists() or not root.is_dir():
            return False
        for _ in root.glob(pattern):
            return True
        return False

    def _check_cancel(self) -> None:
        if self._cancel_requested is not None and self._cancel_requested():
            raise DetectionCancelled("Analysis cancelled by user.")
