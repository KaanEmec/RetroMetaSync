from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from retrometasync.core.models import Game, System

ProgressCallback = Callable[[str], None]


@dataclass(slots=True)
class LoaderInput:
    source_root: Path
    systems: list[System] = field(default_factory=list)
    progress_callback: ProgressCallback | None = None
    # Supported modes: "meta", "deep", "force".
    scan_mode: str = "deep"
    max_asset_index_files: int = 40000


@dataclass(slots=True)
class LoaderResult:
    systems: list[System] = field(default_factory=list)
    games_by_system: dict[str, list[Game]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class BaseLoader(ABC):
    ecosystem: str = "unknown"

    @abstractmethod
    def load(self, load_input: LoaderInput) -> LoaderResult:
        """Load metadata and games from a source root."""

