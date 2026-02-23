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
