"""Library dashboard: summary and per-system counts in a compact ttk.Treeview."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from retrometasync.core.models import AssetType, Library
from retrometasync.ui.table_perf import (
    BASE_TABLE_FONT_SIZE,
    BASE_TABLE_ROW_HEIGHT,
    MAX_TABLE_FONT_SIZE,
    MAX_TABLE_ROW_HEIGHT,
    MIN_TABLE_FONT_SIZE,
    MIN_TABLE_ROW_HEIGHT,
    get_dpi_scale,
)

_IMAGE_LIKE_ASSET_TYPES: set[AssetType] = {
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


def _apply_dark_treeview_style(
    widget: ttk.Treeview,
    scale: float | None = None,
) -> int:
    """Apply dark theme to Library Treeview; scale font/row for DPI. Returns row height in pixels."""
    if scale is None:
        scale = get_dpi_scale(widget)
    font_size = max(MIN_TABLE_FONT_SIZE, min(MAX_TABLE_FONT_SIZE, round(BASE_TABLE_FONT_SIZE * scale)))
    row_height = max(MIN_TABLE_ROW_HEIGHT, min(MAX_TABLE_ROW_HEIGHT, round(BASE_TABLE_ROW_HEIGHT * scale)))
    style = ttk.Style(widget)
    style.theme_use("clam")
    style.configure(
        "Library.Treeview",
        background="#1e293b",
        foreground="#e2e8f0",
        fieldbackground="#1e293b",
        borderwidth=0,
        rowheight=row_height,
        font=("Segoe UI", font_size),
    )
    style.configure(
        "Library.Treeview.Heading",
        background="#334155",
        foreground="#f1f5f9",
        font=("Segoe UI", font_size, "bold"),
    )
    style.map(
        "Library.Treeview",
        background=[("selected", "#475569")],
        foreground=[("selected", "#f8fafc")],
    )
    style.map("Library.Treeview", background=[("alternate", "#252d3d")])
    return row_height


class LibraryView(ctk.CTkFrame):
    """Dashboard: ecosystem summary and a Treeview table of systems with ROM/asset counts."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(border_width=1, border_color=("#cfd4dc", "#2f3745"))
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            self,
            text="📚 Library Dashboard",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=("#0f172a", "#f8fafc"),
        )
        self.title_label.grid(row=0, column=0, padx=10, pady=(10, 4), sticky="w")

        self.summary_label = ctk.CTkLabel(
            self,
            text="No library analyzed yet.",
            text_color=("#1f2937", "#dce5f2"),
            anchor="w",
        )
        self.summary_label.grid(row=1, column=0, padx=10, pady=(0, 8), sticky="ew")

        self._table_container = ctk.CTkFrame(
            self,
            fg_color=("#f8fafc", "#0b1220"),
            border_width=1,
            border_color=("#d7dde7", "#344056"),
        )
        self._table_container.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self._table_container.grid_columnconfigure(0, weight=1)
        self._table_container.grid_rowconfigure(0, weight=1)
        self._last_tree_rows: int | None = None
        self._rows_cache: list[tuple[str, int, int, int, int]] = []
        self._sort_column: str = "system"
        self._sort_desc: bool = False

        self._tree = ttk.Treeview(
            self._table_container,
            columns=("system", "roms", "images", "videos", "manuals"),
            show="headings",
            selectmode="none",
            height=20,
            style="Library.Treeview",
        )
        scale = get_dpi_scale(self._table_container)
        self._tree_row_height = _apply_dark_treeview_style(self._tree, scale)
        self._tree.heading("system", text="System", command=lambda c="system": self._on_heading_click(c))
        self._tree.heading("roms", text="ROMs", command=lambda c="roms": self._on_heading_click(c))
        self._tree.heading("images", text="Images", command=lambda c="images": self._on_heading_click(c))
        self._tree.heading("videos", text="Videos", command=lambda c="videos": self._on_heading_click(c))
        self._tree.heading("manuals", text="Manuals", command=lambda c="manuals": self._on_heading_click(c))
        self._tree.column("system", width=220, minwidth=140, stretch=True)
        self._tree.column("roms", width=90, minwidth=70, stretch=True)
        self._tree.column("images", width=110, minwidth=80, stretch=True)
        self._tree.column("videos", width=110, minwidth=80, stretch=True)
        self._tree.column("manuals", width=120, minwidth=90, stretch=True)

        scrollbar_width = max(14, round(14 * scale))
        scrollbar = tk.Scrollbar(self._table_container, orient=tk.VERTICAL, command=self._tree.yview, width=scrollbar_width)
        self._tree.configure(yscrollcommand=scrollbar.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._table_container.bind("<Configure>", self._on_table_configure)
        self.after_idle(self._update_tree_height)

    def _on_table_configure(self, event) -> None:
        if event.height <= 0 or not hasattr(self, "_tree_row_height"):
            return
        rows = max(6, event.height // self._tree_row_height)
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
            rows = max(6, h // self._tree_row_height)
            if rows != self._last_tree_rows:
                self._last_tree_rows = rows
                self._tree.configure(height=rows)
        except tk.TclError:
            pass

    def set_library(self, library: Library) -> None:
        self.summary_label.configure(
            text=(
                f"Ecosystem: {library.detected_ecosystem or 'unknown'}"
                f" | Confidence: {library.confidence if library.confidence is not None else 'n/a'}"
                f" | Systems: {len(library.systems)}"
            )
        )

        self._rows_cache = []
        systems = sorted(library.systems.values(), key=lambda s: s.system_id)
        for system in systems:
            games = library.games_by_system.get(system.system_id, [])
            rom_count = len(games)
            image_count = 0
            video_count = 0
            manual_count = 0
            for game in games:
                has_image = any(a.asset_type in _IMAGE_LIKE_ASSET_TYPES for a in game.assets)
                has_video = any(a.asset_type == AssetType.VIDEO for a in game.assets)
                has_manual = any(a.asset_type == AssetType.MANUAL for a in game.assets)
                image_count += int(has_image)
                video_count += int(has_video)
                manual_count += int(has_manual)

            self._rows_cache.append((system.display_name, rom_count, image_count, video_count, manual_count))
        self._render_rows()
        self._update_tree_height()

    def reset(self) -> None:
        for iid in self._tree.get_children():
            self._tree.delete(iid)
        self._rows_cache = []
        self.summary_label.configure(text="No library analyzed yet.")

    def _render_rows(self) -> None:
        for iid in self._tree.get_children():
            self._tree.delete(iid)

        rows = list(self._rows_cache)
        col_idx = {"system": 0, "roms": 1, "images": 2, "videos": 3, "manuals": 4}[self._sort_column]
        if self._sort_column == "system":
            rows.sort(key=lambda r: str(r[col_idx]).lower(), reverse=self._sort_desc)
        else:
            rows.sort(key=lambda r: int(r[col_idx]), reverse=self._sort_desc)

        for idx, row in enumerate(rows):
            iid = self._tree.insert(
                "",
                tk.END,
                values=(row[0], str(row[1]), str(row[2]), str(row[3]), str(row[4])),
            )
            if idx % 2 == 1:
                self._tree.item(iid, tags=("alternate",))
        self._refresh_heading_labels()

    def _on_heading_click(self, column: str) -> None:
        if self._sort_column == column:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_column = column
            self._sort_desc = False
        self._render_rows()

    def _refresh_heading_labels(self) -> None:
        labels = {
            "system": "System",
            "roms": "ROMs",
            "images": "Images",
            "videos": "Videos",
            "manuals": "Manuals",
        }
        for col, label in labels.items():
            if col == self._sort_column:
                arrow = " ↓" if self._sort_desc else " ↑"
                self._tree.heading(col, text=f"{label}{arrow}")
            else:
                self._tree.heading(col, text=label)
