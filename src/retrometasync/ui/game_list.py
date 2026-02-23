"""Filterable multi-select game table using virtualized ttk.Treeview.

ViewModel holds row records and filter indexes; selection is stored by
stable game key. Treeview is populated in chunks to keep UI responsive.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from retrometasync.core.models import AssetType, AssetVerificationState, Game, Library
from retrometasync.ui.table_perf import (
    BATCH_INSERT_SIZE,
    FILTER_DEBOUNCE_MS,
    MAX_COLUMN_TEXT_LEN,
    BASE_TABLE_FONT_SIZE,
    BASE_TABLE_ROW_HEIGHT,
    MAX_TABLE_FONT_SIZE,
    MAX_TABLE_ROW_HEIGHT,
    MIN_TABLE_FONT_SIZE,
    MIN_TABLE_ROW_HEIGHT,
    get_dpi_scale,
    normalize_row_text,
)

IMAGE_ASSET_TYPES: set[AssetType] = {
    AssetType.BOX_FRONT,
    AssetType.BOX_BACK,
    AssetType.BOX_SPINE,
    AssetType.DISC,
    AssetType.SCREENSHOT_GAMEPLAY,
    AssetType.SCREENSHOT_TITLE,
    AssetType.SCREENSHOT_MENU,
    AssetType.MARQUEE,
    AssetType.WHEEL,
    AssetType.LOGO,
    AssetType.FANART,
    AssetType.BACKGROUND,
    AssetType.MIXIMAGE,
    AssetType.BEZEL,
}


@dataclass
class GameRowRecord:
    """Immutable row data for one game; display strings cached for fast filter/display."""
    key: str
    system_id: str
    game_title: str
    rom_filename: str
    assets: str
    has_image: bool
    has_video: bool
    has_manual: bool
    missing_image: bool
    missing_video: bool
    missing_manual: bool


def _build_key(system_id: str, game: Game) -> str:
    return f"{system_id}::{game.rom_path.as_posix()}"


def _asset_status(game: Game, asset_types: set[AssetType]) -> str:
    relevant_assets = [asset for asset in game.assets if asset.asset_type in asset_types]
    if any(asset.verification_state == AssetVerificationState.VERIFIED_EXISTS for asset in relevant_assets):
        return "has"
    if any(asset.verification_state == AssetVerificationState.VERIFIED_MISSING for asset in relevant_assets):
        return "missing"
    return "unchecked"


def _asset_tags(image_status: str, video_status: str, manual_status: str) -> str:
    def label(kind: str, status: str) -> str:
        if kind == "img":
            if status == "has":
                return "🖼 IMG"
            if status == "missing":
                return "⚪ NO-IMG"
            return "❔ UNCHECKED-IMG"
        if kind == "vid":
            if status == "has":
                return "🎞 VID"
            if status == "missing":
                return "⚪ NO-VID"
            return "❔ UNCHECKED-VID"
        if status == "has":
            return "📘 MAN"
        if status == "missing":
            return "⚪ NO-MAN"
        return "❔ UNCHECKED-MAN"

    parts = [
        label("img", image_status),
        label("vid", video_status),
        label("man", manual_status),
    ]
    return " | ".join(parts)


def _passes_asset_filter(record: GameRowRecord, asset_filter: str) -> bool:
    if asset_filter == "Any Assets":
        return True
    if asset_filter == "Has Images":
        return record.has_image
    if asset_filter == "Has Video":
        return record.has_video
    if asset_filter == "Has Manual":
        return record.has_manual
    if asset_filter == "Missing Video":
        return record.missing_video
    if asset_filter == "Missing Manual":
        return record.missing_manual
    return True


class GameListViewModel:
    """Holds all game row records and filter indexes for fast filtered views."""

    def __init__(self, library: Library) -> None:
        self._games_by_key: dict[str, Game] = {}
        self._rows: list[GameRowRecord] = []
        self._rows_by_key: dict[str, GameRowRecord] = {}
        self._system_to_keys: dict[str, list[str]] = {}
        self._all_keys_sorted: list[str] = []

        for system_id, games in library.games_by_system.items():
            keys_this_system: list[str] = []
            for game in games:
                key = _build_key(system_id, game)
                self._games_by_key[key] = game
                image_status = _asset_status(game, IMAGE_ASSET_TYPES)
                video_status = _asset_status(game, {AssetType.VIDEO})
                manual_status = _asset_status(game, {AssetType.MANUAL})
                has_image = image_status == "has"
                has_video = video_status == "has"
                has_manual = manual_status == "has"
                record = GameRowRecord(
                    key=key,
                    system_id=system_id,
                    game_title=normalize_row_text(game.title, MAX_COLUMN_TEXT_LEN),
                    rom_filename=normalize_row_text(game.rom_filename, MAX_COLUMN_TEXT_LEN),
                    assets=_asset_tags(image_status, video_status, manual_status),
                    has_image=has_image,
                    has_video=has_video,
                    has_manual=has_manual,
                    missing_image=image_status == "missing",
                    missing_video=video_status == "missing",
                    missing_manual=manual_status == "missing",
                )
                self._rows.append(record)
                self._rows_by_key[key] = record
                keys_this_system.append(key)
            self._system_to_keys[system_id] = keys_this_system

        self._all_keys_sorted = sorted(
            self._games_by_key.keys(),
            key=lambda k: (k.split("::", 1)[0], self._games_by_key[k].rom_filename.lower()),
        )

    def games_by_key(self) -> dict[str, Game]:
        return self._games_by_key

    def rows_by_key(self) -> dict[str, GameRowRecord]:
        return self._rows_by_key

    def filtered_keys(self, system_filter: str, asset_filter: str) -> list[str]:
        if system_filter == "All Systems":
            keys = list(self._all_keys_sorted)
        else:
            keys = list(self._system_to_keys.get(system_filter, []))
            keys.sort(key=lambda k: self._games_by_key[k].rom_filename.lower())

        if asset_filter == "Any Assets":
            return keys
        rows_by_key = {r.key: r for r in self._rows}
        return [k for k in keys if _passes_asset_filter(rows_by_key[k], asset_filter)]


def _apply_dark_treeview_style(
    widget: ttk.Treeview,
    scale: float | None = None,
) -> int:
    """Apply dark theme to GameList Treeview; scale font/row for DPI. Returns row height in pixels."""
    if scale is None:
        scale = get_dpi_scale(widget)
    font_size = max(MIN_TABLE_FONT_SIZE, min(MAX_TABLE_FONT_SIZE, round(BASE_TABLE_FONT_SIZE * scale)))
    row_height = max(MIN_TABLE_ROW_HEIGHT, min(MAX_TABLE_ROW_HEIGHT, round(BASE_TABLE_ROW_HEIGHT * scale)))
    style = ttk.Style(widget)
    style.theme_use("clam")
    style.configure(
        "GameList.Treeview",
        background="#1e293b",
        foreground="#e2e8f0",
        fieldbackground="#1e293b",
        borderwidth=0,
        rowheight=row_height,
        font=("Segoe UI", font_size),
    )
    style.configure(
        "GameList.Treeview.Heading",
        background="#334155",
        foreground="#f1f5f9",
        font=("Segoe UI", font_size, "bold"),
    )
    style.map("GameList.Treeview", background=[("selected", "#475569")], foreground=[("selected", "#f8fafc")])
    return row_height


class GameListPane(ctk.CTkFrame):
    """Filterable multi-select game table; uses ttk.Treeview and selection-by-key."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(border_width=1, border_color=("#cfd4dc", "#2f3745"))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._library: Library | None = None
        self._view_model: GameListViewModel | None = None
        self._selected_keys: set[str] = set()
        self._visible_keys: list[str] = []
        self._debounce_after_id: str | None = None
        self._chunk_after_id: str | None = None
        self._pending_insert_keys: list[str] = []
        self._progress_callback: Callable[[str], None] | None = None
        self._last_tree_rows: int | None = None
        self._sort_column: str | None = None
        self._sort_desc: bool = False

        self.title_label = ctk.CTkLabel(
            self,
            text="🎮 Game Selection",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=("#0f172a", "#f8fafc"),
        )
        self.title_label.grid(row=0, column=0, padx=10, pady=(10, 4), sticky="w")

        self.controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.controls_frame.grid(row=1, column=0, padx=10, pady=(0, 8), sticky="ew")
        for col in range(7):
            self.controls_frame.grid_columnconfigure(col, weight=0)
        self.controls_frame.grid_columnconfigure(6, weight=1)

        self.system_filter_var = ctk.StringVar(value="All Systems")
        self.system_filter = ctk.CTkOptionMenu(
            self.controls_frame,
            variable=self.system_filter_var,
            values=["All Systems"],
            command=lambda _: self._schedule_filter_refresh(),
            width=150,
        )
        self.system_filter.grid(row=0, column=0, padx=(0, 6), pady=0, sticky="w")

        self.asset_filter_var = ctk.StringVar(value="Any Assets")
        self.asset_filter = ctk.CTkOptionMenu(
            self.controls_frame,
            variable=self.asset_filter_var,
            values=["Any Assets", "Has Images", "Has Video", "Has Manual", "Missing Video", "Missing Manual"],
            command=lambda _: self._schedule_filter_refresh(),
            width=130,
        )
        self.asset_filter.grid(row=0, column=1, padx=(0, 6), pady=0, sticky="w")

        self.select_visible_btn = ctk.CTkButton(
            self.controls_frame, text="Select Visible", width=105, command=lambda: self._set_visible_selection(True)
        )
        self.select_visible_btn.grid(row=0, column=2, padx=(0, 6), pady=0, sticky="w")
        self.clear_visible_btn = ctk.CTkButton(
            self.controls_frame, text="Clear Visible", width=105, command=lambda: self._set_visible_selection(False)
        )
        self.clear_visible_btn.grid(row=0, column=3, padx=(0, 6), pady=0, sticky="w")
        self.select_all_btn = ctk.CTkButton(
            self.controls_frame, text="Select All", width=90, command=lambda: self._set_all_selection(True)
        )
        self.select_all_btn.grid(row=0, column=4, padx=(0, 6), pady=0, sticky="w")
        self.clear_all_btn = ctk.CTkButton(
            self.controls_frame, text="Clear All", width=90, command=lambda: self._set_all_selection(False)
        )
        self.clear_all_btn.grid(row=0, column=5, padx=(0, 6), pady=0, sticky="w")
        self.selection_label = ctk.CTkLabel(self.controls_frame, text="Selected: 0", anchor="e")
        self.selection_label.grid(row=0, column=6, padx=(6, 0), pady=0, sticky="e")

        self._table_container = ctk.CTkFrame(
            self,
            fg_color=("#f8fafc", "#0b1220"),
            border_width=1,
            border_color=("#d7dde7", "#344056"),
        )
        self._table_container.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self._table_container.grid_columnconfigure(0, weight=1)
        self._table_container.grid_rowconfigure(0, weight=1)

        self._tree = ttk.Treeview(
            self._table_container,
            columns=("selected", "system", "game_name", "rom_file", "assets"),
            show="headings",
            selectmode="extended",
            height=20,
            style="GameList.Treeview",
        )
        scale = get_dpi_scale(self._table_container)
        self._tree_row_height = _apply_dark_treeview_style(self._tree, scale)
        self._tree.heading("selected", text="", command=lambda c="selected": self._on_heading_click(c))
        self._tree.heading("system", text="🎯 System", command=lambda c="system": self._on_heading_click(c))
        self._tree.heading("game_name", text="🏷 Game Name", command=lambda c="game_name": self._on_heading_click(c))
        self._tree.heading("rom_file", text="🕹 ROM File", command=lambda c="rom_file": self._on_heading_click(c))
        self._tree.heading("assets", text="📦 Assets", command=lambda c="assets": self._on_heading_click(c))
        self._tree.column("selected", width=42, minwidth=42, stretch=False)
        self._tree.column("system", width=130, minwidth=100, stretch=False)
        self._tree.column("game_name", width=300, minwidth=180, stretch=True)
        self._tree.column("rom_file", width=300, minwidth=180, stretch=True)
        self._tree.column("assets", width=320, minwidth=220, stretch=True)

        scrollbar_width = max(14, round(14 * scale))
        scrollbar = tk.Scrollbar(self._table_container, orient=tk.VERTICAL, command=self._tree.yview, width=scrollbar_width)
        self._tree.configure(yscrollcommand=scrollbar.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self._table_container.bind("<Configure>", self._on_table_configure)
        self.after_idle(self._update_tree_height)
        self._refresh_heading_labels()

        self._tree.bind("<Double-1>", self._on_row_activate)
        self._tree.bind("<space>", self._on_space)
        self._info_label = ctk.CTkLabel(
            self._table_container,
            text="Analyze a library to populate game rows.",
            text_color=("#1f2937", "#dce5f2"),
            anchor="w",
        )

    def set_library(self, library: Library, progress_callback: Callable[[str], None] | None = None) -> None:
        self._library = library
        self._selected_keys.clear()
        self._sort_column = None
        self._sort_desc = False
        self._cancel_debounce()
        self._cancel_chunk()
        self._progress_callback = progress_callback

        if self._progress_callback:
            self._progress_callback("Building game list model...")
        system_values = ["All Systems"] + sorted(library.systems.keys())
        self.system_filter.configure(values=system_values)
        self.system_filter_var.set("All Systems")
        self.asset_filter_var.set("Any Assets")

        self._view_model = GameListViewModel(library)
        n = len(self._view_model.games_by_key())
        if self._progress_callback:
            self._progress_callback(f"Game list model: {n} games")
        self._refresh_heading_labels()
        self._refresh_table_from_filter()

    def reset(self) -> None:
        self._library = None
        self._view_model = None
        self._selected_keys.clear()
        self._visible_keys = []
        self._cancel_debounce()
        self._cancel_chunk()
        self.system_filter.configure(values=["All Systems"])
        self.system_filter_var.set("All Systems")
        self.asset_filter_var.set("Any Assets")
        self._sort_column = None
        self._sort_desc = False
        self._refresh_heading_labels()
        self._clear_tree()
        self._info_label.grid_remove()
        self._info_label.grid(row=0, column=0, columnspan=2, padx=8, pady=8, sticky="w")
        self._update_selection_label()

    def get_selected_games(self) -> dict[str, list[Game]]:
        selected: dict[str, list[Game]] = {}
        if not self._view_model:
            return selected
        gbk = self._view_model.games_by_key()
        for key in self._selected_keys:
            if key in gbk:
                system_id, _ = key.split("::", 1)
                selected.setdefault(system_id, []).append(gbk[key])
        return selected

    def selected_count(self) -> int:
        return len(self._selected_keys)

    def set_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.system_filter.configure(state=state)
        self.asset_filter.configure(state=state)
        self.select_visible_btn.configure(state=state)
        self.clear_visible_btn.configure(state=state)
        self.select_all_btn.configure(state=state)
        self.clear_all_btn.configure(state=state)

    def _schedule_filter_refresh(self) -> None:
        self._cancel_debounce()
        self._debounce_after_id = self.after(FILTER_DEBOUNCE_MS, self._apply_filter_refresh)

    def _on_table_configure(self, event) -> None:
        if event.height <= 0 or not hasattr(self, "_tree_row_height"):
            return
        rows = max(8, event.height // self._tree_row_height)
        if rows != self._last_tree_rows:
            self._last_tree_rows = rows
            self._tree.configure(height=rows)

    def _update_tree_height(self) -> None:
        if not hasattr(self, "_tree_row_height"):
            return
        try:
            h = self._table_container.winfo_height()
            if h <= 0:
                return
            rows = max(8, h // self._tree_row_height)
            if rows != self._last_tree_rows:
                self._last_tree_rows = rows
                self._tree.configure(height=rows)
        except tk.TclError:
            pass

    def _cancel_debounce(self) -> None:
        if self._debounce_after_id is not None:
            self.after_cancel(self._debounce_after_id)
            self._debounce_after_id = None

    def _cancel_chunk(self) -> None:
        if self._chunk_after_id is not None:
            self.after_cancel(self._chunk_after_id)
            self._chunk_after_id = None

    def _apply_filter_refresh(self) -> None:
        self._debounce_after_id = None
        self._refresh_table_from_filter()

    def _refresh_table_from_filter(self) -> None:
        self._cancel_chunk()
        self._clear_tree()
        if not self._view_model:
            self._show_empty_message("Analyze a library to populate game rows.")
            self._update_selection_label()
            return

        system_filter = self.system_filter_var.get()
        asset_filter = self.asset_filter_var.get()
        filtered = self._view_model.filtered_keys(system_filter, asset_filter)
        filtered = self._sort_keys(filtered)
        self._visible_keys = filtered

        if not filtered:
            self._show_empty_message("No games found for current filters.")
            self._update_selection_label()
            return

        self._info_label.grid_remove()
        self._tree.grid(row=0, column=0, sticky="nsew")
        gbk = self._view_model.games_by_key()
        rows_by_key = self._view_model.rows_by_key()

        self._pending_insert_keys = filtered
        self._insert_next_batch(gbk, rows_by_key)

    def _clear_tree(self) -> None:
        for iid in self._tree.get_children():
            self._tree.delete(iid)

    def _show_empty_message(self, message: str) -> None:
        self._tree.grid_remove()
        self._info_label.configure(text=message)
        self._info_label.grid(row=0, column=0, columnspan=2, padx=8, pady=8, sticky="w")

    def _insert_next_batch(
        self,
        gbk: dict[str, Game],
        rows_by_key: dict[str, GameRowRecord],
    ) -> None:
        if not self._pending_insert_keys:
            self._update_selection_label()
            return
        chunk = self._pending_insert_keys[:BATCH_INSERT_SIZE]
        self._pending_insert_keys = self._pending_insert_keys[BATCH_INSERT_SIZE:]
        for key in chunk:
            record = rows_by_key.get(key)
            if not record:
                continue
            sel = "[x]" if key in self._selected_keys else "[ ]"
            self._tree.insert(
                "",
                tk.END,
                iid=key,
                values=(sel, record.system_id, record.game_title, record.rom_filename, record.assets),
            )
        self._update_selection_label()
        if self._pending_insert_keys:
            self._chunk_after_id = self.after(10, lambda: self._insert_next_batch(gbk, rows_by_key))
        else:
            self._chunk_after_id = None
            if self._progress_callback:
                self._progress_callback(f"Game table ready: {len(self._visible_keys)} rows")

    def _on_row_activate(self, event) -> None:
        region = self._tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        iid = self._tree.identify_row(event.y)
        if self._view_model and iid and iid in self._view_model.games_by_key():
            self._toggle_selection(iid)

    def _on_space(self, event) -> None:
        focus = self._tree.focus()
        if focus and (not self._view_model or focus in self._view_model.games_by_key()):
            self._toggle_selection(focus)

    def _toggle_selection(self, key: str) -> None:
        if key in self._selected_keys:
            self._selected_keys.discard(key)
            self._tree.set(key, "selected", "[ ]")
        else:
            self._selected_keys.add(key)
            self._tree.set(key, "selected", "[x]")
        self._update_selection_label()

    def _set_visible_selection(self, selected: bool) -> None:
        if selected:
            for k in self._visible_keys:
                self._selected_keys.add(k)
        else:
            for k in self._visible_keys:
                self._selected_keys.discard(k)
        self._refresh_selection_indicators()
        self._update_selection_label()

    def _set_all_selection(self, selected: bool) -> None:
        if not self._view_model:
            return
        all_keys = set(self._view_model.games_by_key())
        if selected:
            self._selected_keys |= all_keys
        else:
            self._selected_keys.clear()
        self._refresh_selection_indicators()
        self._update_selection_label()

    def _refresh_selection_indicators(self) -> None:
        for iid in self._tree.get_children():
            self._tree.set(iid, "selected", "[x]" if iid in self._selected_keys else "[ ]")

    def _update_selection_label(self) -> None:
        self.selection_label.configure(text=f"Selected: {self.selected_count()}")

    def _sort_keys(self, keys: list[str]) -> list[str]:
        if not self._view_model or not self._sort_column:
            return keys
        rows_by_key = self._view_model.rows_by_key()
        if self._sort_column == "selected":
            return sorted(keys, key=lambda k: (k not in self._selected_keys, k), reverse=self._sort_desc)
        if self._sort_column == "system":
            return sorted(keys, key=lambda k: rows_by_key[k].system_id.lower(), reverse=self._sort_desc)
        if self._sort_column == "game_name":
            return sorted(keys, key=lambda k: rows_by_key[k].game_title.lower(), reverse=self._sort_desc)
        if self._sort_column == "rom_file":
            return sorted(keys, key=lambda k: rows_by_key[k].rom_filename.lower(), reverse=self._sort_desc)
        if self._sort_column == "assets":
            return sorted(keys, key=lambda k: rows_by_key[k].assets.lower(), reverse=self._sort_desc)
        return keys

    def _on_heading_click(self, column: str) -> None:
        if self._sort_column == column:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_column = column
            self._sort_desc = False
        self._refresh_heading_labels()
        self._refresh_table_from_filter()

    def _refresh_heading_labels(self) -> None:
        label_map = {
            "selected": "",
            "system": "🎯 System",
            "game_name": "🏷 Game Name",
            "rom_file": "🕹 ROM File",
            "assets": "📦 Assets",
        }
        for col, base in label_map.items():
            if col == self._sort_column:
                arrow = " ↓" if self._sort_desc else " ↑"
                self._tree.heading(col, text=f"{base}{arrow}")
            else:
                self._tree.heading(col, text=base)
