from __future__ import annotations

import re

# Alias values are normalized by canonicalize_system_id before lookup.
ALIAS_TO_CANONICAL_SYSTEM_ID: dict[str, str] = {
    # Nintendo
    "super_nintendo": "snes",
    "super_famicom": "snes",
    "nintendo_64": "n64",
    "nintendo64": "n64",
    "n64": "n64",
    "n64dd": "n64dd",
    "gamecube": "gamecube",
    "gc": "gamecube",
    "ngc": "gamecube",
    # Sony
    "psp": "psp",
    "playstation_portable": "psp",
    "sony_psp": "psp",
    "psx": "psx",
    "ps1": "psx",
    "playstation": "psx",
    # Sega
    "sega_genesis": "genesis",
    "mega_drive": "megadrive",
    "sega_cd": "segacd",
    "segacd": "segacd",
    "mega_cd": "segacd",
    "megacd": "segacd",
    # SNK
    "snk_neo_geo_aes": "neogeo",
    # Commodore
    "commodore_amiga_cd32": "amigacd32",
    "amiga_cd32": "amigacd32",
    "amigacd32": "amigacd32",
    "cd32": "amigacd32",
    "commodore_amiga": "commodore_amiga",
    # Arcade families
    "capcom_play_system_1": "cps1",
    "capcom_play_system_2": "cps2",
    "capcom_play_system_3": "cps3",
    # General existing shorthand
    "dc": "dreamcast",
}

CANONICAL_TO_SEARCH_TOKENS: dict[str, tuple[str, ...]] = {
    "n64": ("n64", "nintendo 64"),
    "n64dd": ("n64dd", "nintendo 64dd"),
    "gamecube": ("gamecube", "game cube", "nintendo gamecube"),
    "psp": ("psp", "playstation portable", "sony psp"),
    "segacd": ("segacd", "sega cd", "mega cd", "megacd"),
    "amigacd32": ("amigacd32", "amiga cd32", "commodore cd32", "cd32"),
    "commodore_amiga": ("commodore amiga", "amiga", "commodore"),
    "snes": ("snes", "super nintendo", "super famicom"),
    "genesis": ("genesis", "sega genesis", "mega drive"),
    "megadrive": ("megadrive", "mega drive", "genesis"),
    "neogeo": ("neogeo", "neo geo", "snk neo geo"),
    "dreamcast": ("dreamcast", "sega dreamcast", "dc"),
    "cps1": ("cps1", "capcom play system 1"),
    "cps2": ("cps2", "capcom play system 2"),
    "cps3": ("cps3", "capcom play system 3"),
}


def canonicalize_system_id(raw_id: str) -> str:
    normalized = _normalize_alias_key(raw_id)
    if not normalized:
        return ""
    return ALIAS_TO_CANONICAL_SYSTEM_ID.get(normalized, normalized)


def expand_search_tokens(raw_id: str) -> tuple[str, ...]:
    canonical = canonicalize_system_id(raw_id)
    tokens: list[str] = list(CANONICAL_TO_SEARCH_TOKENS.get(canonical, ()))
    if canonical and canonical not in tokens:
        tokens.append(canonical)
    spaced = canonical.replace("_", " ").strip()
    if spaced and spaced not in tokens:
        tokens.append(spaced)
    for part in canonical.split("_"):
        token = part.strip()
        if len(token) >= 2 and token not in tokens:
            tokens.append(token)
    return tuple(tokens)


def _normalize_alias_key(value: str) -> str:
    normalized = value.strip().lower()
    normalized = normalized.replace("&", " and ")
    normalized = normalized.replace("-", "_").replace(" ", "_")
    normalized = re.sub(r"_+", "_", normalized)
    normalized = normalized.strip("_")
    return normalized
