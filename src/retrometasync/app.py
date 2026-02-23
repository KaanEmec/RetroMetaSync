from __future__ import annotations

import sys

import customtkinter as ctk

from retrometasync.ui.main_window import MainWindow


def _set_windows_dpi_aware() -> None:
    """Make the process DPI-aware on Windows so Tk reports correct scale (e.g. 4K + scaling)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        # Per-monitor DPI awareness v2 so winfo_fpixels('1i') reflects actual scaling.
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)  # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
        except Exception:
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_DPI_AWARENESS.Process_Per_Monitor_DPI_Aware
            except Exception:
                ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def main() -> None:
    _set_windows_dpi_aware()
    ctk.set_appearance_mode("dark")
    # The default blue theme gives stronger contrast for buttons/controls.
    ctk.set_default_color_theme("blue")

    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
