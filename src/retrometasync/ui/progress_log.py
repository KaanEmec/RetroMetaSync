from __future__ import annotations

import customtkinter as ctk


class ProgressLog(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(border_width=1, border_color=("#cfd4dc", "#2f3745"))

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.title_label = ctk.CTkLabel(
            self,
            text="🧾 Progress Log",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=("#0f172a", "#f8fafc"),
        )
        self.title_label.grid(row=0, column=0, padx=10, pady=(10, 4), sticky="w")

        self.textbox = ctk.CTkTextbox(
            self,
            wrap="word",
            fg_color=("#f8fafc", "#0b1220"),
            text_color=("#0b1324", "#e5edf7"),
            border_width=1,
            border_color=("#d7dde7", "#344056"),
        )
        self.textbox.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.textbox.configure(state="disabled")
        self._pending_lines: list[str] = []
        self._flush_after_id: str | None = None
        self._flush_interval_ms = 150

    def log(self, message: str) -> None:
        self._pending_lines.append(message)
        if self._flush_after_id is None:
            self._flush_after_id = self.after(self._flush_interval_ms, self._flush_pending)

    def _flush_pending(self) -> None:
        self._flush_after_id = None
        if not self._pending_lines:
            return
        joined = "\n".join(self._pending_lines) + "\n"
        self._pending_lines.clear()
        self.textbox.configure(state="normal")
        self.textbox.insert("end", joined)
        self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def clear(self) -> None:
        if self._flush_after_id is not None:
            self.after_cancel(self._flush_after_id)
            self._flush_after_id = None
        self._pending_lines.clear()
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.configure(state="disabled")
