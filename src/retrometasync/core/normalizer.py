from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from retrometasync.core.detection import DetectionResult
from retrometasync.core.loaders import ESGamelistLoader, LaunchBoxXmlLoader, LoaderInput, LoaderResult
from retrometasync.core.models import Library
from retrometasync.core.preloaded_metadata import enrich_library_with_preloaded_metadata


@dataclass(slots=True)
class NormalizationResult:
    library: Library
    warnings: list[str] = field(default_factory=list)


class LibraryNormalizer:
    """Builds a normalized in-memory library model from detection output."""

    def normalize(
        self,
        detection_result: DetectionResult,
        progress_callback: Callable[[str], None] | None = None,
        scan_mode: str | None = None,
        preloaded_metadata_root: Path | None = None,
        compute_missing_hashes: bool = False,
    ) -> NormalizationResult:
        loader = self._select_loader(detection_result.detected_ecosystem)
        if loader is None:
            library = detection_result.to_library()
            return NormalizationResult(
                library=library,
                warnings=[f"No loader available yet for ecosystem '{detection_result.detected_ecosystem}'."],
            )

        effective_scan_mode = (scan_mode or detection_result.scan_mode or "deep").strip().lower()
        if effective_scan_mode in {"launchbox", "single_rom_folder"}:
            effective_scan_mode = "deep"
        compute_hashes_for_metadata = compute_missing_hashes and effective_scan_mode != "meta"

        load_result = loader.load(
            LoaderInput(
                source_root=detection_result.source_root,
                systems=detection_result.systems,
                progress_callback=progress_callback,
                scan_mode=effective_scan_mode,
            )
        )
        library = self._to_library(detection_result, load_result)
        metadata_result = enrich_library_with_preloaded_metadata(
            library=library,
            source_root=detection_result.source_root,
            metadata_root=preloaded_metadata_root,
            compute_missing_hashes=compute_hashes_for_metadata,
            progress_callback=progress_callback,
        )
        if progress_callback is not None and compute_missing_hashes and not compute_hashes_for_metadata:
            progress_callback("[metadata] Meta scan: deferred checksum fallback hashing until conversion-time checks.")
        warnings = list(load_result.warnings)
        if metadata_result.warnings:
            warnings.extend(metadata_result.warnings)
        if progress_callback is not None and metadata_result.enriched_games > 0:
            progress_callback(f"[metadata] Enriched {metadata_result.enriched_games} games from preloaded DAT metadata.")
        return NormalizationResult(library=library, warnings=warnings)

    @staticmethod
    def _select_loader(ecosystem: str):
        if ecosystem in {
            "es_classic",
            "batocera",
            "knulli",
            "amberelec",
            "jelos_rocknix",
            "arkos",
            "retrobat",
            "es_de",
            "emudeck",
            "retrodeck",
        }:
            return ESGamelistLoader()
        if ecosystem == "launchbox":
            return LaunchBoxXmlLoader()
        return None

    @staticmethod
    def _to_library(detection_result: DetectionResult, load_result: LoaderResult) -> Library:
        systems_map = {system.system_id: system for system in load_result.systems}
        return Library(
            source_root=detection_result.source_root,
            systems=systems_map,
            games_by_system=load_result.games_by_system,
            detected_ecosystem=detection_result.detected_ecosystem,
            confidence=detection_result.confidence,
        )

