# RetroMetaSync

RetroMetaSync is a Python desktop application for analyzing, converting, and migrating retro gaming libraries (ROMs, images, videos, manuals, and metadata) between frontend ecosystems such as Batocera, LaunchBox, RetroPie, and ES-DE.

## Current Status

Project is in active implementation following an approved phase-based plan.

- Phase 1: project scaffold and data model (in progress/completed in this commit set)
- Phase 2+: detection, loaders, UI, conversion engine, and validation

## Tech Stack

- Python 3.10+
- CustomTkinter for modern desktop UI
- pathlib and shutil for filesystem operations
- xml.etree.ElementTree (stdlib) for XML metadata handling
- Optional lxml support may be added later if needed

## Planned Project Layout

```text
RetroMetaSync/
  README.md
  requirements.txt
  src/
    retrometasync/
      __init__.py
      core/
        __init__.py
        models.py
      config/
        __init__.py
        ecosystems.py
```

## Next Milestones

1. Implement detection engine using ecosystem fingerprint rules.
2. Build loaders/parsers for ES-family and LaunchBox metadata formats.
3. Build CustomTkinter UI dashboard and multi-selection game list.
4. Implement threaded conversion engine and live progress logging.
