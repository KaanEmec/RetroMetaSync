from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import shutil
from typing import Callable

from retrometasync.core.conversion.targets import TARGET_MODULES
from retrometasync.core.conversion.writers.dat_writer import write_dat
from retrometasync.core.conversion.writers.gamelist_xml import write_gamelist
from retrometasync.core.conversion.writers.launchbox_xml import write_launchbox_platform_xml
from retrometasync.core.models import AssetType, Game, Library

ProgressCallback = Callable[[str], None]

IMAGE_TYPES: tuple[AssetType, ...] = (
    AssetType.BOX_FRONT,
    AssetType.BOX_BACK,
    AssetType.BOX_SPINE,
    AssetType.DISC,
    AssetType.SCREENSHOT_GAMEPLAY,
    AssetType.SCREENSHOT_TITLE,
    AssetType.SCREENSHOT_MENU,
    AssetType.MIXIMAGE,
)
MARQUEE_TYPES: tuple[AssetType, ...] = (AssetType.MARQUEE, AssetType.WHEEL, AssetType.LOGO)
FANART_TYPES: tuple[AssetType, ...] = (AssetType.FANART, AssetType.BACKGROUND, AssetType.BEZEL)


@dataclass(slots=True)
class ConversionRequest:
    """Input bundle for one conversion run.

    `dry_run` performs planning/validation without writing files.
    `overwrite_existing` controls whether existing output files are replaced.
    """

    library: Library
    selected_games: dict[str, list[Game]]
    target_ecosystem: str
    output_root: Path
    copy_roms: bool = True
    export_dat: bool = False
    dry_run: bool = False
    overwrite_existing: bool = False


@dataclass(slots=True)
class ConversionResult:
    target_ecosystem: str
    output_root: Path
    systems_processed: int = 0
    games_processed: int = 0
    roms_copied: int = 0
    assets_copied: int = 0
    files_skipped: int = 0
    files_renamed_due_to_collision: int = 0
    preflight_checks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ConversionEngine:
    """Target-agnostic conversion orchestrator.

    The engine delegates path conventions to target planners, then performs
    copy/write operations with validation and progress logging.
    """

    def convert(self, request: ConversionRequest, progress: ProgressCallback | None = None) -> ConversionResult:
        if request.target_ecosystem not in TARGET_MODULES:
            raise ValueError(f"Unsupported target ecosystem: {request.target_ecosystem}")

        planner = TARGET_MODULES[request.target_ecosystem]
        output_root = request.output_root.expanduser().resolve()
        if not request.dry_run:
            output_root.mkdir(parents=True, exist_ok=True)

        result = ConversionResult(target_ecosystem=request.target_ecosystem, output_root=output_root)
        gamelist_payload: dict[Path, list[dict[str, str]]] = {}
        launchbox_payload: dict[Path, list[dict[str, str]]] = {}
        dat_payload: dict[str, list[dict[str, object]]] = {}

        total_games = sum(len(games) for games in request.selected_games.values())
        self._log(
            progress,
            (
                f"Starting conversion to '{request.target_ecosystem}' with {total_games} selected games."
                f" dry_run={request.dry_run}, overwrite_existing={request.overwrite_existing}"
            ),
        )
        if total_games == 0:
            result.warnings.append("No games selected for conversion.")
            self._log(progress, "No selected games found; skipping conversion.")
            return result

        preflight = _run_preflight_checks(request)
        result.preflight_checks = preflight["checks"]
        result.warnings.extend(preflight["warnings"])
        self._log(progress, "Validation checklist:")
        for check_line in result.preflight_checks:
            self._log(progress, f"  - {check_line}")
        for warning in preflight["warnings"]:
            self._log(progress, f"[warn] {warning}")

        for system_id, games in request.selected_games.items():
            if not games:
                continue

            result.systems_processed += 1
            system_display = request.library.systems.get(system_id).display_name if system_id in request.library.systems else system_id
            self._log(progress, f"Processing system '{system_id}' ({len(games)} games).")

            for game in games:
                result.games_processed += 1
                try:
                    stem = _safe_stem(game.rom_basename)
                    rom_name = _safe_filename(game.rom_filename)
                    planned_paths = planner.plan_paths(output_root, system_id, system_display, rom_name, stem)

                    # Resolve destination up front to avoid silent overwrites.
                    if request.copy_roms:
                        resolved_rom = _resolve_destination_path(
                            planned_paths["rom"],
                            overwrite_existing=request.overwrite_existing,
                            allow_auto_rename=True,
                        )
                        if resolved_rom is None:
                            result.files_skipped += 1
                            warning = f"ROM destination exists and overwrite disabled: {planned_paths['rom']}"
                            result.warnings.append(warning)
                            self._log(progress, f"[warn] {warning}")
                        elif game.rom_path.exists():
                            if resolved_rom != planned_paths["rom"]:
                                result.files_renamed_due_to_collision += 1
                                self._log(progress, f"[warn] ROM collision resolved as: {resolved_rom.name}")
                            if len(str(resolved_rom)) > 240:
                                result.warnings.append(f"Long path risk on Windows: {resolved_rom}")
                            if request.dry_run:
                                self._log(progress, f"[dry-run] Would copy ROM -> {resolved_rom}")
                            else:
                                _copy_file(game.rom_path, resolved_rom)
                            planned_paths["rom"] = resolved_rom
                            result.roms_copied += 1
                        else:
                            warning = f"ROM file missing, skipped: {game.rom_path}"
                            result.warnings.append(warning)
                            self._log(progress, f"[warn] {warning}")
                    else:
                        self._log(progress, f"[warn] ROM copy disabled for: {game.rom_path.name}")

                    chosen_assets = _pick_assets(game)
                    copied_asset_targets = self._copy_assets(
                        chosen_assets=chosen_assets,
                        planned_paths=planned_paths,
                        result=result,
                        progress=progress,
                        dry_run=request.dry_run,
                        overwrite_existing=request.overwrite_existing,
                    )

                    if "gamelist" in planned_paths:
                        entry = _build_gamelist_entry(game, planned_paths, copied_asset_targets)
                        gamelist_payload.setdefault(planned_paths["gamelist"], []).append(entry)

                    if "platform_xml" in planned_paths:
                        entry = _build_launchbox_entry(
                            game,
                            output_root,
                            planned_paths,
                            copied_asset_targets,
                            platform_name=system_display,
                        )
                        launchbox_payload.setdefault(planned_paths["platform_xml"], []).append(entry)

                    if request.export_dat:
                        rom_for_dat = planned_paths["rom"] if request.copy_roms else game.rom_path
                        dat_payload.setdefault(system_id, []).append(
                            {
                                "machine_name": game.rom_basename,
                                "rom_path": rom_for_dat,
                            }
                        )
                except Exception as exc:  # noqa: BLE001
                    warning = f"Game conversion failed for '{game.rom_path}': {exc}"
                    result.warnings.append(warning)
                    self._log(progress, f"[warn] {warning}")

        for gamelist_path, entries in gamelist_payload.items():
            if request.dry_run:
                self._log(progress, f"[dry-run] Would write gamelist: {gamelist_path} ({len(entries)} entries)")
            else:
                write_gamelist(gamelist_path, entries)
                self._log(progress, f"Wrote gamelist: {gamelist_path}")

        for platform_xml_path, entries in launchbox_payload.items():
            if request.dry_run:
                self._log(progress, f"[dry-run] Would write LaunchBox XML: {platform_xml_path} ({len(entries)} entries)")
            else:
                write_launchbox_platform_xml(platform_xml_path, entries)
                self._log(progress, f"Wrote LaunchBox XML: {platform_xml_path}")

        if request.export_dat:
            for system_id, entries in dat_payload.items():
                dat_path = output_root / "dats" / f"{system_id}.dat"
                if request.dry_run:
                    self._log(progress, f"[dry-run] Would write DAT: {dat_path} ({len(entries)} entries)")
                else:
                    write_dat(dat_path, dat_name=f"{system_id}_export", games=entries)
                    self._log(progress, f"Wrote DAT: {dat_path}")

        self._log(
            progress,
            (
                "Conversion complete."
                f" systems={result.systems_processed}, games={result.games_processed},"
                f" roms={result.roms_copied}, assets={result.assets_copied},"
                f" skipped={result.files_skipped}, renamed={result.files_renamed_due_to_collision}"
            ),
        )
        return result

    def _copy_assets(
        self,
        chosen_assets: dict[str, Path],
        planned_paths: dict[str, Path],
        result: ConversionResult,
        progress: ProgressCallback | None,
        dry_run: bool,
        overwrite_existing: bool,
    ) -> dict[str, Path]:
        copied: dict[str, Path] = {}
        for key, source in chosen_assets.items():
            if key not in planned_paths:
                continue
            if not source.exists():
                warning = f"Asset source missing [{key}]: {source}"
                result.warnings.append(warning)
                self._log(progress, f"[warn] {warning}")
                continue

            destination_base = planned_paths[key]
            candidate_destination = destination_base.with_suffix(source.suffix.lower())
            destination = _resolve_destination_path(
                candidate_destination,
                overwrite_existing=overwrite_existing,
                allow_auto_rename=True,
            )
            if destination is None:
                result.files_skipped += 1
                warning = f"Asset destination exists and overwrite disabled [{key}]: {candidate_destination}"
                result.warnings.append(warning)
                self._log(progress, f"[warn] {warning}")
                continue

            if destination != candidate_destination:
                result.files_renamed_due_to_collision += 1
                self._log(progress, f"[warn] Asset collision resolved for [{key}]: {destination.name}")
            if len(str(destination)) > 240:
                result.warnings.append(f"Long path risk on Windows: {destination}")

            if dry_run:
                self._log(progress, f"[dry-run] Would copy asset [{key}] -> {destination}")
            else:
                _copy_file(source, destination)
            copied[key] = destination
            result.assets_copied += 1
            if not dry_run:
                self._log(progress, f"Copied asset [{key}] -> {destination}")
        return copied

    @staticmethod
    def _log(progress: ProgressCallback | None, message: str) -> None:
        if progress is not None:
            progress(message)


def _build_gamelist_entry(
    game: Game,
    planned_paths: dict[str, Path],
    copied_assets: dict[str, Path],
) -> dict[str, str]:
    # ES-family gamelists use relative paths to keep the output portable.
    entry: dict[str, str] = {
        "path": _relative_for_es(planned_paths["rom"], planned_paths["gamelist"].parent),
        "name": game.title,
    }
    if game.sort_title:
        entry["sortname"] = game.sort_title
    if game.description:
        entry["desc"] = game.description
    if game.developer:
        entry["developer"] = game.developer
    if game.publisher:
        entry["publisher"] = game.publisher
    if game.genres:
        entry["genre"] = ", ".join(game.genres)
    if game.languages:
        entry["lang"] = ", ".join(game.languages)
    if game.regions:
        entry["region"] = ", ".join(game.regions)
    if game.players:
        entry["players"] = game.players
    entry["favorite"] = "true" if game.favorite else "false"
    entry["hidden"] = "true" if game.hidden else "false"
    if game.playcount is not None:
        entry["playcount"] = str(game.playcount)
    if game.last_played:
        entry["lastplayed"] = game.last_played.strftime("%Y%m%dT%H%M%S")
    if game.rating is not None:
        entry["rating"] = f"{game.rating:.2f}"
    if game.release_date:
        entry["releasedate"] = game.release_date.strftime("%Y%m%dT000000")

    if "image" in copied_assets:
        entry["image"] = _relative_for_es(copied_assets["image"], planned_paths["gamelist"].parent)
    if "thumbnail" in copied_assets:
        entry["thumbnail"] = _relative_for_es(copied_assets["thumbnail"], planned_paths["gamelist"].parent)
    if "marquee" in copied_assets:
        entry["marquee"] = _relative_for_es(copied_assets["marquee"], planned_paths["gamelist"].parent)
    if "video" in copied_assets:
        entry["video"] = _relative_for_es(copied_assets["video"], planned_paths["gamelist"].parent)
    if "manual" in copied_assets:
        entry["manual"] = _relative_for_es(copied_assets["manual"], planned_paths["gamelist"].parent)
    if "fanart" in copied_assets:
        entry["fanart"] = _relative_for_es(copied_assets["fanart"], planned_paths["gamelist"].parent)
    return entry


def _build_launchbox_entry(
    game: Game,
    output_root: Path,
    planned_paths: dict[str, Path],
    copied_assets: dict[str, Path],
    platform_name: str,
) -> dict[str, str]:
    entry: dict[str, str] = {
        "title": game.title,
        "application_path": _relative_or_absolute(planned_paths["rom"], output_root),
        "platform": platform_name,
    }
    if game.sort_title:
        entry["sort_title"] = game.sort_title
    entry["favorite"] = "true" if game.favorite else "false"
    if game.playcount is not None:
        entry["play_count"] = str(game.playcount)
    if game.last_played:
        entry["last_played_date"] = game.last_played.strftime("%Y-%m-%dT%H:%M:%S")
    if game.rating is not None:
        entry["community_star_rating"] = f"{game.rating:.2f}"
        entry["star_rating"] = f"{game.rating:.2f}"
    if "manual" in copied_assets:
        entry["manual_path"] = _relative_or_absolute(copied_assets["manual"], output_root)
    if "image" in copied_assets:
        entry["front_image_path"] = _relative_or_absolute(copied_assets["image"], output_root)
    if "thumbnail" in copied_assets:
        entry["screenshot_image_path"] = _relative_or_absolute(copied_assets["thumbnail"], output_root)
    if "fanart" in copied_assets:
        entry["background_image_path"] = _relative_or_absolute(copied_assets["fanart"], output_root)
    if "marquee" in copied_assets:
        entry["logo_image_path"] = _relative_or_absolute(copied_assets["marquee"], output_root)
    if "video" in copied_assets:
        entry["video_path"] = _relative_or_absolute(copied_assets["video"], output_root)
    if game.developer:
        entry["developer"] = game.developer
    if game.publisher:
        entry["publisher"] = game.publisher
    if game.genres:
        entry["genre"] = ", ".join(game.genres)
    if game.languages:
        entry["language"] = ", ".join(game.languages)
    if game.regions:
        entry["region"] = ", ".join(game.regions)
    if game.description:
        entry["notes"] = game.description
    if game.release_date:
        entry["release_date"] = game.release_date.strftime("%Y-%m-%d")
    return entry


def _pick_assets(game: Game) -> dict[str, Path]:
    """Select one representative source file per output slot.

    Priority is deterministic: first matching asset in the original list wins.
    """
    chosen: dict[str, Path] = {}

    for asset in game.assets:
        if "image" not in chosen and asset.asset_type in IMAGE_TYPES:
            chosen["image"] = asset.file_path
        if "thumbnail" not in chosen and asset.asset_type in (AssetType.SCREENSHOT_GAMEPLAY, AssetType.SCREENSHOT_TITLE):
            chosen["thumbnail"] = asset.file_path
        if "marquee" not in chosen and asset.asset_type in MARQUEE_TYPES:
            chosen["marquee"] = asset.file_path
        if "video" not in chosen and asset.asset_type == AssetType.VIDEO:
            chosen["video"] = asset.file_path
        if "manual" not in chosen and asset.asset_type == AssetType.MANUAL:
            chosen["manual"] = asset.file_path
        if "bezel" not in chosen and asset.asset_type == AssetType.BEZEL:
            chosen["bezel"] = asset.file_path
        if "fanart" not in chosen and asset.asset_type in FANART_TYPES:
            chosen["fanart"] = asset.file_path

    return chosen


def _copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _safe_filename(value: str) -> str:
    # Normalize invalid Windows filename characters and edge cases.
    disallowed = '<>:"/\\|?*'
    sanitized = "".join("_" if char in disallowed else char for char in value).strip().rstrip(".")
    if sanitized.upper() in {"CON", "PRN", "AUX", "NUL", "COM1", "LPT1"}:
        sanitized = f"{sanitized}_file"
    return sanitized or "untitled"


def _safe_stem(value: str) -> str:
    return _safe_filename(value)


def _relative_for_es(target_path: Path, base_dir: Path) -> str:
    try:
        relative = target_path.relative_to(base_dir).as_posix()
    except ValueError:
        # Cross-drive paths on Windows cannot always be relativized.
        return target_path.as_posix()
    if relative.startswith("./"):
        return relative
    return f"./{relative}"


def _run_preflight_checks(request: ConversionRequest) -> dict[str, list[str]]:
    checks: list[str] = []
    warnings: list[str] = []

    selected_games = [game for games in request.selected_games.values() for game in games]
    selected_count = len(selected_games)
    checks.append(f"Selected games count: {selected_count}")

    duplicate_paths = _count_duplicates([game.rom_path.resolve().as_posix() for game in selected_games])
    if duplicate_paths:
        warnings.append(f"Duplicate ROM selection paths detected: {len(duplicate_paths)}")
        checks.append("ROM uniqueness: FAIL")
    else:
        checks.append("ROM uniqueness: PASS")

    missing_roms = [game for game in selected_games if not game.rom_path.exists()]
    if missing_roms:
        warnings.append(f"Missing ROM files in selection: {len(missing_roms)}")
        checks.append("ROM path existence: PARTIAL")
    else:
        checks.append("ROM path existence: PASS")

    unknown_systems = [system_id for system_id in request.selected_games if system_id not in request.library.systems]
    if unknown_systems:
        warnings.append(f"Selected systems not present in library model: {', '.join(sorted(unknown_systems))}")
        checks.append("System membership: PARTIAL")
    else:
        checks.append("System membership: PASS")

    output_root = request.output_root.expanduser().resolve()
    source_root = request.library.source_root.expanduser().resolve()
    if _is_subpath(output_root, source_root):
        warnings.append("Output folder is inside source library; this may cause duplicate scans.")
        checks.append("Output/source separation: WARN")
    elif _is_subpath(source_root, output_root):
        warnings.append("Source folder is inside output root; conversion may recursively include generated files.")
        checks.append("Output/source separation: WARN")
    else:
        checks.append("Output/source separation: PASS")

    checks.append(f"Dry-run mode: {'ENABLED' if request.dry_run else 'DISABLED'}")
    checks.append(f"Overwrite existing files: {'YES' if request.overwrite_existing else 'NO'}")
    checks.append(f"DAT export: {'ENABLED' if request.export_dat else 'DISABLED'}")

    return {"checks": checks, "warnings": warnings}


def _count_duplicates(values: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return [value for value, count in counts.items() if count > 1]


def _is_subpath(path: Path, possible_parent: Path) -> bool:
    try:
        path.relative_to(possible_parent)
        return True
    except ValueError:
        return False


def _resolve_destination_path(
    destination: Path,
    overwrite_existing: bool,
    allow_auto_rename: bool,
) -> Path | None:
    """Return a safe destination path for copy operations."""
    if not destination.exists() or overwrite_existing:
        return destination
    if not allow_auto_rename:
        return None
    return _with_collision_suffix(destination)


def _with_collision_suffix(path: Path) -> Path:
    """Create a non-conflicting filename by adding _2, _3, ... suffixes."""
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    index = 2
    candidate = path
    while candidate.exists():
        candidate = parent / f"{stem}_{index}{suffix}"
        index += 1
    return candidate


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()
