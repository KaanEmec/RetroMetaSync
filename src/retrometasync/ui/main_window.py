from __future__ import annotations

from pathlib import Path
from queue import Empty, Queue
import threading
import time
import tkinter.messagebox as messagebox
import tkinter.filedialog as filedialog

import customtkinter as ctk

from retrometasync.core.conversion import ConversionEngine, ConversionRequest, ConversionResult
from retrometasync.core.conversion.system_mapping_store import (
    discover_destination_systems,
    load_system_mapping,
    save_system_mapping,
    suggest_system_mapping,
)
from retrometasync.core import LibraryDetector, LibraryNormalizer
from retrometasync.core.asset_verifier import verify_unchecked_assets
from retrometasync.core.dat_auto_detector import DatAutoDetector, DatDetectionMatch
from retrometasync.core.detection import DetectionCancelled, DetectionResult
from retrometasync.core.models import Game, Library
from retrometasync.core.normalizer import NormalizationResult
from retrometasync.core.preloaded_metadata import enrich_library_systems_with_preloaded_metadata
from retrometasync.ui.convert_dialog import ConvertPane
from retrometasync.ui.duplicate_conflict_dialog import show_duplicate_conflict_dialog
from retrometasync.ui.game_list import GameListPane
from retrometasync.ui.library_view import LibraryView
from retrometasync.ui.progress_log import ProgressLog
from retrometasync.ui.system_mapping_dialog import show_system_mapping_dialog


class _AnalysisCancelledError(Exception):
    """Internal signal used to abort analysis cooperatively."""


class MainWindow(ctk.CTk):
    """Top-level UI coordinator.

    This class keeps UI responsive by running heavy tasks (analyze/convert)
    in worker threads and handling their results on the main thread.
    """

    def __init__(self) -> None:
        super().__init__()
        self.title("RetroMetaSync")
        self.geometry("1300x820")
        self.minsize(1000, 700)

        self.detector = LibraryDetector()
        self.normalizer = LibraryNormalizer()
        self.dat_auto_detector = DatAutoDetector()
        self.converter = ConversionEngine()
        self.result_queue: Queue[tuple[str, object]] = Queue()
        self.current_library: Library | None = None
        self._analysis_running = False
        self._analysis_cancel_requested = False
        self._analysis_cancel_event = threading.Event()
        self._conversion_running = False
        self._asset_check_running = False
        self._dat_detection_running = False
        self._progress_lock = threading.Lock()
        self._last_progress_emit: dict[str, float] = {"analysis": 0.0, "conversion": 0.0, "verify_assets": 0.0}
        self._progress_emit_interval_sec = 0.15

        self._build_layout()
        self.after(100, self._poll_queue)

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self._build_source_controls()

        # Top section: equal-height dashboard and game list.
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.grid(row=2, column=0, padx=12, pady=(0, 8), sticky="nsew")
        self.top_frame.grid_columnconfigure(0, weight=1)
        self.top_frame.grid_columnconfigure(1, weight=1)
        self.top_frame.grid_rowconfigure(0, weight=1)

        self.library_view = LibraryView(self.top_frame)
        self.library_view.grid(row=0, column=0, padx=(0, 6), pady=0, sticky="nsew")
        self.library_view.set_on_system_selected(self._on_library_system_selected)

        self.game_list = GameListPane(self.top_frame)
        self.game_list.grid(row=0, column=1, padx=(6, 0), pady=0, sticky="nsew")
        self.game_list.set_on_check_unchecked_visible(self._on_check_unchecked_visible_assets)

        # Bottom section: progress log + conversion side-by-side.
        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.grid(row=3, column=0, padx=12, pady=(0, 12), sticky="nsew")
        self.bottom_frame.grid_columnconfigure(0, weight=2)
        self.bottom_frame.grid_columnconfigure(1, weight=1)
        self.bottom_frame.grid_rowconfigure(0, weight=1)

        self.convert_pane = ConvertPane(self.bottom_frame)
        self.convert_pane.grid(row=0, column=1, padx=(6, 0), pady=0, sticky="nsew")
        self.convert_pane.set_on_convert(self._on_convert)
        self.convert_pane.set_enabled(False)

        self.progress_log = ProgressLog(self.bottom_frame)
        self.progress_log.grid(row=0, column=0, padx=(0, 6), pady=0, sticky="nsew")

    def _build_source_controls(self) -> None:
        source_frame = ctk.CTkFrame(self)
        source_frame.grid(row=0, column=0, padx=12, pady=12, sticky="ew")
        source_frame.grid_columnconfigure(1, weight=1)

        label = ctk.CTkLabel(source_frame, text="📂 Source Library Folder", text_color=("#0f172a", "#f8fafc"))
        label.grid(row=0, column=0, padx=(10, 6), pady=10, sticky="w")

        self.source_entry = ctk.CTkEntry(source_frame, placeholder_text="Select your source library root")
        self.source_entry.grid(row=0, column=1, padx=(0, 6), pady=10, sticky="ew")

        self.browse_button = ctk.CTkButton(source_frame, text="📁 Browse", width=90, command=self._on_browse)
        self.browse_button.grid(row=0, column=2, padx=(0, 6), pady=10)

        self.analyze_button = ctk.CTkButton(source_frame, text="🔍 Analyze Library", command=self._on_analyze)
        self.analyze_button.grid(row=0, column=3, padx=(0, 10), pady=10)

        self.stop_analyze_button = ctk.CTkButton(
            source_frame,
            text="⏹ Stop",
            width=90,
            command=self._on_stop_analysis,
            state="disabled",
        )
        self.stop_analyze_button.grid(row=0, column=4, padx=(0, 6), pady=10)

        self.source_mode_var = ctk.StringVar(value="Auto (Meta)")
        self.source_mode_menu = ctk.CTkOptionMenu(
            source_frame,
            values=[
                "Auto (Meta)",
                "Auto (Scan)",
                "Auto (Force Scan)",
                "Launchbox Root/Data",
                "Single Rom Folder",
            ],
            variable=self.source_mode_var,
            width=170,
        )
        self.source_mode_menu.grid(row=0, column=5, padx=(0, 10), pady=10, sticky="e")

        self.preloaded_metadata_root_entry = ctk.CTkEntry(
            source_frame,
            placeholder_text="Optional: preloaded DAT folder",
            width=250,
        )
        self.preloaded_metadata_root_entry.grid(row=1, column=1, padx=(0, 6), pady=(0, 10), sticky="ew")
        default_preloaded_root = self._default_preloaded_metadata_root()
        if default_preloaded_root is not None:
            self.preloaded_metadata_root_entry.insert(0, str(default_preloaded_root))

        self.preloaded_metadata_root_browse = ctk.CTkButton(
            source_frame,
            text="📁 DATs",
            width=90,
            command=self._on_browse_preloaded_metadata_root,
        )
        self.preloaded_metadata_root_browse.grid(row=1, column=2, padx=(0, 6), pady=(0, 10))

        self.detect_dat_button = ctk.CTkButton(
            source_frame,
            text="🧠 Detect DATs",
            width=120,
            command=self._on_detect_dats,
        )
        self.detect_dat_button.grid(row=1, column=3, padx=(0, 6), pady=(0, 10), sticky="w")

        self.force_dat_file_button = ctk.CTkButton(
            source_frame,
            text="📄 Force DAT File",
            width=110,
            command=self._on_force_dat_file,
        )
        self.force_dat_file_button.grid(row=1, column=4, padx=(0, 6), pady=(0, 10), sticky="w")

        self.strict_dat_verify_var = ctk.BooleanVar(value=False)
        self.strict_dat_verify_check = ctk.CTkCheckBox(
            source_frame,
            text="Strict DAT verify (slower)",
            variable=self.strict_dat_verify_var,
        )
        self.strict_dat_verify_check.grid(row=1, column=5, padx=(0, 10), pady=(0, 10), sticky="w")

        self.preloaded_hashes_var = ctk.BooleanVar(value=False)
        self.preloaded_hashes_check = ctk.CTkCheckBox(
            source_frame,
            text="Use checksum fallback matching (slower)",
            variable=self.preloaded_hashes_var,
        )
        self.preloaded_hashes_check.grid(row=2, column=1, columnspan=5, padx=(0, 10), pady=(0, 10), sticky="w")

        self.status_label = ctk.CTkLabel(
            self,
            text="Select a source folder and run analysis.",
            anchor="w",
            text_color=("#1f2937", "#dce5f2"),
        )
        self.status_label.grid(row=1, column=0, padx=14, pady=(0, 8), sticky="ew")

    def _on_browse(self) -> None:
        initial = self.source_entry.get().strip() or str(Path.home())
        selected = filedialog.askdirectory(initialdir=initial)
        if selected:
            self.source_entry.delete(0, "end")
            self.source_entry.insert(0, selected)

    def _on_browse_preloaded_metadata_root(self) -> None:
        initial = self.preloaded_metadata_root_entry.get().strip() or self.source_entry.get().strip() or str(Path.home())
        selected = filedialog.askdirectory(initialdir=initial)
        if selected:
            self.preloaded_metadata_root_entry.delete(0, "end")
            self.preloaded_metadata_root_entry.insert(0, selected)

    def _default_preloaded_metadata_root(self) -> Path | None:
        project_root = Path(__file__).resolve().parents[3]
        candidate = project_root / "PreloadedMetaData"
        if candidate.exists() and candidate.is_dir():
            return candidate
        return None

    def _dat_detection_target_systems(self) -> list[str]:
        library = self.current_library
        if library is None:
            return []
        if self.game_list.has_active_filters():
            return self.game_list.visible_system_ids()
        return sorted(library.systems.keys())

    def _on_detect_dats(self) -> None:
        if self._analysis_running or self._conversion_running or self._asset_check_running or self._dat_detection_running:
            return
        if self.current_library is None:
            self._set_status("Analyze a library before detecting DAT files.", is_error=True)
            return

        target_system_ids = self._dat_detection_target_systems()
        if not target_system_ids:
            self._set_status("No visible systems to detect DAT files for.", is_error=True)
            return
        scope_label = "visible systems" if self.game_list.has_active_filters() else "all scanned systems"
        self._dat_detection_running = True
        self._set_global_busy(True)
        self.convert_pane.set_enabled(False)
        self.game_list.set_enabled(False)
        self.progress_log.log(f"Detecting DAT files for {len(target_system_ids)} {scope_label}...")
        self._set_status(f"Detecting DAT files for {len(target_system_ids)} systems...")

        source_root = self.current_library.source_root
        metadata_root = self._preloaded_metadata_root_from_ui()
        strict_verify = bool(self.strict_dat_verify_var.get())
        hash_fallback = bool(self.preloaded_hashes_var.get())

        worker = threading.Thread(
            target=self._detect_dats_worker,
            args=(target_system_ids, source_root, metadata_root, strict_verify, hash_fallback, "Auto Detect DATs"),
            daemon=True,
        )
        worker.start()

    def _detect_dats_worker(
        self,
        target_system_ids: list[str],
        source_root: Path,
        metadata_root: Path | None,
        strict_verify: bool,
        hash_fallback: bool,
        action_label: str,
    ) -> None:
        library = self.current_library
        if library is None:
            self.result_queue.put(("detect_dat_error", "No analyzed library loaded."))
            return
        try:
            detection = self.dat_auto_detector.detect_for_systems(
                source_root=source_root,
                metadata_root=metadata_root,
                target_system_ids=target_system_ids,
                strict_verify=strict_verify,
                games_by_system=library.games_by_system,
                progress_callback=lambda line: self._enqueue_progress("analysis", "detect_dat_progress", line),
            )
            overrides = {system_id: match.dat_path for system_id, match in detection.matches.items()}
            metadata_result = enrich_library_systems_with_preloaded_metadata(
                library=library,
                source_root=source_root,
                metadata_root=metadata_root,
                target_system_ids=target_system_ids,
                compute_missing_hashes=hash_fallback,
                progress_callback=lambda line: self._enqueue_progress("analysis", "detect_dat_progress", line),
                dat_override_by_system=overrides,
            )
            self.result_queue.put(
                (
                    "detect_dat_complete",
                    {
                        "target_count": len(target_system_ids),
                        "matches": detection.matches,
                        "unresolved": detection.unresolved_systems,
                        "warnings": detection.warnings + (metadata_result.warnings or []),
                        "enriched_games": metadata_result.enriched_games,
                        "action_label": action_label,
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            self.result_queue.put(("detect_dat_error", str(exc)))

    def _on_force_dat_file(self) -> None:
        if self._analysis_running or self._conversion_running or self._asset_check_running or self._dat_detection_running:
            return
        if self.current_library is None:
            self._set_status("Analyze a library before forcing DAT selection.", is_error=True)
            return
        target_system_ids = self._dat_detection_target_systems()
        if not target_system_ids:
            self._set_status("No visible systems to apply DAT file.", is_error=True)
            return
        initial = self.preloaded_metadata_root_entry.get().strip() or str(self.current_library.source_root)
        selected_file = filedialog.askopenfilename(
            initialdir=initial,
            filetypes=[("DAT/XML files", "*.dat *.xml"), ("All files", "*.*")],
        )
        if not selected_file:
            return
        dat_file = Path(selected_file)
        if not dat_file.exists() or not dat_file.is_file():
            self._set_status("Selected DAT file is invalid.", is_error=True)
            return
        self._run_dat_action(
            target_system_ids=target_system_ids,
            action_label="Force DAT File",
            worker_target=self._force_dat_file_worker,
            worker_args=(
                target_system_ids,
                self.current_library.source_root,
                dat_file,
                bool(self.preloaded_hashes_var.get()),
            ),
        )

    def _run_dat_action(self, *, target_system_ids: list[str], action_label: str, worker_target, worker_args: tuple) -> None:
        scope_label = "visible systems" if self.game_list.has_active_filters() else "all scanned systems"
        self._dat_detection_running = True
        self._set_global_busy(True)
        self.convert_pane.set_enabled(False)
        self.game_list.set_enabled(False)
        self.progress_log.log(f"{action_label}: {len(target_system_ids)} {scope_label}...")
        self._set_status(f"{action_label} running for {len(target_system_ids)} systems...")
        worker = threading.Thread(target=worker_target, args=worker_args, daemon=True)
        worker.start()

    def _force_dat_file_worker(
        self,
        target_system_ids: list[str],
        source_root: Path,
        dat_file: Path,
        hash_fallback: bool,
    ) -> None:
        library = self.current_library
        if library is None:
            self.result_queue.put(("detect_dat_error", "No analyzed library loaded."))
            return
        try:
            matches = {
                system_id: DatDetectionMatch(
                    system_id=system_id,
                    dat_path=dat_file,
                    confidence=100,
                    reason="manual-file",
                )
                for system_id in target_system_ids
            }
            metadata_result = enrich_library_systems_with_preloaded_metadata(
                library=library,
                source_root=source_root,
                metadata_root=dat_file.parent,
                target_system_ids=target_system_ids,
                compute_missing_hashes=hash_fallback,
                progress_callback=lambda line: self._enqueue_progress("analysis", "detect_dat_progress", line),
                dat_override_by_system={system_id: dat_file for system_id in target_system_ids},
            )
            self.result_queue.put(
                (
                    "detect_dat_complete",
                    {
                        "target_count": len(target_system_ids),
                        "matches": matches,
                        "unresolved": [],
                        "warnings": metadata_result.warnings or [],
                        "enriched_games": metadata_result.enriched_games,
                        "action_label": "Force DAT File",
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            self.result_queue.put(("detect_dat_error", str(exc)))

    def _on_analyze(self) -> None:
        if self._analysis_running or self._asset_check_running:
            return

        # Validate user input early and provide clear feedback in status line.
        source_text = self.source_entry.get().strip()
        if not source_text:
            self._set_status("Please choose a source folder first.", is_error=True)
            return

        source_path = Path(source_text)
        if not source_path.exists() or not source_path.is_dir():
            self._set_status("Selected source path is invalid.", is_error=True)
            return

        self.progress_log.clear()
        with self._progress_lock:
            self._last_progress_emit["analysis"] = 0.0
        self.progress_log.log(f"Analyzing: {source_path}")
        scan_mode = self._scan_mode_from_ui(self.source_mode_var.get())
        if scan_mode == "meta":
            self._set_status(
                "Running metadata-only analysis (no full ROM/asset checks). Selected items are validated during conversion."
            )
            self.progress_log.log(
                "[stage] Auto (Meta): metadata-only analyze enabled; ROM/asset existence checks are deferred to conversion."
            )
        else:
            self._set_status("Running detection and metadata normalization...")
        self._analysis_cancel_requested = False
        self._analysis_cancel_event.clear()
        self._analysis_running = True
        self._set_global_busy(True)
        self.convert_pane.set_enabled(False)
        self.current_library = None
        self.library_view.reset()
        self.game_list.reset()
        self.game_list.set_enabled(False)
        metadata_root = self._preloaded_metadata_root_from_ui()
        use_hash_fallback = bool(self.preloaded_hashes_var.get())

        worker = threading.Thread(
            target=self._analyze_worker,
            args=(source_path, scan_mode, metadata_root, use_hash_fallback),
            daemon=True,
        )
        worker.start()

    def _on_stop_analysis(self) -> None:
        if not self._analysis_running or self._analysis_cancel_requested:
            return
        self._analysis_cancel_requested = True
        self._analysis_cancel_event.set()
        self.progress_log.log("[stage] Stop requested. Finishing current scan step...")
        self._set_status("Stopping analysis...")
        self._update_analysis_stop_button_state()

    def _is_analysis_cancel_requested(self) -> bool:
        return self._analysis_cancel_event.is_set()

    def _update_analysis_stop_button_state(self) -> None:
        if self._analysis_running and not self._analysis_cancel_requested:
            self.stop_analyze_button.configure(state="normal", text="⏹ Stop")
            return
        if self._analysis_running and self._analysis_cancel_requested:
            self.stop_analyze_button.configure(state="disabled", text="⏳ Stopping...")
            return
        self.stop_analyze_button.configure(state="disabled", text="⏹ Stop")

    def _analyze_worker(
        self,
        source_path: Path,
        scan_mode: str,
        preloaded_metadata_root: Path | None,
        compute_missing_hashes: bool,
    ) -> None:
        def analysis_progress(message: str) -> None:
            if self._is_analysis_cancel_requested():
                raise _AnalysisCancelledError("Analysis cancelled by user.")
            self._enqueue_progress("analysis", "analysis_progress", message)

        try:
            analysis_progress("[stage] detect:start")
            detection_result = self.detector.detect(
                source_path,
                progress_callback=analysis_progress,
                scan_mode=scan_mode,
                cancel_requested=self._is_analysis_cancel_requested,
            )
            analysis_progress("[stage] detect:done")
            analysis_progress("[stage] normalize:start")
            normalization_result = self.normalizer.normalize(
                detection_result,
                progress_callback=analysis_progress,
                scan_mode=scan_mode,
                preloaded_metadata_root=preloaded_metadata_root,
                compute_missing_hashes=compute_missing_hashes,
            )
            analysis_progress("[stage] normalize:done")
            if self._is_analysis_cancel_requested():
                raise _AnalysisCancelledError("Analysis cancelled by user.")
            self.result_queue.put(("analysis_complete", (detection_result, normalization_result)))
        except (_AnalysisCancelledError, DetectionCancelled):
            self.result_queue.put(("analysis_cancelled", "Analysis cancelled by user."))
        except Exception as exc:  # noqa: BLE001
            self.result_queue.put(("analysis_error", str(exc)))

    def _poll_queue(self) -> None:
        # Worker threads publish events to this queue; UI consumes them here.
        try:
            while True:
                event_type, payload = self.result_queue.get_nowait()
                if event_type == "analysis_complete":
                    detection_result, normalization_result = payload  # type: ignore[misc]
                    self._on_analysis_complete(detection_result, normalization_result)
                elif event_type == "analysis_error":
                    self._on_analysis_error(str(payload))
                elif event_type == "analysis_cancelled":
                    self._on_analysis_cancelled(str(payload))
                elif event_type == "analysis_progress":
                    self.progress_log.log(str(payload))
                elif event_type == "conversion_progress":
                    self.progress_log.log(str(payload))
                elif event_type == "conversion_complete":
                    self._on_conversion_complete(payload)  # type: ignore[arg-type]
                elif event_type == "conversion_error":
                    self._on_conversion_error(str(payload))
                elif event_type == "verify_assets_progress":
                    self.progress_log.log(str(payload))
                elif event_type == "verify_assets_complete":
                    self._on_verify_assets_complete(payload)  # type: ignore[arg-type]
                elif event_type == "verify_assets_error":
                    self._on_verify_assets_error(str(payload))
                elif event_type == "detect_dat_progress":
                    self.progress_log.log(str(payload))
                elif event_type == "detect_dat_complete":
                    self._on_detect_dats_complete(payload)  # type: ignore[arg-type]
                elif event_type == "detect_dat_error":
                    self._on_detect_dats_error(str(payload))
        except Empty:
            pass
        finally:
            self.after(100, self._poll_queue)

    def _on_analysis_complete(
        self, detection_result: DetectionResult, normalization_result: NormalizationResult
    ) -> None:
        if self._analysis_cancel_requested:
            self._on_analysis_cancelled("Analysis cancelled by user.")
            return
        library = normalization_result.library
        self.current_library = library
        self.library_view.set_library(library)
        # Defer game list model build and table population so dashboard paints first.
        def deferred_game_list() -> None:
            self.game_list.set_library(
                library,
                progress_callback=lambda msg: self._enqueue_progress("analysis", "analysis_progress", msg),
            )
        self.after(0, deferred_game_list)

        self.progress_log.log(
            f"Detected ecosystem: {detection_result.detected_ecosystem} (confidence {detection_result.confidence})"
        )
        self.progress_log.log(f"Detected systems: {len(library.systems)}")

        for warning in detection_result.warnings:
            self.progress_log.log(f"[detect warning] {warning}")
        for warning in normalization_result.warnings:
            self.progress_log.log(f"[loader warning] {warning}")

        self._set_status(
            f"Analysis complete. Ecosystem: {library.detected_ecosystem} | Systems: {len(library.systems)}"
        )
        self._analysis_running = False
        self._analysis_cancel_requested = False
        self._analysis_cancel_event.clear()
        self._set_global_busy(False)
        has_games = any(library.games_by_system.values())
        self.convert_pane.set_enabled(has_games)
        self.game_list.set_enabled(True)

    def _on_analysis_error(self, message: str) -> None:
        self.progress_log.log(f"[error] {message}")
        self._set_status(f"Analysis failed: {message}", is_error=True)
        self._analysis_running = False
        self._analysis_cancel_requested = False
        self._analysis_cancel_event.clear()
        self._set_global_busy(False)
        self.convert_pane.set_enabled(False)
        self.game_list.set_enabled(True)

    def _on_analysis_cancelled(self, message: str) -> None:
        self.progress_log.log(f"[stage] {message}")
        self._set_status("Analysis stopped.")
        self._analysis_running = False
        self._analysis_cancel_requested = False
        self._analysis_cancel_event.clear()
        self._set_global_busy(False)
        self.convert_pane.set_enabled(False)
        self.game_list.set_enabled(True)

    def _set_status(self, message: str, is_error: bool = False) -> None:
        self.status_label.configure(
            text=message,
            text_color=("#b91c1c", "#fca5a5") if is_error else ("gray40", "gray75"),
        )

    def _on_convert(self) -> None:
        if self._analysis_running or self._conversion_running or self._asset_check_running:
            return
        if self.current_library is None:
            self._set_status("Analyze a library before conversion.", is_error=True)
            return

        # Conversion only runs for explicit user selection.
        selected_games = self.game_list.get_selected_games()
        selected_count = sum(len(games) for games in selected_games.values())
        if selected_count == 0:
            self._set_status("Select at least one game before conversion.", is_error=True)
            return

        output_text = self.convert_pane.get_output_path()
        if not output_text:
            self._set_status("Choose an output folder before conversion.", is_error=True)
            return

        output_root = Path(output_text)
        target = self.convert_pane.get_target()

        try:
            source_systems = sorted(selected_games.keys())
            saved_mapping = load_system_mapping(output_root, target)
            # If every selected source system is already mapped for this target/output root,
            # reuse those mappings directly and skip the mapping dialog.
            has_complete_saved_mapping = all(
                source_system in saved_mapping and saved_mapping[source_system].strip()
                for source_system in source_systems
            )
            if has_complete_saved_mapping:
                system_mapping = {source_system: saved_mapping[source_system].strip() for source_system in source_systems}
            else:
                destination_snapshot = discover_destination_systems(output_root, target)
                suggested_mapping = suggest_system_mapping(
                    source_systems=source_systems,
                    destination_systems=destination_snapshot.systems,
                    previous_mapping=saved_mapping,
                )
                system_mapping = show_system_mapping_dialog(
                    master=self,
                    source_systems=source_systems,
                    destination_systems=destination_snapshot.systems,
                    suggested_mapping=suggested_mapping,
                )
                if system_mapping is None:
                    self._set_status("Conversion cancelled during system mapping step.")
                    return
                save_system_mapping(output_root, target, system_mapping)
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Failed to prepare system mapping: {exc}", is_error=True)
            return

        preflight_request = ConversionRequest(
            library=self.current_library,
            selected_games=selected_games,
            target_ecosystem=target,
            output_root=output_root,
            export_dat=self.convert_pane.should_export_dat(),
            dry_run=self.convert_pane.is_dry_run(),
            overwrite_existing=self.convert_pane.should_overwrite_existing(),
            merge_existing_metadata=self.convert_pane.should_merge_existing_metadata(),
            system_mapping=system_mapping,
        )
        try:
            duplicate_conflicts = self.converter.preview_duplicate_conflicts(preflight_request)
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Failed duplicate preflight: {exc}", is_error=True)
            return
        conflict_decisions: dict[str, str] = {}
        if duplicate_conflicts:
            response = messagebox.askyesno(
                title="Duplicate Conflicts Found",
                message=f"Detected {len(duplicate_conflicts)} duplicate game conflict(s). Resolve now?",
                parent=self,
            )
            if not response:
                self._set_status("Conversion cancelled before duplicate conflict resolution.")
                return
            decisions = show_duplicate_conflict_dialog(self, duplicate_conflicts)
            if decisions is None:
                self._set_status("Conversion cancelled during duplicate conflict resolution.")
                return
            conflict_decisions = decisions

        self._conversion_running = True
        self.convert_pane.set_busy(True)
        self._set_global_busy(True)
        self.game_list.set_enabled(False)
        with self._progress_lock:
            self._last_progress_emit["conversion"] = 0.0
        self.progress_log.log(
            f"Starting conversion: target={target}, games={selected_count}, output={output_root.as_posix()}"
        )
        self._set_status("Conversion running...")

        request = ConversionRequest(
            library=self.current_library,
            selected_games=selected_games,
            target_ecosystem=target,
            output_root=output_root,
            export_dat=self.convert_pane.should_export_dat(),
            dry_run=self.convert_pane.is_dry_run(),
            overwrite_existing=self.convert_pane.should_overwrite_existing(),
            merge_existing_metadata=self.convert_pane.should_merge_existing_metadata(),
            system_mapping=system_mapping,
            conflict_decisions=conflict_decisions,
        )
        worker = threading.Thread(target=self._convert_worker, args=(request,), daemon=True)
        worker.start()

    def _convert_worker(self, request: ConversionRequest) -> None:
        try:
            result = self.converter.convert(
                request,
                progress=lambda line: self._enqueue_progress("conversion", "conversion_progress", line),
            )
            self.result_queue.put(("conversion_complete", result))
        except Exception as exc:  # noqa: BLE001
            self.result_queue.put(("conversion_error", str(exc)))

    def _on_conversion_complete(self, result: ConversionResult) -> None:
        for warning in result.warnings:
            self.progress_log.log(f"[warn] {warning}")
        self.progress_log.log(
            (
                f"Done: systems={result.systems_processed}, games={result.games_processed}, "
                f"roms={result.roms_copied}, assets={result.assets_copied}"
            )
        )
        self._set_status(
            f"Conversion complete ({result.target_ecosystem}) - {result.games_processed} games processed."
        )
        self._conversion_running = False
        self.convert_pane.set_busy(False)
        self._set_global_busy(False)
        self.game_list.set_enabled(True)

    def _on_conversion_error(self, message: str) -> None:
        self.progress_log.log(f"[error] Conversion failed: {message}")
        self._set_status(f"Conversion failed: {message}", is_error=True)
        self._conversion_running = False
        self.convert_pane.set_busy(False)
        self._set_global_busy(False)
        self.game_list.set_enabled(True)

    def _on_check_unchecked_visible_assets(self) -> None:
        if self._analysis_running or self._conversion_running or self._asset_check_running:
            return
        if self.current_library is None:
            self._set_status("Analyze a library before checking assets.", is_error=True)
            return

        visible_games = self.game_list.visible_unchecked_games()
        if not visible_games:
            self._set_status("No unchecked assets found in the visible list.")
            return

        library = self.current_library
        if library is None:
            self._set_status("Analyze a library before checking assets.", is_error=True)
            return
        games_with_display: list[tuple[str, Game, str]] = []
        for key, game in visible_games:
            system = library.systems.get(game.system_id)
            system_display = system.display_name if system is not None else game.system_id
            games_with_display.append((key, game, system_display))

        self._asset_check_running = True
        self._set_global_busy(True)
        self.convert_pane.set_enabled(False)
        self.game_list.set_enabled(False)
        with self._progress_lock:
            self._last_progress_emit["verify_assets"] = 0.0
        self.progress_log.log(f"Checking unchecked assets for {len(games_with_display)} visible games...")
        self._set_status("Verifying visible unchecked assets...")

        worker = threading.Thread(target=self._verify_assets_worker, args=(library, games_with_display), daemon=True)
        worker.start()

    def _verify_assets_worker(self, library: Library, visible_games: list[tuple[str, Game, str]]) -> None:
        try:
            updated_keys: list[str] = []
            changed_assets = 0
            total_games = len(visible_games)
            for index, (key, game, system_display) in enumerate(visible_games, start=1):
                self._enqueue_progress(
                    "verify_assets",
                    "verify_assets_progress",
                    f"[stage] Checking assets {index}/{total_games}: {system_display} - {game.title}",
                )
                changes = verify_unchecked_assets(game, library=library, system_display=system_display)
                if changes > 0:
                    updated_keys.append(key)
                    changed_assets += changes
            self._enqueue_progress(
                "verify_assets",
                "verify_assets_progress",
                f"Asset check finished: {len(visible_games)} visible games scanned, {changed_assets} assets updated.",
            )
            self.result_queue.put(
                (
                    "verify_assets_complete",
                    {
                        "updated_keys": updated_keys,
                        "checked_games": len(visible_games),
                        "changed_assets": changed_assets,
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            self.result_queue.put(("verify_assets_error", str(exc)))

    def _on_verify_assets_complete(self, payload: dict[str, object]) -> None:
        updated_keys = payload.get("updated_keys", [])
        if isinstance(updated_keys, list):
            self.game_list.refresh_asset_states_for_keys([str(key) for key in updated_keys])
        checked_games = int(payload.get("checked_games", 0))
        changed_assets = int(payload.get("changed_assets", 0))
        self.progress_log.log(f"Checked visible unchecked assets: games={checked_games}, updated_assets={changed_assets}")
        self._set_status(f"Asset check complete: {changed_assets} assets updated across {checked_games} visible games.")
        self._asset_check_running = False
        self._set_global_busy(False)
        has_games = bool(self.current_library and any(self.current_library.games_by_system.values()))
        self.convert_pane.set_enabled(has_games)
        self.game_list.set_enabled(True)

    def _on_verify_assets_error(self, message: str) -> None:
        self.progress_log.log(f"[error] Asset check failed: {message}")
        self._set_status(f"Asset check failed: {message}", is_error=True)
        self._asset_check_running = False
        self._set_global_busy(False)
        has_games = bool(self.current_library and any(self.current_library.games_by_system.values()))
        self.convert_pane.set_enabled(has_games)
        self.game_list.set_enabled(True)

    def _on_detect_dats_complete(self, payload: dict[str, object]) -> None:
        matches = payload.get("matches", {})
        unresolved = payload.get("unresolved", [])
        warnings = payload.get("warnings", [])
        target_count = int(payload.get("target_count", 0))
        enriched_games = int(payload.get("enriched_games", 0))
        action_label = str(payload.get("action_label", "DAT detection"))

        matched_count = len(matches) if isinstance(matches, dict) else 0
        unresolved_count = len(unresolved) if isinstance(unresolved, list) else 0
        if isinstance(matches, dict):
            for system_id, match in matches.items():
                dat_name = getattr(match, "dat_path", Path("-")).name
                confidence = getattr(match, "confidence", "n/a")
                self.progress_log.log(
                    f"[metadata] {system_id}: detected '{dat_name}' (confidence {confidence})"
                )
        if isinstance(unresolved, list) and unresolved:
            self.progress_log.log(f"[metadata] unresolved systems: {', '.join(str(item) for item in unresolved)}")
        if isinstance(warnings, list):
            for warning in warnings:
                self.progress_log.log(f"[metadata warning] {warning}")

        if self.current_library is not None:
            self.library_view.set_library(self.current_library)
            self.game_list.set_library(
                self.current_library,
                progress_callback=lambda msg: self._enqueue_progress("analysis", "detect_dat_progress", msg),
            )

        self._set_status(
            f"{action_label} complete. Matched {matched_count}/{target_count} systems; unresolved {unresolved_count}; "
            f"enriched {enriched_games} games."
        )
        self._dat_detection_running = False
        self._set_global_busy(False)
        has_games = bool(self.current_library and any(self.current_library.games_by_system.values()))
        self.convert_pane.set_enabled(has_games)
        self.game_list.set_enabled(True)

    def _on_detect_dats_error(self, message: str) -> None:
        self.progress_log.log(f"[error] DAT detection failed: {message}")
        self._set_status(f"DAT detection failed: {message}", is_error=True)
        self._dat_detection_running = False
        self._set_global_busy(False)
        has_games = bool(self.current_library and any(self.current_library.games_by_system.values()))
        self.convert_pane.set_enabled(has_games)
        self.game_list.set_enabled(True)

    def _set_global_busy(self, busy: bool) -> None:
        # Shared busy state to prevent conflicting actions while workers run.
        state = "disabled" if busy else "normal"
        self.analyze_button.configure(state=state)
        self.browse_button.configure(state=state)
        self.source_entry.configure(state=state)
        self.source_mode_menu.configure(state=state)
        self.preloaded_metadata_root_entry.configure(state=state)
        self.preloaded_metadata_root_browse.configure(state=state)
        self.detect_dat_button.configure(state=state)
        self.force_dat_file_button.configure(state=state)
        self.strict_dat_verify_check.configure(state=state)
        self.preloaded_hashes_check.configure(state=state)
        self._update_analysis_stop_button_state()

    def _enqueue_progress(self, channel: str, event_type: str, message: str) -> None:
        now = time.monotonic()
        with self._progress_lock:
            last = self._last_progress_emit.get(channel, 0.0)
            if not message.startswith("[stage]") and now - last < self._progress_emit_interval_sec:
                return
            self._last_progress_emit[channel] = now
        self.result_queue.put((event_type, message))

    def _on_library_system_selected(self, system_id: str) -> None:
        self.game_list.set_system_filter(system_id)

    @staticmethod
    def _scan_mode_from_ui(selection: str) -> str:
        mapping = {
            "Auto (Meta)": "meta",
            "Auto (Scan)": "deep",
            "Auto (Force Scan)": "force",
            "Launchbox Root/Data": "launchbox",
            "Single Rom Folder": "single_rom_folder",
        }
        return mapping.get(selection, "meta")

    def _preloaded_metadata_root_from_ui(self) -> Path | None:
        value = self.preloaded_metadata_root_entry.get().strip()
        if not value:
            return None
        candidate = Path(value)
        if candidate.exists() and candidate.is_dir():
            return candidate
        self._enqueue_progress("analysis", "analysis_progress", f"[metadata] Ignoring invalid DAT root: {value}")
        return None
