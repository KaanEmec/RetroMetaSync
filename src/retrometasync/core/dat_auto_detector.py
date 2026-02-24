from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from retrometasync.config.ecosystems import PRELOADED_METADATA_PROFILE_BY_SYSTEM, PRELOADED_METADATA_SOURCE_CATALOG
from retrometasync.config.system_aliases import canonicalize_system_id, expand_search_tokens
from retrometasync.core.models import Game
from retrometasync.core.preloaded_metadata import _metadata_search_roots, parse_clrmamepro_dat

_MAX_CANDIDATES = 5000
_HEADER_BYTES = 8192
_DEFAULT_SCORE_THRESHOLD = 45
_VERIFY_SAMPLE_LIMIT = 12
_IGNORED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "node_modules",
    "mamedev-mame",
}


@dataclass(frozen=True, slots=True)
class DatDetectionMatch:
    system_id: str
    dat_path: Path
    confidence: int
    reason: str


@dataclass(slots=True)
class DatDetectionResult:
    matches: dict[str, DatDetectionMatch] = field(default_factory=dict)
    unresolved_systems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class _DatCandidate:
    path: Path
    filename_normalized: str
    header_text: str


class DatAutoDetector:
    def detect_for_systems(
        self,
        *,
        source_root: Path,
        target_system_ids: list[str],
        metadata_root: Path | None = None,
        strict_verify: bool = False,
        games_by_system: dict[str, list[Game]] | None = None,
        progress_callback=None,
    ) -> DatDetectionResult:
        result = DatDetectionResult()
        normalized_targets = sorted({canonicalize_system_id(system_id) for system_id in target_system_ids if system_id.strip()})
        candidates = self._collect_candidates(
            source_root=source_root,
            metadata_root=metadata_root,
            warnings=result.warnings,
            target_system_ids=normalized_targets,
        )
        if not candidates:
            result.unresolved_systems = normalized_targets
            return result

        for system_id in normalized_targets:
            ranked = self._rank_candidates_for_system(system_id=system_id, candidates=candidates)
            if not ranked:
                result.unresolved_systems.append(system_id)
                result.warnings.append(f"[metadata] {system_id}: no DAT candidates scored above zero.")
                continue
            best_match = ranked[0]
            if best_match.confidence < _DEFAULT_SCORE_THRESHOLD:
                near_miss_text = ", ".join(
                    f"{match.dat_path.name} ({match.confidence})" for match in ranked[:3]
                )
                result.warnings.append(f"[metadata] {system_id}: near matches {near_miss_text}")
                result.unresolved_systems.append(system_id)
                continue

            match = best_match
            if strict_verify:
                verified = self._verify_match(
                    system_id=system_id,
                    candidate=best_match,
                    games=(games_by_system or {}).get(system_id, ()),
                )
                if verified is None:
                    result.unresolved_systems.append(system_id)
                    continue
                match = verified
            result.matches[system_id] = match
            if progress_callback is not None:
                progress_callback(
                    f"[metadata] {system_id}: detected DAT '{match.dat_path.name}' (confidence {match.confidence})"
                )

        unresolved = sorted(set(result.unresolved_systems) - set(result.matches))
        result.unresolved_systems = unresolved
        return result

    def _collect_candidates(
        self,
        *,
        source_root: Path,
        metadata_root: Path | None,
        warnings: list[str],
        target_system_ids: list[str],
    ) -> list[_DatCandidate]:
        candidates: list[_DatCandidate] = []
        seen: set[str] = set()
        preferred_names = self._preferred_catalog_filenames(target_system_ids)
        for root in _metadata_search_roots(source_root, metadata_root):
            if not root.exists() or not root.is_dir():
                continue
            root_preferred: list[Path] = []
            root_other: list[Path] = []
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [name for name in dirnames if name.lower() not in _IGNORED_DIR_NAMES]
                for filename in filenames:
                    name_lower = filename.lower()
                    if not (name_lower.endswith(".dat") or name_lower.endswith(".xml")):
                        continue
                    path = Path(dirpath) / filename
                    key = path.resolve().as_posix().lower()
                    if key in seen or not path.is_file():
                        continue
                    seen.add(key)
                    if name_lower in preferred_names:
                        root_preferred.append(path)
                    else:
                        root_other.append(path)
                    if len(seen) >= _MAX_CANDIDATES:
                        warnings.append(f"DAT candidate scan capped at {_MAX_CANDIDATES} files.")
                        break
                if len(seen) >= _MAX_CANDIDATES:
                    break
            ordered_paths = sorted(root_preferred, key=lambda item: len(item.parts)) + sorted(
                root_other, key=lambda item: len(item.parts)
            )
            for path in ordered_paths:
                candidates.append(
                    _DatCandidate(
                        path=path,
                        filename_normalized=path.name.lower().replace("-", " ").replace("_", " "),
                        header_text=self._read_header(path, warnings),
                    )
                )
            if len(seen) >= _MAX_CANDIDATES:
                break
        return candidates

    @staticmethod
    def _preferred_catalog_filenames(target_system_ids: list[str]) -> set[str]:
        preferred: set[str] = set()
        for system_id in target_system_ids:
            for source_key in PRELOADED_METADATA_PROFILE_BY_SYSTEM.get(system_id, ()):
                for filename in PRELOADED_METADATA_SOURCE_CATALOG.get(source_key, ()):
                    preferred.add(filename.lower())
        return preferred

    @staticmethod
    def _read_header(path: Path, warnings: list[str]) -> str:
        try:
            chunk = path.read_text(encoding="utf-8", errors="ignore")[:_HEADER_BYTES]
        except OSError as exc:
            warnings.append(f"Failed to read DAT candidate header '{path}': {exc}")
            return ""
        chunk_lower = chunk.lower()
        if "<header>" in chunk_lower:
            return chunk_lower
        if "clrmamepro" in chunk_lower or 'name "' in chunk_lower:
            return chunk_lower
        return chunk_lower

    def _rank_candidates_for_system(self, *, system_id: str, candidates: list[_DatCandidate]) -> list[DatDetectionMatch]:
        canonical_system_id = canonicalize_system_id(system_id)
        profile_source_keys = PRELOADED_METADATA_PROFILE_BY_SYSTEM.get(canonical_system_id, ())
        profile_filenames = {
            candidate.lower()
            for source_key in profile_source_keys
            for candidate in PRELOADED_METADATA_SOURCE_CATALOG.get(source_key, ())
        }
        ranked: list[DatDetectionMatch] = []
        for candidate in candidates:
            score, reasons = self._score_candidate(
                system_id=canonical_system_id,
                candidate=candidate,
                profile_filenames=profile_filenames,
            )
            if score <= 0:
                continue
            reason = "+".join(reasons)
            match = DatDetectionMatch(
                system_id=canonical_system_id,
                dat_path=candidate.path,
                confidence=min(100, score),
                reason=reason,
            )
            ranked.append(match)
        ranked.sort(key=lambda item: item.confidence, reverse=True)
        return ranked

    @classmethod
    def _score_candidate(
        cls,
        *,
        system_id: str,
        candidate: _DatCandidate,
        profile_filenames: set[str],
    ) -> tuple[int, list[str]]:
        score = 0
        reasons: list[str] = []
        if candidate.path.name.lower() in profile_filenames:
            score += 70
            reasons.append("catalog")

        keywords = expand_search_tokens(system_id)
        haystack_name = candidate.filename_normalized
        haystack_header = candidate.header_text
        for token in keywords:
            escaped = re.escape(token.lower())
            if re.search(rf"\b{escaped}\b", haystack_name):
                score += 30
            elif token.lower() in haystack_name:
                score += 18
            if re.search(rf"\b{escaped}\b", haystack_header):
                score += 15
            elif token.lower() in haystack_header:
                score += 10
        if score > 0:
            reasons.append("name/header")

        overlap_bonus = cls._fuzzy_overlap_bonus(system_id=system_id, candidate=candidate)
        if overlap_bonus > 0:
            score += overlap_bonus
            reasons.append("fuzzy")
        return score, reasons

    @staticmethod
    def _fuzzy_overlap_bonus(*, system_id: str, candidate: _DatCandidate) -> int:
        system_tokens = {token for token in _tokenize(" ".join(expand_search_tokens(system_id))) if len(token) >= 2}
        if not system_tokens:
            return 0
        candidate_tokens = _tokenize(candidate.filename_normalized + " " + candidate.header_text)
        overlap = system_tokens.intersection(candidate_tokens)
        if not overlap:
            return 0
        ratio = len(overlap) / max(1, len(system_tokens))
        return int(22 * ratio)

    def _verify_match(
        self,
        *,
        system_id: str,
        candidate: DatDetectionMatch,
        games: list[Game],
    ) -> DatDetectionMatch | None:
        if not games:
            return candidate
        sample_set_names = {game.rom_basename.strip().lower() for game in games[:_VERIFY_SAMPLE_LIMIT] if game.rom_basename}
        if not sample_set_names:
            return candidate
        try:
            index = parse_clrmamepro_dat(candidate.dat_path)
        except (ET.ParseError, OSError, ValueError):
            return None
        hits = sum(1 for set_name in sample_set_names if set_name in index.by_set_name)
        ratio = hits / max(1, len(sample_set_names))
        if ratio <= 0:
            return None
        confidence = min(100, candidate.confidence + int(35 * ratio))
        return DatDetectionMatch(
            system_id=system_id,
            dat_path=candidate.dat_path,
            confidence=confidence,
            reason=f"{candidate.reason}+verify({hits}/{len(sample_set_names)})",
        )


def _tokenize(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.lower()) if token}
