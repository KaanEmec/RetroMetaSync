from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from retrometasync.core.conversion import ConversionEngine, ConversionRequest
from retrometasync.core.models import Asset, AssetType, Game, Library, MetadataSource, System


class ConversionEngineTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
