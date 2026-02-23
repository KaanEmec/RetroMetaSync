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

    def log(self, message: str) -> None:
        self.textbox.configure(state="normal")
        self.textbox.insert("end", f"{message}\n")
        self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def clear(self) -> None:
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.configure(state="disabled")
