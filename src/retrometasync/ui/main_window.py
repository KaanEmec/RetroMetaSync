from __future__ import annotations

from pathlib import Path
from queue import Empty, Queue
import threading
import time
import tkinter.filedialog as filedialog

import customtkinter as ctk

from retrometasync.core.conversion import ConversionEngine, ConversionRequest, ConversionResult
from retrometasync.core import LibraryDetector, LibraryNormalizer
from retrometasync.core.asset_verifier import verify_unchecked_assets
from retrometasync.core.detection import DetectionResult
from retrometasync.core.models import Game, Library
from retrometasync.core.normalizer import NormalizationResult
from retrometasync.ui.convert_dialog import ConvertPane
from retrometasync.ui.game_list import GameListPane
from retrometasync.ui.library_view import LibraryView
from retrometasync.ui.progress_log import ProgressLog


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
        self.converter = ConversionEngine()
        self.result_queue: Queue[tuple[str, object]] = Queue()
        self.current_library: Library | None = None
        self._analysis_running = False
        self._conversion_running = False
        self._asset_check_running = False
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

        self.source_mode_var = ctk.StringVar(value="Auto Detect")
        self.source_mode_menu = ctk.CTkOptionMenu(
            source_frame,
            values=[
                "Auto Detect",
                "LaunchBox (Root/Data)",
                "ES Family (gamelist)",
                "ES-DE",
                "RetroBat",
                "RetroArch/Playlist",
                "AttractMode",
                "Pegasus",
                "OnionOS",
                "muOS",
            ],
            variable=self.source_mode_var,
            width=170,
        )
        self.source_mode_menu.grid(row=0, column=4, padx=(0, 10), pady=10, sticky="e")

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
        self._set_status("Running detection and metadata normalization...")
        self._set_global_busy(True)
        self.convert_pane.set_enabled(False)
        self._analysis_running = True
        self.current_library = None
        self.library_view.reset()
        self.game_list.reset()
        self.game_list.set_enabled(False)
        preferred_ecosystem = self._preferred_ecosystem_from_ui(self.source_mode_var.get())

        worker = threading.Thread(
            target=self._analyze_worker,
            args=(source_path, preferred_ecosystem),
            daemon=True,
        )
        worker.start()

    def _analyze_worker(self, source_path: Path, preferred_ecosystem: str | None) -> None:
        try:
            self._enqueue_progress("analysis", "analysis_progress", "[stage] detect:start")
            detection_result = self.detector.detect(
                source_path,
                progress_callback=lambda line: self._enqueue_progress("analysis", "analysis_progress", line),
                preferred_ecosystem=preferred_ecosystem,
            )
            self._enqueue_progress("analysis", "analysis_progress", "[stage] detect:done")
            self._enqueue_progress("analysis", "analysis_progress", "[stage] normalize:start")
            normalization_result = self.normalizer.normalize(
                detection_result,
                progress_callback=lambda line: self._enqueue_progress("analysis", "analysis_progress", line),
            )
            self._enqueue_progress("analysis", "analysis_progress", "[stage] normalize:done")
            self.result_queue.put(("analysis_complete", (detection_result, normalization_result)))
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
        except Empty:
            pass
        finally:
            self.after(100, self._poll_queue)

    def _on_analysis_complete(
        self, detection_result: DetectionResult, normalization_result: NormalizationResult
    ) -> None:
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
        self._set_global_busy(False)
        has_games = any(library.games_by_system.values())
        self.convert_pane.set_enabled(has_games)
        self.game_list.set_enabled(True)
        self._analysis_running = False

    def _on_analysis_error(self, message: str) -> None:
        self.progress_log.log(f"[error] {message}")
        self._set_status(f"Analysis failed: {message}", is_error=True)
        self._set_global_busy(False)
        self.convert_pane.set_enabled(False)
        self.game_list.set_enabled(True)
        self._analysis_running = False

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

    def _set_global_busy(self, busy: bool) -> None:
        # Shared busy state to prevent conflicting actions while workers run.
        state = "disabled" if busy else "normal"
        self.analyze_button.configure(state=state)
        self.browse_button.configure(state=state)
        self.source_entry.configure(state=state)
        self.source_mode_menu.configure(state=state)

    def _enqueue_progress(self, channel: str, event_type: str, message: str) -> None:
        now = time.monotonic()
        with self._progress_lock:
            last = self._last_progress_emit.get(channel, 0.0)
            if not message.startswith("[stage]") and now - last < self._progress_emit_interval_sec:
                return
            self._last_progress_emit[channel] = now
        self.result_queue.put((event_type, message))

    @staticmethod
    def _preferred_ecosystem_from_ui(selection: str) -> str | None:
        mapping = {
            "LaunchBox (Root/Data)": "launchbox",
            "ES Family (gamelist)": "es_family",
            "ES-DE": "es_de",
            "RetroBat": "retrobat",
            "RetroArch/Playlist": "retroarch",
            "AttractMode": "attract_mode",
            "Pegasus": "pegasus",
            "OnionOS": "onionos",
            "muOS": "muos",
        }
        return mapping.get(selection)
