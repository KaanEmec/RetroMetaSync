from __future__ import annotations

import customtkinter as ctk


class ProgressLog(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.title_label = ctk.CTkLabel(self, text="Progress Log", font=ctk.CTkFont(size=14, weight="bold"))
        self.title_label.grid(row=0, column=0, padx=10, pady=(10, 4), sticky="w")

        self.textbox = ctk.CTkTextbox(self, wrap="word")
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
