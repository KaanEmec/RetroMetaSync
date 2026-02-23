from __future__ import annotations

import tkinter as tk

import customtkinter as ctk


class SystemMappingDialog(ctk.CTkToplevel):
    """Modal dialog to map source systems to destination system folders."""

    def __init__(
        self,
        master,
        source_systems: list[str],
        destination_systems: list[str],
        suggested_mapping: dict[str, str],
    ) -> None:
        super().__init__(master)
        self.title("System Folder Mapping")
        self.geometry("760x560")
        self.minsize(680, 460)
        self.transient(master)
        self.grab_set()
        self._result: dict[str, str] | None = None
        self._source_systems = list(source_systems)
        self._entries: dict[str, ctk.CTkEntry] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        title = ctk.CTkLabel(
            self,
            text="Map Source Systems To Existing Destination Folders",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        )
        title.grid(row=0, column=0, padx=14, pady=(12, 4), sticky="ew")

        guidance = (
            "Enter destination folder names per source system.\n"
            "Leave a field empty to keep/use the source system folder name."
        )
        guidance_label = ctk.CTkLabel(self, text=guidance, justify="left", anchor="w")
        guidance_label.grid(row=1, column=0, padx=14, pady=(0, 10), sticky="ew")

        body = ctk.CTkScrollableFrame(self)
        body.grid(row=2, column=0, padx=14, pady=(0, 10), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        existing_hint = ", ".join(destination_systems) if destination_systems else "(none found)"
        hint = ctk.CTkLabel(body, text=f"Detected destination systems: {existing_hint}", anchor="w", justify="left")
        hint.grid(row=0, column=0, columnspan=2, padx=8, pady=(4, 10), sticky="ew")

        for idx, source_system in enumerate(self._source_systems, start=1):
            src_label = ctk.CTkLabel(body, text=source_system, anchor="w")
            src_label.grid(row=idx, column=0, padx=(8, 8), pady=4, sticky="ew")
            entry = ctk.CTkEntry(body, placeholder_text="Destination system folder name")
            entry.grid(row=idx, column=1, padx=(0, 8), pady=4, sticky="ew")
            suggestion = suggested_mapping.get(source_system, "")
            if suggestion:
                entry.insert(0, suggestion)
            self._entries[source_system] = entry

        button_bar = ctk.CTkFrame(self, fg_color="transparent")
        button_bar.grid(row=3, column=0, padx=14, pady=(2, 12), sticky="ew")
        button_bar.grid_columnconfigure(0, weight=1)
        cancel_btn = ctk.CTkButton(button_bar, text="Cancel", width=110, command=self._cancel)
        cancel_btn.grid(row=0, column=1, padx=(0, 8), sticky="e")
        confirm_btn = ctk.CTkButton(button_bar, text="Use Mapping", width=130, command=self._confirm)
        confirm_btn.grid(row=0, column=2, sticky="e")

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.after(0, lambda: self.focus_force())

    def _confirm(self) -> None:
        mapping: dict[str, str] = {}
        for source_system in self._source_systems:
            raw_value = self._entries[source_system].get().strip()
            mapping[source_system] = raw_value or source_system
        self._result = mapping
        self.destroy()

    def _cancel(self) -> None:
        self._result = None
        self.destroy()

    def wait_for_result(self) -> dict[str, str] | None:
        self.wait_window(self)
        return self._result


def show_system_mapping_dialog(
    master,
    source_systems: list[str],
    destination_systems: list[str],
    suggested_mapping: dict[str, str],
) -> dict[str, str] | None:
    dialog = SystemMappingDialog(
        master=master,
        source_systems=source_systems,
        destination_systems=destination_systems,
        suggested_mapping=suggested_mapping,
    )
    return dialog.wait_for_result()
