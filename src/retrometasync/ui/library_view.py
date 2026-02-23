from __future__ import annotations

import customtkinter as ctk

from retrometasync.core.models import AssetType, Library


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


class LibraryView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(self, text="Library Dashboard", font=ctk.CTkFont(size=16, weight="bold"))
        self.title_label.grid(row=0, column=0, padx=10, pady=(10, 4), sticky="w")

        self.summary_label = ctk.CTkLabel(
            self, text="No library analyzed yet.", text_color=("gray45", "gray70"), anchor="w"
        )
        self.summary_label.grid(row=1, column=0, padx=10, pady=(0, 8), sticky="ew")

        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew")
        for column in range(5):
            self.scroll.grid_columnconfigure(column, weight=1)

    def set_library(self, library: Library) -> None:
        self._clear_rows()
        systems = sorted(library.systems.values(), key=lambda item: item.system_id)

        self.summary_label.configure(
            text=(
                f"Ecosystem: {library.detected_ecosystem or 'unknown'}"
                f" | Confidence: {library.confidence if library.confidence is not None else 'n/a'}"
                f" | Systems: {len(systems)}"
            )
        )

        self._add_header_row()
        for row_idx, system in enumerate(systems, start=1):
            games = library.games_by_system.get(system.system_id, [])
            rom_count = len(games)
            image_count = 0
            video_count = 0
            manual_count = 0

            for game in games:
                has_image = any(asset.asset_type in _IMAGE_LIKE_ASSET_TYPES for asset in game.assets)
                has_video = any(asset.asset_type == AssetType.VIDEO for asset in game.assets)
                has_manual = any(asset.asset_type == AssetType.MANUAL for asset in game.assets)
                image_count += int(has_image)
                video_count += int(has_video)
                manual_count += int(has_manual)

            values = (system.display_name, str(rom_count), str(image_count), str(video_count), str(manual_count))
            for col, value in enumerate(values):
                label = ctk.CTkLabel(self.scroll, text=value, anchor="w")
                label.grid(row=row_idx, column=col, padx=6, pady=3, sticky="ew")

    def reset(self) -> None:
        self._clear_rows()
        self.summary_label.configure(text="No library analyzed yet.")

    def _add_header_row(self) -> None:
        headers = ("System", "ROMs", "With Images", "With Videos", "With Manuals")
        for col, header in enumerate(headers):
            label = ctk.CTkLabel(self.scroll, text=header, font=ctk.CTkFont(weight="bold"), anchor="w")
            label.grid(row=0, column=col, padx=6, pady=(0, 6), sticky="ew")

    def _clear_rows(self) -> None:
        for child in self.scroll.winfo_children():
            child.destroy()
