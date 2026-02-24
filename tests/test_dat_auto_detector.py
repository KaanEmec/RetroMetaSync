from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from retrometasync.core.dat_auto_detector import DatAutoDetector
from retrometasync.core.models import Game


class DatAutoDetectorTests(unittest.TestCase):
    def test_detects_catalog_dat_for_target_system(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dat_root = root / "PreloadedMetaData" / "FBNeo"
            dat_root.mkdir(parents=True, exist_ok=True)
            dat_path = dat_root / "FinalBurn Neo (ClrMame Pro XML, Arcade only).dat"
            dat_path.write_text(
                """<?xml version="1.0"?>
<datafile>
  <header>
    <name>FinalBurn Neo - Arcade Games</name>
  </header>
  <machine name="pacman">
    <description>Pac-Man</description>
  </machine>
</datafile>
""",
                encoding="utf-8",
            )
            detector = DatAutoDetector()
            result = detector.detect_for_systems(source_root=root, metadata_root=root / "PreloadedMetaData", target_system_ids=["arcade"])
            self.assertIn("arcade", result.matches)
            self.assertEqual(result.matches["arcade"].dat_path.name, dat_path.name)

    def test_strict_verify_rejects_non_matching_dat(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dat_root = root / "dats"
            dat_root.mkdir(parents=True, exist_ok=True)
            dat_path = dat_root / "FinalBurn Neo (ClrMame Pro XML, Arcade only).dat"
            dat_path.write_text(
                """<?xml version="1.0"?>
<datafile>
  <machine name="someothergame">
    <description>Some Other Game</description>
  </machine>
</datafile>
""",
                encoding="utf-8",
            )
            games_by_system = {
                "arcade": [Game(rom_path=root / "roms" / "pacman.zip", system_id="arcade", title="pacman")]
            }
            detector = DatAutoDetector()
            result = detector.detect_for_systems(
                source_root=root,
                metadata_root=dat_root,
                target_system_ids=["arcade"],
                strict_verify=True,
                games_by_system=games_by_system,
            )
            self.assertNotIn("arcade", result.matches)
            self.assertIn("arcade", result.unresolved_systems)

    def test_detects_cps1_using_fbneo_arcade_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dat_root = root / "PreloadedMetaData"
            dat_root.mkdir(parents=True, exist_ok=True)
            dat_path = dat_root / "FinalBurn Neo (ClrMame Pro XML, Arcade only).dat"
            dat_path.write_text(
                """<?xml version="1.0"?>
<datafile>
  <header>
    <name>FinalBurn Neo - Arcade Games</name>
  </header>
  <machine name="sf2">
    <description>Street Fighter II</description>
  </machine>
</datafile>
""",
                encoding="utf-8",
            )
            detector = DatAutoDetector()
            result = detector.detect_for_systems(source_root=root, metadata_root=dat_root, target_system_ids=["cps1"])
            self.assertIn("cps1", result.matches)
            self.assertEqual(result.matches["cps1"].dat_path.name, dat_path.name)

    def test_detects_dreamcast_keyword_file_even_with_ignored_large_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dat_root = root / "PreloadedMetaData" / "MAME"
            dat_root.mkdir(parents=True, exist_ok=True)
            # Large tree should be skipped by detector.
            ignored = dat_root / "mamedev-mame" / "hash"
            ignored.mkdir(parents=True, exist_ok=True)
            for index in range(30):
                (ignored / f"noise_{index}.xml").write_text("<datafile></datafile>", encoding="utf-8")
            dreamcast_dat = dat_root / "Sega - Dreamcast.dat"
            dreamcast_dat.write_text(
                """clrmamepro (
    name "Sega - Dreamcast"
)
""",
                encoding="utf-8",
            )
            detector = DatAutoDetector()
            result = detector.detect_for_systems(source_root=root, metadata_root=root / "PreloadedMetaData", target_system_ids=["dreamcast"])
            self.assertIn("dreamcast", result.matches)
            self.assertEqual(result.matches["dreamcast"].dat_path.name, dreamcast_dat.name)

    def test_detects_commodore_amiga_from_no_intro_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dat_root = root / "PreloadedMetaData" / "NoIntro"
            dat_root.mkdir(parents=True, exist_ok=True)
            amiga_dat = dat_root / "Commodore - Amiga.dat"
            amiga_dat.write_text(
                """clrmamepro (
    name "Commodore - Amiga"
)
""",
                encoding="utf-8",
            )
            detector = DatAutoDetector()
            result = detector.detect_for_systems(
                source_root=root,
                metadata_root=root / "PreloadedMetaData",
                target_system_ids=["commodore_amiga"],
            )
            self.assertIn("commodore_amiga", result.matches)
            self.assertEqual(result.matches["commodore_amiga"].dat_path.name, amiga_dat.name)

    def test_detects_common_alias_systems_from_catalog_and_keywords(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dat_root = root / "PreloadedMetaData"
            dat_root.mkdir(parents=True, exist_ok=True)
            expected = {
                "n64": "Nintendo - Nintendo 64.dat",
                "gc": "Nintendo - GameCube.dat",
                "psp": "Sony - PlayStation Portable.dat",
                "segacd": "Sega - Mega-CD - Sega CD.dat",
                "amigacd32": "Commodore - CD32.dat",
            }
            for filename in expected.values():
                (dat_root / filename).write_text(
                    f"""clrmamepro (
    name "{filename.replace('.dat', '')}"
)
""",
                    encoding="utf-8",
                )
            detector = DatAutoDetector()
            result = detector.detect_for_systems(
                source_root=root,
                metadata_root=dat_root,
                target_system_ids=list(expected.keys()),
            )
            for system_id, dat_name in expected.items():
                canonical = result.matches.get(system_id) or result.matches.get("gamecube" if system_id == "gc" else system_id)
                self.assertIsNotNone(canonical)
                if canonical is not None:
                    self.assertEqual(canonical.dat_path.name, dat_name)


if __name__ == "__main__":
    unittest.main()
