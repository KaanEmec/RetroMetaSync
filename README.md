<p align="center">
  <strong>RetroMetaSync</strong>
</p>
<p align="center">
  <em>Analyze, convert, and migrate retro gaming libraries between frontend ecosystems</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776ab?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-333333?style=flat-square" alt="Cross-platform">
  <img src="https://img.shields.io/badge/UI-CustomTkinter-1f2937?style=flat-square" alt="CustomTkinter">
</p>

---

## What is RetroMetaSync?

**RetroMetaSync** is a desktop application that lets you **analyze**, **convert**, and **migrate** your retro gaming libraries—ROMs, box art, videos, manuals, and metadata—between different frontend ecosystems. Whether you're moving from LaunchBox to Batocera, from ES-DE to RetroBat, or syncing libraries across devices, RetroMetaSync handles the format translation and file organization for you.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SOURCE LIBRARY                    RETROMETASYNC                    TARGET  │
│  (any supported ecosystem)          ────────────────                 (your   │
│                                    • Detect ecosystem                choice) │
│  📁 LaunchBox / ES-DE / Batocera    • Parse metadata                          │
│  📁 RetroBat / RetroArch / etc.     • Normalize to internal model              │
│                                    • Map systems & assets                     │
│  📄 gamelist.xml / Platforms/*.xml  • Convert & write output                  │
│  🖼 Images, videos, manuals         • Merge or overwrite                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Features

### Core capabilities

| Feature | Description |
|--------|-------------|
| **Auto-detection** | Automatically detects your library ecosystem (LaunchBox, ES-DE, Batocera, RetroBat, etc.) using signature files and folder structure |
| **Manual override** | Force a specific source format when auto-detection is uncertain |
| **Multi-ecosystem conversion** | Convert from any supported source to Batocera, ES-DE, LaunchBox, RetroBat, or ES Classic |
| **Selective conversion** | Choose which games and systems to convert—no need to migrate everything at once |
| **System mapping** | Map source platform IDs to target platform IDs (e.g. `snes` → `Super Nintendo Entertainment System`) with suggestions and persistence |
| **Duplicate conflict resolution** | Detect and resolve duplicate games before conversion with an interactive dialog |
| **Metadata merge** | Optionally merge new entries into existing gamelists/metadata files at the destination |
| **Asset verification** | Check whether box art, videos, and manuals exist on disk; verify unchecked assets in bulk for the visible list |
| **Dry run** | Preview conversion without writing files |
| **DAT export** | Export DAT files for ROM set verification (ClrMamePro, RomCenter, etc.) |

### Supported asset types

The app normalizes and converts a wide range of media:

| Category | Asset types |
|----------|-------------|
| **Box art** | Box front, box back, box spine, disc |
| **Screenshots** | Gameplay, title screen, menu |
| **Marquee / wheel** | Marquee, wheel, logo |
| **Background** | Fanart, background, miximage |
| **Media** | Video (gameplay preview), manual (PDF) |
| **Overlays** | Bezel, overlay config |

### Supported ecosystems

#### Source (detection & loading)

| Ecosystem | Detection | Metadata format |
|-----------|-----------|-----------------|
| **LaunchBox** | `LaunchBox/Data/Platforms`, `LaunchBox/Images` | XML, SQLite |
| **ES-DE** | `ES-DE/gamelists`, `ES-DE/downloaded_media` | gamelist.xml |
| **ES Family** (Batocera, RetroPie, AmberELEC, JELOS, ArkOS, KNULLI) | `gamelist.xml`, `userdata/roms` | gamelist.xml |
| **RetroBat** | `retrobat.ini`, `roms` | gamelist.xml |
| **RetroArch** | `*.lpl`, `thumbnails` | Playlist (.lpl) |
| **OnionOS** (Miyoo Mini) | `Roms`, `miyoogamelist.xml`, `Imgs` | miyoogamelist.xml |
| **muOS** | `MUOS/info/catalogue` | Filename-based |
| **Attract-Mode** | `attract.cfg`, `romlists` | Romlist (.txt) |
| **Pegasus** | `metadata.pegasus.txt` | metadata.pegasus.txt |

#### Target (conversion output)

| Ecosystem | Output structure |
|-----------|------------------|
| **Batocera** | `userdata/roms/<system>/` with gamelist.xml, images/, videos/, manuals/ |
| **ES-DE** | `ES-DE/gamelists`, `ES-DE/downloaded_media/<system>/<type>/` |
| **ES Classic** | `.emulationstation/gamelists`, `.emulationstation/downloaded_*` |
| **LaunchBox** | `LaunchBox/Data/Platforms`, `LaunchBox/Images` |
| **RetroBat** | `roms/<system>/` with gamelist.xml and media folders |

---

## User interface

### Layout

- **Source controls** — Browse for library folder, analyze, and choose source mode (Auto Detect or specific ecosystem)
- **Library dashboard** — Summary of detected ecosystem, confidence, and per-system counts (ROMs, images, videos, manuals) in a sortable table
- **Game list** — Filterable, multi-select table with:
  - System, title, ROM filename
  - Rating, genre, year
  - Asset status (image, video, manual) with verification states (has / missing / unchecked)
  - Checkboxes for inclusion in conversion
  - Button to verify unchecked assets for the visible list
- **Conversion pane** — Target ecosystem, output path, options (dry run, overwrite, export DAT, merge metadata), and Start Conversion
- **Progress log** — Live log of analysis, conversion, and asset verification

### Visual design

- **Dark theme** by default
- **DPI-aware** on Windows for correct scaling on 4K and high-DPI displays
- **Responsive tables** with virtualized rendering for large libraries

---

## Quick start

### Requirements

- **Python 3.10+**
- **CustomTkinter** (≥ 5.2.2)

### Installation

```bash
# Clone or download the project
cd RetroMetaSync

# Create a virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate   # Linux/macOS

# Install dependencies
pip install -r requirements.txt
```

### Run the app

**Windows (batch):**
```batch
run_app.bat
```

**Or run directly:**
```bash
set PYTHONPATH=src
python -m retrometasync.app
```

### Basic workflow

1. **Select source folder** — Point to your library root (e.g. LaunchBox folder, ES-DE config directory, Batocera `userdata`, etc.)
2. **Analyze** — Click **Analyze Library**; the app detects the ecosystem and loads metadata
3. **Review** — Check the Library Dashboard and Game List; filter and select games to convert
4. **Configure conversion** — Choose target ecosystem (Batocera, ES-DE, LaunchBox, RetroBat, ES Classic), output path, and options
5. **Convert** — Click **Start Conversion**; resolve system mapping and duplicate conflicts if prompted

---

## Project structure

```
RetroMetaSync/
├── README.md
├── requirements.txt
├── run_app.bat
├── Backlog.txt
├── Retro Library Structures & Metadata Interop Reference.md
├── Retro Library Structure Detection Guide.md
├── src/
│   └── retrometasync/
│       ├── __init__.py
│       ├── app.py                    # Entry point, DPI setup, theme
│       ├── config/
│       │   ├── __init__.py
│       │   └── ecosystems.py         # Ecosystem IDs, signatures, asset mappings
│       ├── core/
│       │   ├── __init__.py
│       │   ├── models.py             # Game, System, Library, Asset, AssetType
│       │   ├── detection.py          # Library ecosystem detection
│       │   ├── normalizer.py         # Load metadata, build Library
│       │   ├── asset_verifier.py     # Verify asset files on disk
│       │   ├── loaders/
│       │   │   ├── base.py
│       │   │   ├── es_gamelist.py    # ES-family gamelist.xml
│       │   │   ├── launchbox_xml.py  # LaunchBox platform XML
│       │   │   └── launchbox_sqlite.py
│       │   └── conversion/
│       │       ├── engine.py         # Conversion orchestrator
│       │       ├── targets/          # Batocera, ES-DE, LaunchBox, RetroBat, ES Classic
│       │       └── writers/          # gamelist_xml, launchbox_xml, dat_writer
│       └── ui/
│           ├── main_window.py       # Main window, threading, queue polling
│           ├── library_view.py       # Library dashboard Treeview
│           ├── game_list.py          # Game list pane, filters, selection
│           ├── convert_dialog.py     # Conversion options pane
│           ├── progress_log.py       # Progress log widget
│           ├── system_mapping_dialog.py
│           ├── duplicate_conflict_dialog.py
│           └── table_perf.py         # DPI scaling, table constants
└── tests/
    ├── test_detection.py
    ├── test_es_gamelist_loader.py
    ├── test_launchbox_loader.py
    ├── test_conversion_engine.py
    ├── test_asset_verifier.py
    └── test_game_list_ui.py
```

---

## Tech stack

| Layer | Technology |
|-------|------------|
| **Language** | Python 3.10+ |
| **UI** | CustomTkinter (modern, themed desktop UI) |
| **File I/O** | `pathlib`, `shutil` |
| **XML** | `xml.etree.ElementTree` (stdlib) |
| **Database** | `sqlite3` (stdlib) for LaunchBox SQLite support |
| **Threading** | Background workers for analysis/conversion; main thread for UI updates |

---

## Planned improvements (backlog)

- **Gamelist/data merge** — Automatically add new entries to existing gamelists in the target folder
- **Extra columns** — Rating, genre, year in game list (with horizontal scroll if needed)
- **Improved checkboxes** — Bigger, clearer selection controls in the game list
- **Bulk asset check** — Button to verify all unchecked assets for the visible (filtered) list

---

## Reference documentation

- **Retro Library Structures & Metadata Interop Reference.md** — Detailed specification of how each ecosystem stores ROMs, metadata, and media; conversion cookbook; mapping tables; validation checklist
- **Retro Library Structure Detection Guide.md** — Detection rules and fingerprinting

---

## License

See project repository for license information.
