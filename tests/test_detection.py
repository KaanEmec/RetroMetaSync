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


if __name__ == "__main__":
    unittest.main()
