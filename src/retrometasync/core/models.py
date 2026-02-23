from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


class AssetType(str, Enum):
    BOX_FRONT = "box_front"
    BOX_BACK = "box_back"
    BOX_SPINE = "box_spine"
    DISC = "disc"
    SCREENSHOT_GAMEPLAY = "screenshot_gameplay"
    SCREENSHOT_TITLE = "screenshot_title"
    SCREENSHOT_MENU = "screenshot_menu"
    MARQUEE = "marquee"
    WHEEL = "wheel"
    LOGO = "logo"
    FANART = "fanart"
    BACKGROUND = "background"
    MIXIMAGE = "miximage"
    VIDEO = "video"
    MANUAL = "manual"
    BEZEL = "bezel"
    OVERLAY_CFG = "overlay_cfg"


class MetadataSource(str, Enum):
    NONE = "none"
    GAMELIST_XML = "gamelist_xml"
    LAUNCHBOX_XML = "launchbox_xml"
    LAUNCHBOX_SQLITE = "launchbox_sqlite"
    ROMLIST_TXT = "romlist_txt"
    METADATA_PEGASUS = "metadata_pegasus"
    RETROARCH_LPL = "retroarch_lpl"
    MIYOO_GAMELIST = "miyoogamelist"
    DAT_XML = "dat_xml"


class AssetVerificationState(str, Enum):
    UNCHECKED = "unchecked"
    VERIFIED_EXISTS = "verified_exists"
    VERIFIED_MISSING = "verified_missing"


@dataclass(slots=True)
class Asset:
    asset_type: AssetType
    file_path: Path
    format: str | None = None
    match_key: str | None = None
    verification_state: AssetVerificationState = AssetVerificationState.UNCHECKED


@dataclass(slots=True)
class Game:
    rom_path: Path
    system_id: str
    title: str
    sort_title: str | None = None
    regions: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    release_date: datetime | None = None
    genres: list[str] = field(default_factory=list)
    developer: str | None = None
    publisher: str | None = None
    rating: float | None = None
    favorite: bool = False
    hidden: bool = False
    players: str | None = None
    playcount: int | None = None
    last_played: datetime | None = None
    description: str | None = None
    assets: list[Asset] = field(default_factory=list)
    crc: str | None = None
    sha1: str | None = None

    @property
    def rom_filename(self) -> str:
        return self.rom_path.name

    @property
    def rom_basename(self) -> str:
        return self.rom_path.stem


@dataclass(slots=True)
class System:
    system_id: str
    display_name: str
    rom_root: Path
    asset_roots: dict[AssetType, Path] = field(default_factory=dict)
    metadata_source: MetadataSource = MetadataSource.NONE
    metadata_paths: list[Path] = field(default_factory=list)
    detected_ecosystem: str | None = None


@dataclass(slots=True)
class Library:
    source_root: Path
    systems: dict[str, System] = field(default_factory=dict)
    games_by_system: dict[str, list[Game]] = field(default_factory=dict)
    detected_ecosystem: str | None = None
    confidence: float | None = None
