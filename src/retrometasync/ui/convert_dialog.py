from __future__ import annotations

import customtkinter as ctk
import tkinter.filedialog as filedialog


TARGET_ECOSYSTEM_OPTIONS = ["batocera", "es_de", "launchbox", "retrobat", "es_classic"]


class ConvertPane(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._on_convert = None
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)

        self.title_label = ctk.CTkLabel(self, text="Conversion", font=ctk.CTkFont(size=14, weight="bold"))
        self.title_label.grid(row=0, column=0, columnspan=3, padx=10, pady=(10, 8), sticky="w")

        self.target_label = ctk.CTkLabel(self, text="Target Ecosystem")
        self.target_label.grid(row=1, column=0, padx=(10, 6), pady=4, sticky="w")

        self.target_option = ctk.CTkOptionMenu(
            self, values=TARGET_ECOSYSTEM_OPTIONS
        )
        self.target_option.grid(row=1, column=1, columnspan=2, padx=(0, 10), pady=4, sticky="ew")

        self.output_label = ctk.CTkLabel(self, text="Output Path")
        self.output_label.grid(row=2, column=0, padx=(10, 6), pady=4, sticky="w")

        self.output_entry = ctk.CTkEntry(self, placeholder_text="Choose conversion output root")
        self.output_entry.grid(row=2, column=1, padx=(0, 10), pady=4, sticky="ew")

        self.output_browse = ctk.CTkButton(self, text="Browse", width=80, command=self._browse_output)
        self.output_browse.grid(row=2, column=2, padx=(0, 10), pady=4, sticky="e")

        self.dry_run_var = ctk.BooleanVar(value=False)
        self.dry_run_check = ctk.CTkCheckBox(self, text="Dry Run (no file writes)", variable=self.dry_run_var)
        self.dry_run_check.grid(row=3, column=0, columnspan=2, padx=10, pady=(4, 2), sticky="w")

        self.overwrite_var = ctk.BooleanVar(value=False)
        self.overwrite_check = ctk.CTkCheckBox(self, text="Overwrite Existing Files", variable=self.overwrite_var)
        self.overwrite_check.grid(row=4, column=0, columnspan=2, padx=10, pady=(0, 6), sticky="w")

        self.export_dat_var = ctk.BooleanVar(value=False)
        self.export_dat_check = ctk.CTkCheckBox(self, text="Export DAT files", variable=self.export_dat_var)
        self.export_dat_check.grid(row=5, column=0, columnspan=2, padx=10, pady=(0, 6), sticky="w")

        self.convert_button = ctk.CTkButton(self, text="Start Conversion", state="disabled", command=self._handle_convert)
        self.convert_button.grid(row=6, column=0, columnspan=3, padx=10, pady=(4, 10), sticky="ew")

    def set_on_convert(self, callback) -> None:
        self._on_convert = callback

    def get_target(self) -> str:
        return self.target_option.get()

    def get_output_path(self) -> str:
        return self.output_entry.get().strip()

    def set_enabled(self, enabled: bool) -> None:
        self.convert_button.configure(state="normal" if enabled else "disabled")

    def is_dry_run(self) -> bool:
        return bool(self.dry_run_var.get())

    def should_overwrite_existing(self) -> bool:
        return bool(self.overwrite_var.get())

    def should_export_dat(self) -> bool:
        return bool(self.export_dat_var.get())

    def set_busy(self, busy: bool) -> None:
        self.convert_button.configure(text="Converting..." if busy else "Start Conversion")
        self.convert_button.configure(state="disabled" if busy else "normal")
        self.output_browse.configure(state="disabled" if busy else "normal")
        self.target_option.configure(state="disabled" if busy else "normal")
        self.output_entry.configure(state="disabled" if busy else "normal")
        self.dry_run_check.configure(state="disabled" if busy else "normal")
        self.overwrite_check.configure(state="disabled" if busy else "normal")
        self.export_dat_check.configure(state="disabled" if busy else "normal")

    def _browse_output(self) -> None:
        selected = filedialog.askdirectory()
        if selected:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, selected)

    def _handle_convert(self) -> None:
        if self._on_convert is not None:
            self._on_convert()
