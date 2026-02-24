from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from retrometasync.core.detection import DetectionResult
from retrometasync.core.models import MetadataSource, System
from retrometasync.core.normalizer import LibraryNormalizer
from retrometasync.core.preloaded_metadata import (
    enrich_library_systems_with_preloaded_metadata,
    parse_clrmamepro_dat,
    parse_clrmamepro_dat_xml,
)


class PreloadedMetadataTests(unittest.TestCase):
    def test_parse_clrmamepro_text_dat_indexes_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            dat_path = Path(temp_dir) / "mame.dat"
            dat_path.write_text(
                """clrmamepro (
    name "MAME - Consolidated ROM Sets"
)

game (
    name "1941: Counter Attack (World)"
    year "1990"
    developer "Capcom"
    rom ( name 1941.zip size 1419821 crc DE03FB24 sha1 D6EE54766D377D1136F6A5E17B772666A072E74E )
)
""",
                encoding="utf-8",
            )
            index = parse_clrmamepro_dat(dat_path)
            self.assertIn("1941", index.by_set_name)
            entry = index.by_set_name["1941"]
            self.assertEqual(entry.title, "1941: Counter Attack (World)")
            self.assertEqual(entry.year, 1990)
            self.assertEqual(entry.manufacturer, "Capcom")
            self.assertIn("de03fb24", index.by_crc)

    def test_parse_clrmamepro_dat_xml_indexes_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            dat_path = Path(temp_dir) / "fbneo_arcade.dat"
            dat_path.write_text(
                """<?xml version="1.0"?>
<datafile>
  <machine name="pacman">
    <description>Pac-Man</description>
    <year>1980</year>
    <manufacturer>Namco</manufacturer>
    <rom name="pacman.zip" crc="c1e6ab10" sha1="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" />
  </machine>
</datafile>
""",
                encoding="utf-8",
            )

            index = parse_clrmamepro_dat_xml(dat_path)
            self.assertIn("pacman", index.by_set_name)
            entry = index.by_set_name["pacman"]
            self.assertEqual(entry.title, "Pac-Man")
            self.assertEqual(entry.year, 1980)
            self.assertEqual(entry.manufacturer, "Namco")
            self.assertIn("c1e6ab10", index.by_crc)

    def test_normalizer_enriches_placeholder_title_from_fbneo_dat(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            rom_root = root / "roms" / "arcade"
            rom_root.mkdir(parents=True, exist_ok=True)
            rom_path = rom_root / "pacman.zip"
            rom_path.write_bytes(b"rom")

            dat_dir = root / "metadata" / "dats"
            dat_dir.mkdir(parents=True, exist_ok=True)
            (dat_dir / "FinalBurn Neo (ClrMame Pro XML, Arcade only).dat").write_text(
                """<?xml version="1.0"?>
<datafile>
  <machine name="pacman">
    <description>Pac-Man</description>
    <year>1980</year>
    <manufacturer>Namco</manufacturer>
    <rom name="pacman.zip" crc="c1e6ab10" sha1="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" />
  </machine>
</datafile>
""",
                encoding="utf-8",
            )

            system = System(
                system_id="arcade",
                display_name="Arcade",
                rom_root=rom_root,
                metadata_source=MetadataSource.NONE,
                metadata_paths=[],
                detected_ecosystem="es_classic",
            )
            detection = DetectionResult(
                source_root=root,
                detected_ecosystem="es_classic",
                detected_family="es_family",
                confidence=1.0,
                systems=[system],
            )

            result = LibraryNormalizer().normalize(detection)
            games = result.library.games_by_system.get("arcade", [])
            self.assertEqual(len(games), 1)
            game = games[0]
            self.assertEqual(game.title, "Pac-Man")
            self.assertEqual(game.publisher, "Namco")
            self.assertEqual(game.developer, "Namco")
            self.assertEqual(game.crc, "c1e6ab10")
            self.assertEqual(game.sha1, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
            self.assertIsNotNone(game.release_date)

    def test_normalizer_keeps_non_placeholder_title(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            rom_root = root / "roms" / "arcade"
            rom_root.mkdir(parents=True, exist_ok=True)
            rom_path = rom_root / "pacman.zip"
            rom_path.write_bytes(b"rom")
            gamelist_path = rom_root / "gamelist.xml"
            gamelist_path.write_text(
                """<?xml version="1.0"?>
<gameList>
  <game>
    <path>./pacman.zip</path>
    <name>My Custom Pac-Man Title</name>
  </game>
</gameList>
""",
                encoding="utf-8",
            )

            dat_dir = root / "metadata" / "dats"
            dat_dir.mkdir(parents=True, exist_ok=True)
            (dat_dir / "FinalBurn Neo (ClrMame Pro XML, Arcade only).dat").write_text(
                """<?xml version="1.0"?>
<datafile>
  <machine name="pacman">
    <description>Pac-Man</description>
    <year>1980</year>
    <manufacturer>Namco</manufacturer>
  </machine>
</datafile>
""",
                encoding="utf-8",
            )

            system = System(
                system_id="arcade",
                display_name="Arcade",
                rom_root=rom_root,
                metadata_source=MetadataSource.GAMELIST_XML,
                metadata_paths=[gamelist_path],
                detected_ecosystem="es_classic",
            )
            detection = DetectionResult(
                source_root=root,
                detected_ecosystem="es_classic",
                detected_family="es_family",
                confidence=1.0,
                systems=[system],
            )

            result = LibraryNormalizer().normalize(detection)
            game = result.library.games_by_system["arcade"][0]
            self.assertEqual(game.title, "My Custom Pac-Man Title")
            self.assertEqual(game.publisher, "Namco")
            self.assertEqual(game.developer, "Namco")

    def test_normalizer_hash_fallback_matches_when_name_does_not(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            rom_root = root / "roms" / "arcade"
            rom_root.mkdir(parents=True, exist_ok=True)
            rom_path = rom_root / "mismatch.zip"
            rom_path.write_bytes(b"rom")

            dat_root = root / "custom_dats"
            dat_root.mkdir(parents=True, exist_ok=True)
            (dat_root / "FinalBurn Neo (ClrMame Pro XML, Arcade only).dat").write_text(
                """<?xml version="1.0"?>
<datafile>
  <machine name="pacman">
    <description>Pac-Man</description>
    <year>1980</year>
    <manufacturer>Namco</manufacturer>
    <rom name="pacman.zip" crc="79520fa1" sha1="a1e17a20e93e5da710685444df3ad038ac66e2c9" />
  </machine>
</datafile>
""",
                encoding="utf-8",
            )

            system = System(
                system_id="arcade",
                display_name="Arcade",
                rom_root=rom_root,
                metadata_source=MetadataSource.NONE,
                metadata_paths=[],
                detected_ecosystem="es_classic",
            )
            detection = DetectionResult(
                source_root=root,
                detected_ecosystem="es_classic",
                detected_family="es_family",
                confidence=1.0,
                systems=[system],
            )

            # Name-based match should fail, preserving placeholder title.
            without_hashes = LibraryNormalizer().normalize(
                detection,
                preloaded_metadata_root=dat_root,
                compute_missing_hashes=False,
            )
            self.assertEqual(without_hashes.library.games_by_system["arcade"][0].title, "mismatch")

            # Hash fallback should identify the same ROM bytes and enrich.
            with_hashes = LibraryNormalizer().normalize(
                detection,
                preloaded_metadata_root=dat_root,
                compute_missing_hashes=True,
            )
            game = with_hashes.library.games_by_system["arcade"][0]
            self.assertEqual(game.title, "Pac-Man")
            self.assertEqual(game.publisher, "Namco")

    def test_enrich_selected_systems_uses_manual_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            rom_root_arcade = root / "roms" / "arcade"
            rom_root_nes = root / "roms" / "nes"
            rom_root_arcade.mkdir(parents=True, exist_ok=True)
            rom_root_nes.mkdir(parents=True, exist_ok=True)
            (rom_root_arcade / "pacman.zip").write_bytes(b"rom")
            (rom_root_nes / "mario.nes").write_bytes(b"rom")

            metadata_root = root / "PreloadedMetaData"
            metadata_root.mkdir(parents=True, exist_ok=True)
            dat_path = metadata_root / "custom_arcade.dat"
            dat_path.write_text(
                """<?xml version="1.0"?>
<datafile>
  <machine name="pacman">
    <description>Pac-Man</description>
    <manufacturer>Namco</manufacturer>
  </machine>
</datafile>
""",
                encoding="utf-8",
            )

            detection = DetectionResult(
                source_root=root,
                detected_ecosystem="es_classic",
                detected_family="es_family",
                confidence=1.0,
                systems=[
                    System(
                        system_id="arcade",
                        display_name="Arcade",
                        rom_root=rom_root_arcade,
                        metadata_source=MetadataSource.NONE,
                        metadata_paths=[],
                    ),
                    System(
                        system_id="nes",
                        display_name="NES",
                        rom_root=rom_root_nes,
                        metadata_source=MetadataSource.NONE,
                        metadata_paths=[],
                    ),
                ],
            )
            normalized = LibraryNormalizer().normalize(detection)
            arcade_game = normalized.library.games_by_system["arcade"][0]
            nes_game = normalized.library.games_by_system["nes"][0]
            self.assertEqual(arcade_game.title, "pacman")
            self.assertEqual(nes_game.title, "mario")

            enrich_library_systems_with_preloaded_metadata(
                library=normalized.library,
                source_root=root,
                target_system_ids=["arcade"],
                metadata_root=metadata_root,
                dat_override_by_system={"arcade": dat_path},
            )
            self.assertEqual(arcade_game.title, "Pac-Man")
            self.assertEqual(nes_game.title, "mario")


if __name__ == "__main__":
    unittest.main()
