from __future__ import annotations

from retrometasync.core.conversion.engine import _lookup_asset_fallback
from retrometasync.core.models import Asset, AssetType, AssetVerificationState, Game, Library

IMAGE_ASSET_TYPES: tuple[AssetType, ...] = (
    AssetType.BOX_FRONT,
    AssetType.BOX_BACK,
    AssetType.BOX_SPINE,
    AssetType.DISC,
    AssetType.SCREENSHOT_GAMEPLAY,
    AssetType.SCREENSHOT_TITLE,
    AssetType.SCREENSHOT_MENU,
    AssetType.MARQUEE,
    AssetType.WHEEL,
    AssetType.LOGO,
    AssetType.FANART,
    AssetType.BACKGROUND,
    AssetType.MIXIMAGE,
    AssetType.BEZEL,
)


def verify_unchecked_assets(
    game: Game,
    library: Library | None = None,
    system_display: str | None = None,
) -> int:
    """Verify only unchecked assets for a game and update verification states.

    Returns the number of assets whose state changed.
    """
    changes = 0
    for asset in game.assets:
        if asset.verification_state != AssetVerificationState.UNCHECKED:
            continue
        exists = asset.file_path.exists()
        next_state = AssetVerificationState.VERIFIED_EXISTS if exists else AssetVerificationState.VERIFIED_MISSING
        if asset.verification_state != next_state:
            asset.verification_state = next_state
            changes += 1

    if library is not None and system_display:
        for key in ("image", "video", "manual"):
            if not _needs_fallback_lookup(game, key):
                continue
            fallback = _lookup_asset_fallback(key=key, library=library, game=game, system_display=system_display)
            if fallback is None:
                continue
            fallback_asset_type = _fallback_asset_type_for_key(key)
            existing = _first_asset_for_key(game, key)
            if existing is None:
                game.assets.append(
                    Asset(
                        asset_type=fallback_asset_type,
                        file_path=fallback,
                        verification_state=AssetVerificationState.VERIFIED_EXISTS,
                    )
                )
                changes += 1
                continue
            updated = False
            if existing.file_path != fallback:
                existing.file_path = fallback
                updated = True
            if existing.verification_state != AssetVerificationState.VERIFIED_EXISTS:
                existing.verification_state = AssetVerificationState.VERIFIED_EXISTS
                updated = True
            if updated:
                changes += 1
    return changes


def _first_asset_for_key(game: Game, key: str) -> Asset | None:
    key_types = _asset_types_for_key(key)
    for asset in game.assets:
        if asset.asset_type in key_types:
            return asset
    return None


def _needs_fallback_lookup(game: Game, key: str) -> bool:
    key_types = _asset_types_for_key(key)
    relevant = [asset for asset in game.assets if asset.asset_type in key_types]
    if not relevant:
        return True
    return not any(
        asset.verification_state in (AssetVerificationState.VERIFIED_EXISTS, AssetVerificationState.VERIFIED_MISSING)
        for asset in relevant
    )


def _asset_types_for_key(key: str) -> tuple[AssetType, ...]:
    if key == "image":
        return IMAGE_ASSET_TYPES
    if key == "video":
        return (AssetType.VIDEO,)
    return (AssetType.MANUAL,)


def _fallback_asset_type_for_key(key: str) -> AssetType:
    if key == "video":
        return AssetType.VIDEO
    if key == "manual":
        return AssetType.MANUAL
    return AssetType.BOX_FRONT
