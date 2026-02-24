from __future__ import annotations

from retrometasync.core.models import AssetType


# Canonical ecosystem IDs used throughout the app.
ECOSYSTEMS: tuple[str, ...] = (
    "es_classic",
    "batocera",
    "knulli",
    "amberelec",
    "jelos_rocknix",
    "arkos",
    "onionos",
    "muos",
    "es_de",
    "emudeck",
    "retrodeck",
    "retrobat",
    "launchbox",
    "attract_mode",
    "pegasus",
    "retroarch",
)


# Signature paths/files used by detection scoring.
SIGNATURE_HINTS: dict[str, tuple[str, ...]] = {
    "retroarch": ("*.lpl", "thumbnails"),
    "pegasus": ("metadata.pegasus.txt",),
    "attract_mode": ("attract.cfg", "romlists"),
    "launchbox": ("LaunchBox/Data/Platforms", "LaunchBox/Images"),
    "es_de": ("ES-DE/gamelists", "ES-DE/downloaded_media"),
    "retrobat": ("retrobat.ini", "roms"),
    "onionos": ("Roms", "miyoogamelist.xml", "Imgs"),
    "muos": ("MUOS/info/catalogue",),
    "batocera": ("userdata/roms", "gamelist.xml"),
    "es_classic": (".emulationstation/gamelists", ".emulationstation/es_systems.cfg"),
}


# ES-family XML tag to normalized asset type.
ES_FAMILY_TAG_TO_ASSET_TYPE: dict[str, AssetType] = {
    "image": AssetType.BOX_FRONT,
    "thumbnail": AssetType.SCREENSHOT_GAMEPLAY,
    "fanart": AssetType.FANART,
    "marquee": AssetType.MARQUEE,
    "video": AssetType.VIDEO,
    "manual": AssetType.MANUAL,
    "bezel": AssetType.BEZEL,
}


# Batocera suffix style mapping from reference.
BATOCERA_SUFFIX_TO_ASSET_TYPE: dict[str, AssetType] = {
    "-image": AssetType.BOX_FRONT,
    "-thumb": AssetType.SCREENSHOT_GAMEPLAY,
    "-marquee": AssetType.MARQUEE,
    "-video": AssetType.VIDEO,
    "-bezel": AssetType.BEZEL,
}


# ES-DE downloaded_media folder mapping to normalized asset types.
ES_DE_MEDIA_FOLDER_TO_ASSET_TYPE: dict[str, AssetType] = {
    "covers": AssetType.BOX_FRONT,
    "backcovers": AssetType.BOX_BACK,
    "3dboxes": AssetType.BOX_FRONT,
    "screenshots": AssetType.SCREENSHOT_GAMEPLAY,
    "titlescreens": AssetType.SCREENSHOT_TITLE,
    "marquees": AssetType.MARQUEE,
    "fanart": AssetType.FANART,
    "videos": AssetType.VIDEO,
    "manuals": AssetType.MANUAL,
    "miximages": AssetType.MIXIMAGE,
}


# RetroArch thumbnails folder mapping.
RETROARCH_THUMBNAIL_FOLDER_TO_ASSET_TYPE: dict[str, AssetType] = {
    "Named_Boxarts": AssetType.BOX_FRONT,
    "Named_Snaps": AssetType.SCREENSHOT_GAMEPLAY,
    "Named_Titles": AssetType.SCREENSHOT_TITLE,
}


# muOS catalogue mapping.
MUOS_FOLDER_TO_ASSET_TYPE: dict[str, AssetType] = {
    "box": AssetType.BOX_FRONT,
    "preview": AssetType.SCREENSHOT_GAMEPLAY,
}


# Conversion-time fallback media roots by ecosystem and output slot key.
ECOSYSTEM_MEDIA_FALLBACK_FOLDERS: dict[str, dict[str, tuple[str, ...]]] = {
    "es_family": {
        "image": ("images", "downloaded_images", "covers", "boxart"),
        "thumbnail": ("images", "screenshots", "snaps"),
        "marquee": ("images", "marquees", "wheel"),
        "fanart": ("images", "fanart"),
        "video": ("videos", "downloaded_videos"),
        "manual": ("manuals",),
    },
    "es_de": {
        "image": ("ES-DE/downloaded_media/{system}/covers", "ES-DE/downloaded_media/{system}/3dboxes"),
        "thumbnail": ("ES-DE/downloaded_media/{system}/screenshots", "ES-DE/downloaded_media/{system}/titlescreens"),
        "image_3dbox": ("ES-DE/downloaded_media/{system}/3dboxes",),
        "image_back": ("ES-DE/downloaded_media/{system}/backcovers",),
        "image_miximage": ("ES-DE/downloaded_media/{system}/miximages",),
        "thumbnail_title": ("ES-DE/downloaded_media/{system}/titlescreens",),
        "marquee": ("ES-DE/downloaded_media/{system}/marquees",),
        "fanart": ("ES-DE/downloaded_media/{system}/fanart",),
        "video": ("ES-DE/downloaded_media/{system}/videos",),
        "manual": ("ES-DE/downloaded_media/{system}/manuals",),
    },
    "retroarch": {
        "image": ("thumbnails/{system}/Named_Boxarts",),
        "thumbnail": ("thumbnails/{system}/Named_Snaps", "thumbnails/{system}/Named_Titles"),
    },
    "onionos": {
        "image": ("Roms/{system}/Imgs", "Roms/{system}/imgs"),
        "thumbnail": ("Roms/{system}/Imgs", "Roms/{system}/imgs"),
    },
    "muos": {
        "image": ("MUOS/info/catalogue/{system}/box",),
        "thumbnail": ("MUOS/info/catalogue/{system}/preview",),
    },
}


# Candidate DAT filenames by logical metadata source key.
# The resolver searches these names under:
#  - %RETROMETASYNC_PRELOADED_METADATA_ROOT%
#  - <source_root>/.retrometasync/dats
#  - <source_root>/metadata/dats
#  - <source_root>/dats
PRELOADED_METADATA_SOURCE_CATALOG: dict[str, tuple[str, ...]] = {
    "fbneo_arcade": (
        "FinalBurn Neo (ClrMame Pro XML, Arcade only).dat",
        "fbneo_arcade.dat",
    ),
    "fbneo_neogeo": (
        "FinalBurn Neo (ClrMame Pro XML, Neogeo only).dat",
        "fbneo_neogeo.dat",
    ),
    "fbneo_nes": (
        "FinalBurn Neo (ClrMame Pro XML, NES Games only).dat",
        "fbneo_nes.dat",
    ),
    "fbneo_snes": (
        "FinalBurn Neo (ClrMame Pro XML, SNES Games only).dat",
        "fbneo_snes.dat",
    ),
    "fbneo_megadrive": (
        "FinalBurn Neo (ClrMame Pro XML, Megadrive only).dat",
        "fbneo_megadrive.dat",
    ),
    "fbneo_mastersystem": (
        "FinalBurn Neo (ClrMame Pro XML, Master System only).dat",
        "fbneo_mastersystem.dat",
    ),
    "fbneo_gamegear": (
        "FinalBurn Neo (ClrMame Pro XML, Game Gear only).dat",
        "fbneo_gamegear.dat",
    ),
    "fbneo_pcengine": (
        "FinalBurn Neo (ClrMame Pro XML, PC-Engine only).dat",
        "fbneo_pcengine.dat",
    ),
    "fbneo_tg16": (
        "FinalBurn Neo (ClrMame Pro XML, TurboGrafx16 only).dat",
        "fbneo_turbografx16.dat",
    ),
    "fbneo_colecovision": (
        "FinalBurn Neo (ClrMame Pro XML, ColecoVision only).dat",
        "fbneo_colecovision.dat",
    ),
    "fbneo_msx1": (
        "FinalBurn Neo (ClrMame Pro XML, MSX 1 Games only).dat",
        "fbneo_msx1.dat",
    ),
    "fbneo_sg1000": (
        "FinalBurn Neo (ClrMame Pro XML, Sega SG-1000 only).dat",
        "fbneo_sg1000.dat",
    ),
    "fbneo_fds": (
        "FinalBurn Neo (ClrMame Pro XML, FDS Games only).dat",
        "fbneo_fds.dat",
    ),
    "mame": ("mame.dat", "mame.xml", "mame_listxml.xml"),
    "no_intro_generic": ("no-intro.dat", "no_intro.dat"),
    "no_intro_n64": ("Nintendo - Nintendo 64.dat",),
    "redump_gamecube": ("Nintendo - GameCube.dat",),
    "no_intro_psp": ("Sony - PlayStation Portable.dat",),
    "redump_psp": ("Sony - PlayStation Portable.dat",),
    "redump_segacd": ("Sega - Mega-CD - Sega CD.dat", "Sega - Sega CD.dat"),
    "redump_amigacd32": ("Commodore - CD32.dat", "Commodore - Amiga CD32.dat"),
    "no_intro_amiga": ("Commodore - Amiga.dat",),
    "redump_generic": ("redump.dat",),
}


# Ordered metadata source preferences by normalized system_id.
# Resolver tries each source key until it finds an available DAT file.
PRELOADED_METADATA_PROFILE_BY_SYSTEM: dict[str, tuple[str, ...]] = {
    "arcade": ("fbneo_arcade", "mame"),
    "cps1": ("fbneo_arcade", "mame"),
    "cps2": ("fbneo_arcade", "mame"),
    "cps3": ("fbneo_arcade", "mame"),
    "fbneo": ("fbneo_arcade", "mame"),
    "mame": ("mame", "fbneo_arcade"),
    "neogeo": ("fbneo_neogeo", "fbneo_arcade", "mame"),
    "snk_neo_geo_aes": ("fbneo_neogeo", "fbneo_arcade", "mame"),
    "nes": ("fbneo_nes", "no_intro_generic"),
    "fds": ("fbneo_fds", "no_intro_generic"),
    "snes": ("fbneo_snes", "no_intro_generic"),
    "super_nintendo": ("fbneo_snes", "no_intro_generic"),
    "n64": ("no_intro_n64", "no_intro_generic"),
    "nintendo_64": ("no_intro_n64", "no_intro_generic"),
    "n64dd": ("no_intro_n64",),
    "gamecube": ("redump_gamecube", "redump_generic"),
    "gc": ("redump_gamecube", "redump_generic"),
    "ngc": ("redump_gamecube", "redump_generic"),
    "psp": ("no_intro_psp", "redump_psp", "redump_generic"),
    "playstation_portable": ("no_intro_psp", "redump_psp", "redump_generic"),
    "megadrive": ("fbneo_megadrive", "no_intro_generic"),
    "genesis": ("fbneo_megadrive", "no_intro_generic"),
    "sega_genesis": ("fbneo_megadrive", "no_intro_generic"),
    "segacd": ("redump_segacd", "redump_generic"),
    "megacd": ("redump_segacd", "redump_generic"),
    "sega_cd": ("redump_segacd", "redump_generic"),
    "mastersystem": ("fbneo_mastersystem", "no_intro_generic"),
    "sms": ("fbneo_mastersystem", "no_intro_generic"),
    "gamegear": ("fbneo_gamegear", "no_intro_generic"),
    "gg": ("fbneo_gamegear", "no_intro_generic"),
    "pcengine": ("fbneo_pcengine", "fbneo_tg16", "no_intro_generic"),
    "tg16": ("fbneo_tg16", "fbneo_pcengine", "no_intro_generic"),
    "coleco": ("fbneo_colecovision", "no_intro_generic"),
    "colecovision": ("fbneo_colecovision", "no_intro_generic"),
    "msx": ("fbneo_msx1", "no_intro_generic"),
    "sg1000": ("fbneo_sg1000", "no_intro_generic"),
    "commodore_amiga": ("no_intro_amiga", "no_intro_generic"),
    "amigacd32": ("redump_amigacd32", "redump_generic"),
    "cd32": ("redump_amigacd32", "redump_generic"),
    "commodore_amiga_cd32": ("redump_amigacd32", "redump_generic"),
    "psx": ("redump_generic",),
    "ps2": ("redump_generic",),
    "saturn": ("redump_generic",),
    "dreamcast": ("redump_generic",),
    "dc": ("redump_generic",),
}
