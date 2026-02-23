from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from retrometasync.core.conversion import ConversionEngine, ConversionRequest
from retrometasync.core.conversion.engine import _relative_for_es
from retrometasync.core.models import Asset, AssetType, AssetVerificationState, Game, Library, MetadataSource, System


class ConversionEngineTests(unittest.TestCase):
    def test_relative_for_es_uses_parent_relative_paths_when_possible(self) -> None:
        base = Path("C:/output/roms/snes")
        target = Path("C:/output/media/images/Game-image.png")
        value = _relative_for_es(target, base)
        self.assertTrue(value.startswith("../"))

    def test_batocera_conversion_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_root = root / "source"
            output_root = root / "output"
            source_root.mkdir(parents=True, exist_ok=True)

            rom_path = source_root / "Super Mario World.zip"
            rom_path.write_bytes(b"rom")
            image_path = source_root / "Super Mario World.png"
            image_path.write_bytes(b"img")

            system = System(
                system_id="snes",
                display_name="SNES",
                rom_root=source_root,
                metadata_source=MetadataSource.GAMELIST_XML,
            )
            game = Game(
                rom_path=rom_path,
                system_id="snes",
                title="Super Mario World",
                assets=[Asset(asset_type=AssetType.BOX_FRONT, file_path=image_path)],
            )
            library = Library(source_root=source_root, systems={"snes": system}, games_by_system={"snes": [game]})
            request = ConversionRequest(
                library=library,
                selected_games={"snes": [game]},
                target_ecosystem="batocera",
                output_root=output_root,
            )

            result = ConversionEngine().convert(request)
            self.assertEqual(result.games_processed, 1)

            converted_rom = output_root / "roms" / "snes" / "Super Mario World.zip"
            converted_image = output_root / "roms" / "snes" / "images" / "Super Mario World-image.png"
            gamelist = output_root / "roms" / "snes" / "gamelist.xml"

            self.assertTrue(converted_rom.exists())
            self.assertTrue(converted_image.exists())
            self.assertTrue(gamelist.exists())
            self.assertGreaterEqual(len(result.preflight_checks), 1)

    def test_dry_run_does_not_write_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_root = root / "source"
            output_root = root / "output"
            source_root.mkdir(parents=True, exist_ok=True)

            rom_path = source_root / "Chrono Trigger.sfc"
            rom_path.write_bytes(b"rom")

            system = System(
                system_id="snes",
                display_name="SNES",
                rom_root=source_root,
                metadata_source=MetadataSource.GAMELIST_XML,
            )
            game = Game(rom_path=rom_path, system_id="snes", title="Chrono Trigger")
            library = Library(source_root=source_root, systems={"snes": system}, games_by_system={"snes": [game]})
            request = ConversionRequest(
                library=library,
                selected_games={"snes": [game]},
                target_ecosystem="batocera",
                output_root=output_root,
                dry_run=True,
            )

            result = ConversionEngine().convert(request)
            self.assertEqual(result.games_processed, 1)
            self.assertFalse((output_root / "roms" / "snes" / "Chrono Trigger.sfc").exists())

    def test_collision_auto_rename_when_overwrite_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_root = root / "source"
            output_root = root / "output"
            source_root.mkdir(parents=True, exist_ok=True)

            rom_path = source_root / "Contra.nes"
            rom_path.write_bytes(b"rom")

            existing = output_root / "roms" / "nes" / "Contra.nes"
            existing.parent.mkdir(parents=True, exist_ok=True)
            existing.write_bytes(b"existing")

            system = System(
                system_id="nes",
                display_name="NES",
                rom_root=source_root,
                metadata_source=MetadataSource.GAMELIST_XML,
            )
            game = Game(rom_path=rom_path, system_id="nes", title="Contra")
            library = Library(source_root=source_root, systems={"nes": system}, games_by_system={"nes": [game]})
            request = ConversionRequest(
                library=library,
                selected_games={"nes": [game]},
                target_ecosystem="batocera",
                output_root=output_root,
                overwrite_existing=False,
            )

            result = ConversionEngine().convert(request)
            self.assertEqual(result.games_processed, 1)
            self.assertTrue((output_root / "roms" / "nes" / "Contra_2.nes").exists())
            self.assertGreaterEqual(result.files_renamed_due_to_collision, 1)

    def test_dat_export_writes_system_dat(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_root = root / "source"
            output_root = root / "output"
            source_root.mkdir(parents=True, exist_ok=True)

            rom_path = source_root / "Metal Slug.zip"
            rom_path.write_bytes(b"rom")

            system = System(
                system_id="arcade",
                display_name="Arcade",
                rom_root=source_root,
                metadata_source=MetadataSource.GAMELIST_XML,
            )
            game = Game(rom_path=rom_path, system_id="arcade", title="Metal Slug")
            library = Library(source_root=source_root, systems={"arcade": system}, games_by_system={"arcade": [game]})
            request = ConversionRequest(
                library=library,
                selected_games={"arcade": [game]},
                target_ecosystem="batocera",
                output_root=output_root,
                export_dat=True,
            )

            ConversionEngine().convert(request)
            dat_path = output_root / "dats" / "arcade.dat"
            self.assertTrue(dat_path.exists())

    def test_on_demand_asset_verification_copies_existing_and_skips_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_root = root / "source"
            output_root = root / "output"
            source_root.mkdir(parents=True, exist_ok=True)

            rom_path = source_root / "Mega Man 2.nes"
            rom_path.write_bytes(b"rom")
            image_path = source_root / "Mega Man 2.png"
            image_path.write_bytes(b"img")
            missing_video_path = source_root / "Mega Man 2.mp4"

            image_asset = Asset(asset_type=AssetType.BOX_FRONT, file_path=image_path)
            video_asset = Asset(asset_type=AssetType.VIDEO, file_path=missing_video_path)
            game = Game(
                rom_path=rom_path,
                system_id="nes",
                title="Mega Man 2",
                assets=[image_asset, video_asset],
            )
            system = System(
                system_id="nes",
                display_name="NES",
                rom_root=source_root,
                metadata_source=MetadataSource.GAMELIST_XML,
            )
            library = Library(source_root=source_root, systems={"nes": system}, games_by_system={"nes": [game]})
            request = ConversionRequest(
                library=library,
                selected_games={"nes": [game]},
                target_ecosystem="batocera",
                output_root=output_root,
            )

            progress_lines: list[str] = []
            result = ConversionEngine().convert(request, progress=progress_lines.append)

            self.assertEqual(result.assets_copied, 1)
            self.assertEqual(result.assets_missing_skipped, 1)
            self.assertGreaterEqual(result.files_skipped, 1)
            self.assertEqual(image_asset.verification_state, AssetVerificationState.VERIFIED_EXISTS)
            self.assertEqual(video_asset.verification_state, AssetVerificationState.VERIFIED_MISSING)

            converted_image = output_root / "roms" / "nes" / "images" / "Mega Man 2-image.png"
            converted_video = output_root / "roms" / "nes" / "videos" / "Mega Man 2-video.mp4"
            self.assertTrue(converted_image.exists())
            self.assertFalse(converted_video.exists())
            self.assertTrue(any("asset copied [image]" in line for line in progress_lines))
            self.assertTrue(any("asset missing -> skipped [video]" in line for line in progress_lines))

    def test_launchbox_fallback_media_lookup_copies_asset_when_metadata_path_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            launchbox_root = root / "LaunchBox"
            source_root = launchbox_root
            output_root = root / "output"
            (launchbox_root / "Data" / "Platforms").mkdir(parents=True, exist_ok=True)
            (launchbox_root / "Games" / "Nintendo Game Boy Advance").mkdir(parents=True, exist_ok=True)
            image_dir = launchbox_root / "Images" / "Nintendo Game Boy Advance" / "Box - Front"
            image_dir.mkdir(parents=True, exist_ok=True)

            rom_path = launchbox_root / "Games" / "Nintendo Game Boy Advance" / "Golden Sun.gba"
            rom_path.write_bytes(b"rom")
            fallback_image = image_dir / "Golden Sun-01.png"
            fallback_image.write_bytes(b"img")

            # Metadata path is missing on disk; conversion should resolve via LaunchBox media folders.
            missing_metadata_image = launchbox_root / "Images" / "Nintendo Game Boy Advance" / "Box - Front" / "Missing.png"
            image_asset = Asset(asset_type=AssetType.BOX_FRONT, file_path=missing_metadata_image)
            game = Game(
                rom_path=rom_path,
                system_id="nintendo_game_boy_advance",
                title="Golden Sun",
                assets=[image_asset],
            )
            system = System(
                system_id="nintendo_game_boy_advance",
                display_name="Nintendo Game Boy Advance",
                rom_root=source_root,
                metadata_source=MetadataSource.LAUNCHBOX_XML,
            )
            library = Library(
                source_root=source_root,
                systems={"nintendo_game_boy_advance": system},
                games_by_system={"nintendo_game_boy_advance": [game]},
                detected_ecosystem="launchbox",
            )
            request = ConversionRequest(
                library=library,
                selected_games={"nintendo_game_boy_advance": [game]},
                target_ecosystem="batocera",
                output_root=output_root,
            )

            result = ConversionEngine().convert(request)
            converted_image = output_root / "roms" / "nintendo_game_boy_advance" / "images" / "Golden Sun-image.png"
            self.assertTrue(converted_image.exists())
            self.assertEqual(result.assets_copied, 1)
            self.assertEqual(image_asset.verification_state, AssetVerificationState.VERIFIED_EXISTS)

    def test_launchbox_fallback_media_lookup_works_without_any_metadata_asset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            launchbox_root = root / "LaunchBox"
            output_root = root / "output"
            (launchbox_root / "Data" / "Platforms").mkdir(parents=True, exist_ok=True)
            games_dir = launchbox_root / "Games" / "Nintendo Game Boy Advance"
            video_dir = launchbox_root / "Videos" / "Nintendo Game Boy Advance"
            games_dir.mkdir(parents=True, exist_ok=True)
            video_dir.mkdir(parents=True, exist_ok=True)

            rom_path = games_dir / "Advance Wars.gba"
            rom_path.write_bytes(b"rom")
            (video_dir / "Advance Wars.mp4").write_bytes(b"vid")

            game = Game(
                rom_path=rom_path,
                system_id="nintendo_game_boy_advance",
                title="Advance Wars",
                assets=[],
            )
            system = System(
                system_id="nintendo_game_boy_advance",
                display_name="Nintendo Game Boy Advance",
                rom_root=launchbox_root,
                metadata_source=MetadataSource.LAUNCHBOX_XML,
            )
            library = Library(
                source_root=launchbox_root,
                systems={"nintendo_game_boy_advance": system},
                games_by_system={"nintendo_game_boy_advance": [game]},
                detected_ecosystem="launchbox",
            )
            request = ConversionRequest(
                library=library,
                selected_games={"nintendo_game_boy_advance": [game]},
                target_ecosystem="batocera",
                output_root=output_root,
            )

            result = ConversionEngine().convert(request)
            converted_video = output_root / "roms" / "nintendo_game_boy_advance" / "videos" / "Advance Wars-video.mp4"
            self.assertTrue(converted_video.exists())
            self.assertGreaterEqual(result.assets_copied, 1)

    def test_launchbox_title_screenshot_folder_is_used_for_image_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            launchbox_root = root / "LaunchBox"
            output_root = root / "output"
            (launchbox_root / "Data" / "Platforms").mkdir(parents=True, exist_ok=True)
            games_dir = launchbox_root / "Games" / "SNK Neo Geo AES"
            title_shot_dir = launchbox_root / "Images" / "SNK Neo Geo AES" / "Screenshot - Game Title"
            games_dir.mkdir(parents=True, exist_ok=True)
            title_shot_dir.mkdir(parents=True, exist_ok=True)

            rom_path = games_dir / "mslug5.zip"
            rom_path.write_bytes(b"rom")
            (title_shot_dir / "Metal Slug 5-01.png").write_bytes(b"img")

            game = Game(
                rom_path=rom_path,
                system_id="snk_neo_geo_aes",
                title="Metal Slug 5",
                assets=[],
            )
            system = System(
                system_id="snk_neo_geo_aes",
                display_name="SNK Neo Geo AES",
                rom_root=launchbox_root,
                metadata_source=MetadataSource.LAUNCHBOX_XML,
            )
            library = Library(
                source_root=launchbox_root,
                systems={"snk_neo_geo_aes": system},
                games_by_system={"snk_neo_geo_aes": [game]},
                detected_ecosystem="launchbox",
            )
            request = ConversionRequest(
                library=library,
                selected_games={"snk_neo_geo_aes": [game]},
                target_ecosystem="batocera",
                output_root=output_root,
            )

            result = ConversionEngine().convert(request)
            converted_image = output_root / "roms" / "snk_neo_geo_aes" / "images" / "mslug5-image.png"
            self.assertTrue(converted_image.exists())
            self.assertGreaterEqual(result.assets_copied, 1)

    def test_es_family_fallback_uses_neighbor_images_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_root = root / "source"
            output_root = root / "output"
            rom_dir = source_root / "roms" / "snes"
            image_dir = rom_dir / "images"
            rom_dir.mkdir(parents=True, exist_ok=True)
            image_dir.mkdir(parents=True, exist_ok=True)

            rom_path = rom_dir / "Secret of Evermore.sfc"
            rom_path.write_bytes(b"rom")
            (image_dir / "Secret of Evermore-image.png").write_bytes(b"img")

            game = Game(
                rom_path=rom_path,
                system_id="snes",
                title="Secret of Evermore",
                assets=[],
            )
            system = System(
                system_id="snes",
                display_name="SNES",
                rom_root=rom_dir,
                metadata_source=MetadataSource.GAMELIST_XML,
            )
            library = Library(
                source_root=source_root,
                systems={"snes": system},
                games_by_system={"snes": [game]},
                detected_ecosystem="batocera",
            )
            request = ConversionRequest(
                library=library,
                selected_games={"snes": [game]},
                target_ecosystem="batocera",
                output_root=output_root,
            )

            result = ConversionEngine().convert(request)
            converted_image = output_root / "roms" / "snes" / "images" / "Secret of Evermore-image.png"
            self.assertTrue(converted_image.exists())
            self.assertGreaterEqual(result.assets_copied, 1)


if __name__ == "__main__":
    unittest.main()
