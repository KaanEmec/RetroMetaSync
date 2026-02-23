from __future__ import annotations

from dataclasses import dataclass, field
from glob import escape as glob_escape
import os
from pathlib import Path
import shutil
from typing import Callable

from retrometasync.config.ecosystems import ECOSYSTEM_MEDIA_FALLBACK_FOLDERS
from retrometasync.core.conversion.targets import TARGET_MODULES
from retrometasync.core.conversion.writers.dat_writer import write_dat
from retrometasync.core.conversion.writers.gamelist_xml import read_gamelist, write_gamelist
from retrometasync.core.conversion.writers.launchbox_xml import read_launchbox_platform_xml, write_launchbox_platform_xml
from retrometasync.core.models import Asset, AssetType, AssetVerificationState, Game, Library

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
    merge_existing_metadata: bool = True


@dataclass(slots=True)
class ConversionResult:
    target_ecosystem: str
    output_root: Path
    systems_processed: int = 0
    games_processed: int = 0
    roms_copied: int = 0
    assets_copied: int = 0
    assets_missing_skipped: int = 0
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
                f" dry_run={request.dry_run}, overwrite_existing={request.overwrite_existing},"
                f" merge_existing_metadata={request.merge_existing_metadata}"
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
                        library=request.library,
                        game=game,
                        system_display=system_display,
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
            entries_to_write = entries
            if request.merge_existing_metadata and gamelist_path.exists():
                try:
                    existing = read_gamelist(gamelist_path)
                    entries_to_write = _merge_gamelist_entries(existing, entries)
                except Exception as exc:  # noqa: BLE001
                    warning = f"Failed to merge existing gamelist '{gamelist_path}': {exc}"
                    result.warnings.append(warning)
                    self._log(progress, f"[warn] {warning}")
            if request.dry_run:
                self._log(progress, f"[dry-run] Would write gamelist: {gamelist_path} ({len(entries_to_write)} entries)")
            else:
                write_gamelist(gamelist_path, entries_to_write)
                self._log(progress, f"Wrote gamelist: {gamelist_path}")

        for platform_xml_path, entries in launchbox_payload.items():
            entries_to_write = entries
            if request.merge_existing_metadata and platform_xml_path.exists():
                try:
                    existing = read_launchbox_platform_xml(platform_xml_path)
                    entries_to_write = _merge_launchbox_entries(existing, entries)
                except Exception as exc:  # noqa: BLE001
                    warning = f"Failed to merge existing LaunchBox XML '{platform_xml_path}': {exc}"
                    result.warnings.append(warning)
                    self._log(progress, f"[warn] {warning}")
            if request.dry_run:
                self._log(
                    progress,
                    f"[dry-run] Would write LaunchBox XML: {platform_xml_path} ({len(entries_to_write)} entries)",
                )
            else:
                write_launchbox_platform_xml(platform_xml_path, entries_to_write)
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
                f" assets_missing={result.assets_missing_skipped},"
                f" skipped={result.files_skipped}, renamed={result.files_renamed_due_to_collision}"
            ),
        )
        return result

    def _copy_assets(
        self,
        chosen_assets: dict[str, Asset],
        planned_paths: dict[str, Path],
        result: ConversionResult,
        library: Library,
        game: Game,
        system_display: str,
        progress: ProgressCallback | None,
        dry_run: bool,
        overwrite_existing: bool,
    ) -> dict[str, Path]:
        copied: dict[str, Path] = {}
        candidate_keys = set(chosen_assets.keys())
        candidate_keys.update(_candidate_asset_keys_for_ecosystem(library.detected_ecosystem or ""))

        for key in candidate_keys:
            if key not in planned_paths:
                continue
            asset = chosen_assets.get(key)
            source = asset.file_path if asset is not None else None
            if source is None or not source.exists():
                fallback_source = _lookup_asset_fallback(
                    key=key,
                    library=library,
                    game=game,
                    system_display=system_display,
                )
                if fallback_source is not None:
                    source = fallback_source
                    if asset is not None:
                        asset.file_path = fallback_source
                    self._log(progress, f"[scan] launchbox media fallback matched [{key}] -> {fallback_source}")
                else:
                    if asset is not None:
                        asset.verification_state = AssetVerificationState.VERIFIED_MISSING
                    result.files_skipped += 1
                    result.assets_missing_skipped += 1
                    warning = f"asset missing -> skipped [{key}]: {source or '(no metadata path)'}"
                    result.warnings.append(warning)
                    self._log(progress, f"[warn] {warning}")
                    continue
            if asset is not None:
                asset.verification_state = AssetVerificationState.VERIFIED_EXISTS

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
                self._log(progress, f"[dry-run] asset copied [{key}] -> {destination}")
            else:
                _copy_file(source, destination)
            copied[key] = destination
            result.assets_copied += 1
            if not dry_run:
                self._log(progress, f"asset copied [{key}] -> {destination}")
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


def _pick_assets(game: Game) -> dict[str, Asset]:
    """Select one representative source file per output slot.

    Priority is deterministic: first matching asset in the original list wins.
    """
    chosen: dict[str, Asset] = {}

    for asset in game.assets:
        if "image" not in chosen and asset.asset_type in IMAGE_TYPES:
            chosen["image"] = asset
        if "thumbnail" not in chosen and asset.asset_type in (AssetType.SCREENSHOT_GAMEPLAY, AssetType.SCREENSHOT_TITLE):
            chosen["thumbnail"] = asset
        if "marquee" not in chosen and asset.asset_type in MARQUEE_TYPES:
            chosen["marquee"] = asset
        if "video" not in chosen and asset.asset_type == AssetType.VIDEO:
            chosen["video"] = asset
        if "manual" not in chosen and asset.asset_type == AssetType.MANUAL:
            chosen["manual"] = asset
        if "bezel" not in chosen and asset.asset_type == AssetType.BEZEL:
            chosen["bezel"] = asset
        if "fanart" not in chosen and asset.asset_type in FANART_TYPES:
            chosen["fanart"] = asset

    return chosen


def _lookup_asset_fallback(
    key: str,
    library: Library,
    game: Game,
    system_display: str,
) -> Path | None:
    ecosystem = (library.detected_ecosystem or "").lower()
    if ecosystem == "launchbox":
        return _lookup_launchbox_asset_fallback(key=key, library=library, game=game, system_display=system_display)
    return _lookup_generic_asset_fallback(
        key=key,
        ecosystem=ecosystem,
        library=library,
        game=game,
        system_display=system_display,
    )


def _lookup_launchbox_asset_fallback(
    key: str,
    library: Library,
    game: Game,
    system_display: str,
) -> Path | None:
    """Resolve LaunchBox media by convention for selected games.

    This runs only when the metadata path is missing and only for selected games,
    so we avoid full-library media scans during analysis.
    """
    if (library.detected_ecosystem or "").lower() != "launchbox":
        return None
    launchbox_root = library.source_root
    if (launchbox_root / "Data" / "Platforms").exists():
        pass
    elif launchbox_root.name.lower() == "data" and (launchbox_root / "Platforms").exists():
        launchbox_root = launchbox_root.parent
    elif (launchbox_root / "LaunchBox" / "Data" / "Platforms").exists():
        launchbox_root = launchbox_root / "LaunchBox"

    search_roots = _launchbox_media_roots_for_key(launchbox_root, system_display, game.system_id, key)
    if not search_roots:
        return None

    for root in search_roots:
        if not root.exists():
            continue
        for base_name in _candidate_base_names(game):
            pattern = f"{glob_escape(base_name)}*"
            for match in sorted(root.glob(pattern)):
                if not match.is_file():
                    continue
                return match
    return None


def _lookup_generic_asset_fallback(
    key: str,
    ecosystem: str,
    library: Library,
    game: Game,
    system_display: str,
) -> Path | None:
    fallback_key = _ecosystem_fallback_key(ecosystem)
    folder_templates = ECOSYSTEM_MEDIA_FALLBACK_FOLDERS.get(fallback_key, {}).get(key)
    if not folder_templates:
        return None

    search_roots = _generic_media_roots(
        folder_templates=folder_templates,
        fallback_key=fallback_key,
        library=library,
        game=game,
        system_display=system_display,
    )
    for root in search_roots:
        if not root.exists():
            continue
        for base_name in _candidate_base_names(game):
            pattern = f"{glob_escape(base_name)}*"
            for match in sorted(root.glob(pattern)):
                if match.is_file():
                    return match
    return None


def _launchbox_media_roots_for_key(launchbox_root: Path, system_display: str, system_id: str, key: str) -> list[Path]:
    platform_candidates = _launchbox_platform_candidates(system_display, system_id)
    image_roots = [launchbox_root / "Images" / platform for platform in platform_candidates]
    video_roots = [launchbox_root / "Videos" / platform for platform in platform_candidates]
    manual_roots = [launchbox_root / "Manuals" / platform for platform in platform_candidates]
    image_primary_folders = [
        "Box - Front",
        "Box - Front - Reconstructed",
        "Box - 3D",
        "Cart - Front",
        "Cart - Back",
        "Cart - 3D",
        "Disc",
    ]
    screenshot_folders = [
        "Screenshot - Gameplay",
        "Screenshot - Game Title",
        "Screenshot - High Scores",
        "Screenshot - Game Over",
        "Screenshot - Game Select",
    ]
    marquee_folders = [
        "Clear Logo",
        "Arcade - Marquee",
        "Banner",
        "Steam Banner",
    ]
    fanart_folders = [
        "Fanart - Background",
        "Fanart - Box - Front",
        "Fanart - Box - Back",
        "Fanart - Cart - Front",
        "Fanart - Cart - Back",
        "Fanart - Disc",
    ]
    if key == "image":
        return [root / folder for root in image_roots for folder in (image_primary_folders + screenshot_folders)]
    if key == "thumbnail":
        return [root / folder for root in image_roots for folder in screenshot_folders]
    if key == "marquee":
        return [root / folder for root in image_roots for folder in marquee_folders]
    if key == "fanart":
        return [root / folder for root in image_roots for folder in fanart_folders]
    if key == "video":
        return video_roots
    if key == "manual":
        return manual_roots + [launchbox_root / "Manuals"]
    return []


def _launchbox_platform_candidates(system_display: str, system_id: str) -> list[str]:
    candidates: list[str] = []
    for value in (
        system_display,
        system_display.replace("_", " "),
        system_id,
        system_id.replace("_", " "),
    ):
        cleaned = value.strip()
        if cleaned and cleaned not in candidates:
            candidates.append(cleaned)
    return candidates


def _candidate_asset_keys_for_ecosystem(ecosystem: str) -> set[str]:
    if ecosystem == "launchbox":
        return {"image", "thumbnail", "video", "manual", "marquee", "fanart"}
    if ecosystem in {"es_classic", "batocera", "knulli", "amberelec", "jelos_rocknix", "arkos", "retrobat"}:
        return {"image", "thumbnail", "video", "manual", "marquee", "fanart"}
    if ecosystem in {"es_de", "emudeck", "retrodeck"}:
        return {"image", "thumbnail", "video", "manual", "marquee", "fanart"}
    if ecosystem in {"retroarch", "onionos", "muos"}:
        return {"image", "thumbnail", "video"}
    return set()


def _ecosystem_fallback_key(ecosystem: str) -> str:
    if ecosystem in {"es_classic", "batocera", "knulli", "amberelec", "jelos_rocknix", "arkos", "retrobat"}:
        return "es_family"
    if ecosystem in {"es_de", "emudeck", "retrodeck"}:
        return "es_de"
    if ecosystem in {"retroarch", "onionos", "muos"}:
        return ecosystem
    return ecosystem


def _candidate_base_names(game: Game) -> list[str]:
    values: list[str] = []
    for value in (game.title, game.rom_basename):
        normalized = value.strip() if value else ""
        if normalized and normalized not in values:
            values.append(normalized)
    return values


def _generic_media_roots(
    folder_templates: tuple[str, ...],
    fallback_key: str,
    library: Library,
    game: Game,
    system_display: str,
) -> list[Path]:
    roots: list[Path] = []
    source_root = library.source_root
    system_candidates = _launchbox_platform_candidates(system_display, game.system_id)
    for template in folder_templates:
        if "{system}" in template:
            for system_candidate in system_candidates:
                roots.append(source_root / template.format(system=system_candidate))
        elif fallback_key == "es_family":
            for ancestor in [game.rom_path.parent, game.rom_path.parent.parent, source_root]:
                if ancestor is None:
                    continue
                roots.append(ancestor / template)
        else:
            roots.append(source_root / template)

    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = root.as_posix().lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


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
        relative = os.path.relpath(target_path, base_dir).replace("\\", "/")
    except ValueError:
        # Cross-drive paths on Windows cannot always be relativized.
        return target_path.as_posix()
    if relative.startswith("./") or relative.startswith("../"):
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
    checks.append(f"Merge existing metadata: {'YES' if request.merge_existing_metadata else 'NO'}")
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


def _canonical_entry_path(path_value: str) -> str:
    value = path_value.replace("\\", "/").strip()
    while value.startswith("./"):
        value = value[2:]
    return value.lower()


def _merge_by_key(
    existing_entries: list[dict[str, str]],
    new_entries: list[dict[str, str]],
    key_field: str,
) -> list[dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    order: list[str] = []

    def upsert(entries: list[dict[str, str]]) -> None:
        for entry in entries:
            key_raw = entry.get(key_field, "").strip()
            if not key_raw:
                continue
            key = _canonical_entry_path(key_raw)
            if key not in merged:
                order.append(key)
            merged[key] = dict(entry)

    upsert(existing_entries)
    upsert(new_entries)

    # Keep output deterministic while preserving overwrite behavior.
    sorted_keys = sorted(order, key=lambda k: (k, merged[k].get("name", "").lower(), merged[k].get("title", "").lower()))
    return [merged[key] for key in sorted_keys]


def _merge_gamelist_entries(existing_entries: list[dict[str, str]], new_entries: list[dict[str, str]]) -> list[dict[str, str]]:
    return _merge_by_key(existing_entries, new_entries, key_field="path")


def _merge_launchbox_entries(
    existing_entries: list[dict[str, str]],
    new_entries: list[dict[str, str]],
) -> list[dict[str, str]]:
    return _merge_by_key(existing_entries, new_entries, key_field="application_path")
