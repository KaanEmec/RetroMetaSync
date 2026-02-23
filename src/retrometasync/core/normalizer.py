from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from retrometasync.core.detection import DetectionResult
from retrometasync.core.loaders import ESGamelistLoader, LaunchBoxXmlLoader, LoaderInput, LoaderResult
from retrometasync.core.models import Library


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
    ) -> NormalizationResult:
        loader = self._select_loader(detection_result.detected_ecosystem)
        if loader is None:
            library = detection_result.to_library()
            return NormalizationResult(
                library=library,
                warnings=[f"No loader available yet for ecosystem '{detection_result.detected_ecosystem}'."],
            )

        load_result = loader.load(
            LoaderInput(
                source_root=detection_result.source_root,
                systems=detection_result.systems,
                progress_callback=progress_callback,
                scan_mode="quick",
            )
        )
        library = self._to_library(detection_result, load_result)
        return NormalizationResult(library=library, warnings=load_result.warnings)

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

