from __future__ import annotations

import customtkinter as ctk

from retrometasync.core.conversion import DuplicateConflict


class DuplicateConflictDialog(ctk.CTkToplevel):
    """Modal per-conflict chooser for keep-new/keep-existing decisions."""

    def __init__(self, master, conflicts: list[DuplicateConflict]) -> None:
        super().__init__(master)
        self.title("Duplicate Game Conflict Resolution")
        self.geometry("840x520")
        self.minsize(760, 460)
        self.transient(master)
        self.grab_set()
        self._conflicts = list(conflicts)
        self._result: dict[str, str] | None = None
        self._decisions: dict[str, str] = {}
        self._index = 0

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._header_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=20, weight="bold"),
            anchor="w",
        )
        self._header_label.grid(row=0, column=0, padx=14, pady=(12, 8), sticky="ew")

        self._content_frame = ctk.CTkFrame(self)
        self._content_frame.grid(row=1, column=0, padx=14, pady=(0, 8), sticky="nsew")
        self._content_frame.grid_columnconfigure(0, weight=1)
        self._content_frame.grid_rowconfigure(1, weight=1)

        self._summary_label = ctk.CTkLabel(
            self._content_frame,
            text="",
            font=ctk.CTkFont(size=16, weight="bold"),
            justify="left",
            anchor="w",
        )
        self._summary_label.grid(row=0, column=0, padx=12, pady=(12, 8), sticky="ew")

        self._details_box = ctk.CTkTextbox(
            self._content_frame,
            wrap="word",
            font=ctk.CTkFont(size=15),
            height=210,
            border_width=1,
        )
        self._details_box.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="nsew")
        self._details_box.configure(state="disabled")

        self.apply_all_var = ctk.BooleanVar(value=False)
        self.apply_all_checkbox = ctk.CTkCheckBox(
            self._content_frame,
            text="Apply this choice to all remaining conflicts",
            variable=self.apply_all_var,
            font=ctk.CTkFont(size=14),
        )
        self.apply_all_checkbox.grid(row=2, column=0, padx=12, pady=(0, 12), sticky="w")

        self._button_bar = ctk.CTkFrame(self, fg_color="transparent")
        self._button_bar.grid(row=2, column=0, padx=14, pady=(2, 12), sticky="ew")
        self._button_bar.grid_columnconfigure(0, weight=1)
        self._cancel_btn = ctk.CTkButton(self._button_bar, text="Cancel Conversion", width=130, command=self._cancel)
        self._cancel_btn.grid(row=0, column=1, padx=(0, 8), sticky="e")
        self._keep_existing_btn = ctk.CTkButton(
            self._button_bar,
            text="Keep Existing",
            width=120,
            command=lambda: self._choose("keep_existing"),
        )
        self._keep_existing_btn.grid(row=0, column=2, padx=(0, 8), sticky="e")
        self._keep_new_btn = ctk.CTkButton(
            self._button_bar,
            text="Keep New",
            width=110,
            command=lambda: self._choose("keep_new"),
        )
        self._keep_new_btn.grid(row=0, column=3, sticky="e")

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self._render_current()

    def _render_current(self) -> None:
        conflict = self._conflicts[self._index]
        current = self._index + 1
        total = len(self._conflicts)
        self._header_label.configure(text=f"Conflict {current}/{total}")
        self._summary_label.configure(
            text=(
                "A matching game already exists in destination metadata.\n"
                "Choose which entry should be kept."
            )
        )
        details = (
            "Destination\n"
            f"  System: {conflict.destination_system}\n"
            f"  Metadata file: {conflict.metadata_path}\n\n"
            "Incoming (new)\n"
            f"  Title: {conflict.game_title or '(no title)'}\n"
            f"  ROM: {conflict.rom_filename}\n\n"
            "Existing\n"
            f"  Title: {conflict.existing_title or '(no title)'}\n\n"
            "Actions\n"
            "  Keep New: write new files/metadata and replace the matching existing metadata entry.\n"
            "  Keep Existing: skip this incoming game and preserve destination files/metadata."
        )
        self._details_box.configure(state="normal")
        self._details_box.delete("1.0", "end")
        self._details_box.insert("1.0", details)
        self._details_box.configure(state="disabled")

    def _choose(self, action: str) -> None:
        conflict = self._conflicts[self._index]
        self._decisions[conflict.key] = action
        if self.apply_all_var.get():
            for remaining in self._conflicts[self._index + 1 :]:
                self._decisions[remaining.key] = action
            self._result = dict(self._decisions)
            self.destroy()
            return
        self._index += 1
        if self._index >= len(self._conflicts):
            self._result = dict(self._decisions)
            self.destroy()
            return
        self._render_current()

    def _cancel(self) -> None:
        self._result = None
        self.destroy()

    def wait_for_result(self) -> dict[str, str] | None:
        self.wait_window(self)
        return self._result


def show_duplicate_conflict_dialog(master, conflicts: list[DuplicateConflict]) -> dict[str, str] | None:
    dialog = DuplicateConflictDialog(master=master, conflicts=conflicts)
    return dialog.wait_for_result()
