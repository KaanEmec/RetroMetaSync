from __future__ import annotations

import customtkinter as ctk

from retrometasync.core.models import AssetType, Game, Library


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


class GameListPane(ctk.CTkFrame):
    """Filterable multi-select game table used as conversion input."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self._library: Library | None = None
        self._games_by_key: dict[str, Game] = {}
        self._vars_by_key: dict[str, ctk.BooleanVar] = {}
        self._visible_keys: list[str] = []

        self.title_label = ctk.CTkLabel(self, text="Game Selection", font=ctk.CTkFont(size=14, weight="bold"))
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
            command=lambda _: self._render_rows(),
            width=150,
        )
        self.system_filter.grid(row=0, column=0, padx=(0, 6), pady=0, sticky="w")

        self.asset_filter_var = ctk.StringVar(value="Any Assets")
        self.asset_filter = ctk.CTkOptionMenu(
            self.controls_frame,
            variable=self.asset_filter_var,
            values=["Any Assets", "Has Images", "Has Video", "Has Manual", "Missing Video", "Missing Manual"],
            command=lambda _: self._render_rows(),
            width=130,
        )
        self.asset_filter.grid(row=0, column=1, padx=(0, 6), pady=0, sticky="w")

        self.select_visible_btn = ctk.CTkButton(
            self.controls_frame,
            text="Select Visible",
            width=105,
            command=lambda: self._set_visible_selection(True),
        )
        self.select_visible_btn.grid(row=0, column=2, padx=(0, 6), pady=0, sticky="w")

        self.clear_visible_btn = ctk.CTkButton(
            self.controls_frame,
            text="Clear Visible",
            width=105,
            command=lambda: self._set_visible_selection(False),
        )
        self.clear_visible_btn.grid(row=0, column=3, padx=(0, 6), pady=0, sticky="w")

        self.select_all_btn = ctk.CTkButton(
            self.controls_frame,
            text="Select All",
            width=90,
            command=lambda: self._set_all_selection(True),
        )
        self.select_all_btn.grid(row=0, column=4, padx=(0, 6), pady=0, sticky="w")

        self.clear_all_btn = ctk.CTkButton(
            self.controls_frame,
            text="Clear All",
            width=90,
            command=lambda: self._set_all_selection(False),
        )
        self.clear_all_btn.grid(row=0, column=5, padx=(0, 6), pady=0, sticky="w")

        self.selection_label = ctk.CTkLabel(self.controls_frame, text="Selected: 0", anchor="e")
        self.selection_label.grid(row=0, column=6, padx=(6, 0), pady=0, sticky="e")

        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=2, column=0, padx=10, pady=(0, 4), sticky="ew")
        self.header_frame.grid_columnconfigure(2, weight=1)
        self._add_header_labels()

        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.scroll.grid_columnconfigure(2, weight=1)
        self.scroll.grid_columnconfigure(3, weight=0)

        self.empty_label = ctk.CTkLabel(
            self.scroll,
            text="Analyze a library to populate game rows.",
            text_color=("gray45", "gray70"),
            anchor="w",
        )
        self.empty_label.grid(row=0, column=0, columnspan=4, padx=4, pady=8, sticky="w")

    def set_library(self, library: Library) -> None:
        # Rebuild rows/filters whenever a new library is analyzed.
        self._library = library
        self._games_by_key.clear()
        self._vars_by_key.clear()

        system_values = ["All Systems"]
        for system_id in sorted(library.systems):
            system_values.append(system_id)

        self.system_filter.configure(values=system_values)
        self.system_filter_var.set("All Systems")
        self.asset_filter_var.set("Any Assets")

        for system_id, games in library.games_by_system.items():
            for game in games:
                key = self._build_key(system_id, game)
                self._games_by_key[key] = game
                self._vars_by_key[key] = ctk.BooleanVar(value=False)

        self._render_rows()
        self._update_selection_label()

    def reset(self) -> None:
        self._library = None
        self._games_by_key.clear()
        self._vars_by_key.clear()
        self.system_filter.configure(values=["All Systems"])
        self.system_filter_var.set("All Systems")
        self.asset_filter_var.set("Any Assets")
        self._render_rows()
        self._update_selection_label()

    def get_selected_games(self) -> dict[str, list[Game]]:
        # Conversion engine consumes this grouped structure directly.
        selected: dict[str, list[Game]] = {}
        for key, variable in self._vars_by_key.items():
            if not variable.get():
                continue
            system_id, _ = key.split("::", 1)
            selected.setdefault(system_id, []).append(self._games_by_key[key])
        return selected

    def selected_count(self) -> int:
        return sum(1 for variable in self._vars_by_key.values() if variable.get())

    def set_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.system_filter.configure(state=state)
        self.asset_filter.configure(state=state)
        self.select_visible_btn.configure(state=state)
        self.clear_visible_btn.configure(state=state)
        self.select_all_btn.configure(state=state)
        self.clear_all_btn.configure(state=state)

    def _add_header_labels(self) -> None:
        headers = ("", "System", "ROM Filename / Clean Game Name", "Assets")
        for column, header in enumerate(headers):
            label = ctk.CTkLabel(self.header_frame, text=header, font=ctk.CTkFont(weight="bold"), anchor="w")
            label.grid(row=0, column=column, padx=4, pady=0, sticky="w")

    def _render_rows(self) -> None:
        # Re-render from in-memory model to keep UI logic deterministic.
        for child in self.scroll.winfo_children():
            child.destroy()

        filtered_keys = self._filtered_keys()
        self._visible_keys = filtered_keys

        if not filtered_keys:
            message = "No games found for current filters." if self._library else "Analyze a library to populate game rows."
            label = ctk.CTkLabel(self.scroll, text=message, text_color=("gray45", "gray70"), anchor="w")
            label.grid(row=0, column=0, columnspan=4, padx=4, pady=8, sticky="w")
            return

        for row, key in enumerate(filtered_keys):
            game = self._games_by_key[key]
            system_id, _ = key.split("::", 1)
            variable = self._vars_by_key[key]
            checkbox = ctk.CTkCheckBox(self.scroll, text="", variable=variable, command=self._update_selection_label)
            checkbox.grid(row=row, column=0, padx=(2, 4), pady=2, sticky="w")

            system_label = ctk.CTkLabel(self.scroll, text=system_id, anchor="w")
            system_label.grid(row=row, column=1, padx=4, pady=2, sticky="w")

            display_title = f"{game.rom_filename}  |  {game.title}"
            title_label = ctk.CTkLabel(self.scroll, text=display_title, anchor="w")
            title_label.grid(row=row, column=2, padx=4, pady=2, sticky="w")

            asset_label = ctk.CTkLabel(self.scroll, text=self._asset_tags(game), anchor="w")
            asset_label.grid(row=row, column=3, padx=4, pady=2, sticky="w")

    def _filtered_keys(self) -> list[str]:
        selected_system = self.system_filter_var.get()
        selected_asset_filter = self.asset_filter_var.get()

        keys: list[str] = []
        for key, game in self._games_by_key.items():
            system_id, _ = key.split("::", 1)
            if selected_system != "All Systems" and system_id != selected_system:
                continue
            if not self._passes_asset_filter(game, selected_asset_filter):
                continue
            keys.append(key)

        keys.sort(key=lambda item: (item.split("::", 1)[0], self._games_by_key[item].rom_filename.lower()))
        return keys

    def _passes_asset_filter(self, game: Game, asset_filter: str) -> bool:
        has_image = any(asset.asset_type in IMAGE_ASSET_TYPES for asset in game.assets)
        has_video = any(asset.asset_type == AssetType.VIDEO for asset in game.assets)
        has_manual = any(asset.asset_type == AssetType.MANUAL for asset in game.assets)

        if asset_filter == "Any Assets":
            return True
        if asset_filter == "Has Images":
            return has_image
        if asset_filter == "Has Video":
            return has_video
        if asset_filter == "Has Manual":
            return has_manual
        if asset_filter == "Missing Video":
            return not has_video
        if asset_filter == "Missing Manual":
            return not has_manual
        return True

    def _set_visible_selection(self, selected: bool) -> None:
        for key in self._visible_keys:
            self._vars_by_key[key].set(selected)
        self._update_selection_label()

    def _set_all_selection(self, selected: bool) -> None:
        for variable in self._vars_by_key.values():
            variable.set(selected)
        self._update_selection_label()

    def _update_selection_label(self) -> None:
        count = self.selected_count()
        self.selection_label.configure(text=f"Selected: {count}")

    @staticmethod
    def _build_key(system_id: str, game: Game) -> str:
        return f"{system_id}::{game.rom_path.as_posix()}"

    @staticmethod
    def _asset_tags(game: Game) -> str:
        has_image = any(asset.asset_type in IMAGE_ASSET_TYPES for asset in game.assets)
        has_video = any(asset.asset_type == AssetType.VIDEO for asset in game.assets)
        has_manual = any(asset.asset_type == AssetType.MANUAL for asset in game.assets)

        tags: list[str] = []
        tags.append("IMG" if has_image else "NO-IMG")
        tags.append("VID" if has_video else "NO-VID")
        tags.append("MAN" if has_manual else "NO-MAN")
        return " | ".join(tags)
