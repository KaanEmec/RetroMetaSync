"""Performance constants and helpers for virtualized table rendering.

Used by game list and library dashboard to avoid UI freezes when
displaying large datasets (100k+ rows). Provides batch sizes,
debounce intervals, and chunked insert utilities.
"""
from __future__ import annotations

import sys

# Rows to insert per UI tick when populating Treeview (keeps frame time low).
BATCH_INSERT_SIZE = 1000

# Debounce delay (ms) for filter changes so rapid clicks don't trigger repeated rebuilds.
FILTER_DEBOUNCE_MS = 120

# Max length for display strings to avoid overly wide columns; truncate with suffix.
MAX_COLUMN_TEXT_LEN = 200

# Suffix when text is truncated.
TRUNCATE_SUFFIX = "…"


def normalize_row_text(value: str, max_len: int | None = None) -> str:
    """Normalize text for Treeview: strip, replace newlines, optionally truncate."""
    out = (value or "").strip().replace("\r", "").replace("\n", " ")
    if max_len is not None and len(out) > max_len:
        out = out[: max_len - len(TRUNCATE_SUFFIX)] + TRUNCATE_SUFFIX
    return out


def chunked_range(total: int, chunk_size: int):
    """Yield (start, end) slices for iterating in chunks. end is min(start+chunk_size, total)."""
    start = 0
    while start < total:
        end = min(start + chunk_size, total)
        yield start, end
        start = end


def get_dpi_scale(widget) -> float:
    """Scale factor from 96 DPI (1.0). Use for font size and row height on high-DPI / scaled displays."""
    try:
        root = widget.winfo_toplevel()
        pixels_per_inch = root.winfo_fpixels("1i")
        scale = max(1.0, pixels_per_inch / 96.0)
        # On some Windows/Tk setups this reports 96 DPI even with OS scaling.
        if sys.platform == "win32" and scale <= 1.01:
            try:
                import ctypes

                dpi = ctypes.windll.user32.GetDpiForSystem()
                scale = max(scale, dpi / 96.0)
            except Exception:
                pass
        return scale
    except Exception:
        return 1.0


# Base font size and row height. Use larger base so readable at 96 DPI (e.g. on 4K with scaling).
# get_dpi_scale() may still report 1.0 on some Windows setups; larger base avoids tiny text.
BASE_TABLE_FONT_SIZE = 14
BASE_TABLE_ROW_HEIGHT = 34
MIN_TABLE_ROW_HEIGHT = 28
MAX_TABLE_ROW_HEIGHT = 56
MIN_TABLE_FONT_SIZE = 13
MAX_TABLE_FONT_SIZE = 22
