from __future__ import annotations

from pathlib import Path
from queue import Empty, Queue
import threading
import tkinter.filedialog as filedialog

import customtkinter as ctk

from retrometasync.core.conversion import ConversionEngine, ConversionRequest, ConversionResult
from retrometasync.core import LibraryDetector, LibraryNormalizer
from retrometasync.core.detection import DetectionResult
from retrometasync.core.models import Library
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
        if self._analysis_running:
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
        self.progress_log.log(f"Analyzing: {source_path}")
        self._set_status("Running detection and metadata normalization...")
        self._set_global_busy(True)
        self.convert_pane.set_enabled(False)
        self._analysis_running = True
        self.current_library = None
        self.library_view.reset()
        self.game_list.reset()
        self.game_list.set_enabled(False)

        worker = threading.Thread(target=self._analyze_worker, args=(source_path,), daemon=True)
        worker.start()

    def _analyze_worker(self, source_path: Path) -> None:
        try:
            detection_result = self.detector.detect(
                source_path,
                progress_callback=lambda line: self.result_queue.put(("analysis_progress", line)),
            )
            normalization_result = self.normalizer.normalize(
                detection_result,
                progress_callback=lambda line: self.result_queue.put(("analysis_progress", line)),
            )
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
                progress_callback=lambda msg: self.result_queue.put(("analysis_progress", msg)),
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
        if self._analysis_running or self._conversion_running:
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
        )
        worker = threading.Thread(target=self._convert_worker, args=(request,), daemon=True)
        worker.start()

    def _convert_worker(self, request: ConversionRequest) -> None:
        try:
            result = self.converter.convert(request, progress=lambda line: self.result_queue.put(("conversion_progress", line)))
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

    def _set_global_busy(self, busy: bool) -> None:
        # Shared busy state to prevent conflicting actions while workers run.
        state = "disabled" if busy else "normal"
        self.analyze_button.configure(state=state)
        self.browse_button.configure(state=state)
        self.source_entry.configure(state=state)
