from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from retrometasync.core.detection import LibraryDetector


class DetectionTests(unittest.TestCase):
    def test_detects_es_de_signature(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "ES-DE" / "downloaded_media").mkdir(parents=True, exist_ok=True)
            (root / "ES-DE" / "gamelists" / "snes").mkdir(parents=True, exist_ok=True)
            (root / "ES-DE" / "gamelists" / "snes" / "gamelist.xml").write_text(
                "<gameList></gameList>", encoding="utf-8"
            )

            result = LibraryDetector().detect(root)
            self.assertEqual(result.detected_ecosystem, "es_de")
            self.assertGreater(result.confidence, 0)
            self.assertTrue(any(system.system_id == "snes" for system in result.systems))

    def test_detects_systems_from_real_rom_files_without_gamelist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            roms_root = Path(temp_dir) / "roms"
            snes = roms_root / "snes"
            gba = roms_root / "gba"
            snes.mkdir(parents=True, exist_ok=True)
            gba.mkdir(parents=True, exist_ok=True)
            (snes / "Super Metroid.sfc").write_bytes(b"rom")
            (gba / "Metroid Fusion.gba").write_bytes(b"rom")

            result = LibraryDetector().detect(roms_root)
            detected_ids = {system.system_id for system in result.systems}

            self.assertIn("snes", detected_ids)
            self.assertIn("gba", detected_ids)

    def test_launchbox_fast_path_detects_from_launchbox_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "LaunchBox" / "Data" / "Platforms").mkdir(parents=True, exist_ok=True)
            (root / "LaunchBox" / "Data" / "Platforms" / "Sega Genesis.xml").write_text(
                "<LaunchBox></LaunchBox>",
                encoding="utf-8",
            )

            result = LibraryDetector().detect(root)
            self.assertEqual(result.detected_ecosystem, "launchbox")
            self.assertEqual(result.source_root, root / "LaunchBox")
            self.assertTrue(any(system.system_id == "sega_genesis" for system in result.systems))

    def test_launchbox_mode_accepts_data_folder_directly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            launchbox_root = Path(temp_dir) / "LaunchBox"
            data_root = launchbox_root / "Data"
            (data_root / "Platforms").mkdir(parents=True, exist_ok=True)
            (data_root / "Platforms" / "Nintendo 64.xml").write_text("<LaunchBox></LaunchBox>", encoding="utf-8")

            result = LibraryDetector().detect(data_root, preferred_ecosystem="launchbox")
            self.assertEqual(result.detected_ecosystem, "launchbox")
            self.assertEqual(result.source_root, launchbox_root)
            self.assertTrue(any(system.system_id == "nintendo_64" for system in result.systems))

    def test_preferred_retroarch_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "Nintendo - SNES.lpl").write_text("[]", encoding="utf-8")

            result = LibraryDetector().detect(root, preferred_ecosystem="retroarch")
            self.assertEqual(result.detected_ecosystem, "retroarch")
            self.assertEqual(result.source_root, root)

    def test_auto_fast_detect_muos(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "MUOS" / "info" / "catalogue" / "gba").mkdir(parents=True, exist_ok=True)

            result = LibraryDetector().detect(root)
            self.assertEqual(result.detected_ecosystem, "muos")


if __name__ == "__main__":
    unittest.main()
