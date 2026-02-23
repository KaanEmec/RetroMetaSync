from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from retrometasync.core.asset_verifier import verify_unchecked_assets
from retrometasync.core.models import Asset, AssetType, AssetVerificationState, Game, Library, MetadataSource, System


class AssetVerifierTests(unittest.TestCase):
    def test_verify_unchecked_assets_updates_existing_and_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            existing = root / "exists.png"
            missing = root / "missing.png"
            existing.write_bytes(b"ok")

            game = Game(
                rom_path=root / "game.rom",
                system_id="snes",
                title="Game",
                assets=[
                    Asset(asset_type=AssetType.BOX_FRONT, file_path=existing),
                    Asset(asset_type=AssetType.VIDEO, file_path=missing),
                ],
            )
            changes = verify_unchecked_assets(game)
            self.assertEqual(changes, 2)
            self.assertEqual(game.assets[0].verification_state, AssetVerificationState.VERIFIED_EXISTS)
            self.assertEqual(game.assets[1].verification_state, AssetVerificationState.VERIFIED_MISSING)

    def test_verify_unchecked_assets_does_not_change_already_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            existing = root / "exists.png"
            existing.write_bytes(b"ok")

            game = Game(
                rom_path=root / "game.rom",
                system_id="snes",
                title="Game",
                assets=[
                    Asset(
                        asset_type=AssetType.BOX_FRONT,
                        file_path=existing,
                        verification_state=AssetVerificationState.VERIFIED_EXISTS,
                    )
                ],
            )
            changes = verify_unchecked_assets(game)
            self.assertEqual(changes, 0)
            self.assertEqual(game.assets[0].verification_state, AssetVerificationState.VERIFIED_EXISTS)

    def test_verify_unchecked_assets_finds_launchbox_fallback_media(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            launchbox_root = root / "LaunchBox"
            videos_dir = launchbox_root / "Videos" / "Nintendo 64"
            roms_dir = launchbox_root / "Games" / "Nintendo 64"
            (launchbox_root / "Data" / "Platforms").mkdir(parents=True, exist_ok=True)
            videos_dir.mkdir(parents=True, exist_ok=True)
            roms_dir.mkdir(parents=True, exist_ok=True)

            rom_path = roms_dir / "Mario 64.z64"
            rom_path.write_bytes(b"rom")
            video_path = videos_dir / "Mario 64.mp4"
            video_path.write_bytes(b"video")

            game = Game(
                rom_path=rom_path,
                system_id="nintendo_64",
                title="Mario 64",
                assets=[],
            )
            system = System(
                system_id="nintendo_64",
                display_name="Nintendo 64",
                rom_root=roms_dir,
                metadata_source=MetadataSource.LAUNCHBOX_XML,
            )
            library = Library(
                source_root=launchbox_root,
                systems={"nintendo_64": system},
                games_by_system={"nintendo_64": [game]},
                detected_ecosystem="launchbox",
            )

            changes = verify_unchecked_assets(game, library=library, system_display="Nintendo 64")
            self.assertGreaterEqual(changes, 1)
            self.assertTrue(any(a.asset_type == AssetType.VIDEO for a in game.assets))
            video_assets = [a for a in game.assets if a.asset_type == AssetType.VIDEO]
            self.assertEqual(video_assets[0].verification_state, AssetVerificationState.VERIFIED_EXISTS)


if __name__ == "__main__":
    unittest.main()
