from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from retrometasync.core.loaders import LaunchBoxXmlLoader, LoaderInput
from retrometasync.core.models import AssetVerificationState


class LaunchBoxXmlLoaderTests(unittest.TestCase):
    def test_loads_richer_launchbox_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            platform_dir = root / "LaunchBox" / "Data" / "Platforms"
            platform_dir.mkdir(parents=True, exist_ok=True)
            games_dir = root / "LaunchBox" / "Games" / "Super Nintendo"
            games_dir.mkdir(parents=True, exist_ok=True)
            manuals_dir = root / "LaunchBox" / "Manuals"
            manuals_dir.mkdir(parents=True, exist_ok=True)

            (games_dir / "Secret of Mana.sfc").write_bytes(b"rom")
            (manuals_dir / "Secret of Mana.pdf").write_bytes(b"pdf")

            xml_content = """<?xml version="1.0"?>
<LaunchBox>
  <Game>
    <Title>Secret of Mana</Title>
    <SortTitle>Mana, Secret of</SortTitle>
    <ApplicationPath>Games/Super Nintendo/Secret of Mana.sfc</ApplicationPath>
    <ManualPath>Manuals/Secret of Mana.pdf</ManualPath>
    <Developer>Squaresoft</Developer>
    <Publisher>Nintendo</Publisher>
    <Genre>RPG;Action</Genre>
    <Language>en,jp</Language>
    <Region>US,JP</Region>
    <Favorite>true</Favorite>
    <PlayCount>7</PlayCount>
    <LastPlayedDate>2025-01-01T11:22:33</LastPlayedDate>
    <CommunityStarRating>4.5</CommunityStarRating>
    <Notes>Classic action RPG.</Notes>
  </Game>
</LaunchBox>
"""
            platform_xml = platform_dir / "Super Nintendo.xml"
            platform_xml.write_text(xml_content, encoding="utf-8")

            result = LaunchBoxXmlLoader().load(LoaderInput(source_root=root))
            self.assertEqual(len(result.warnings), 0)
            self.assertIn("snes", result.games_by_system)
            self.assertEqual(len(result.games_by_system["snes"]), 1)

            game = result.games_by_system["snes"][0]
            self.assertEqual(game.title, "Secret of Mana")
            self.assertEqual(game.sort_title, "Mana, Secret of")
            self.assertTrue(game.favorite)
            self.assertEqual(game.playcount, 7)
            self.assertEqual(game.rating, 4.5)
            self.assertIn("RPG", game.genres)
            self.assertIn("en", game.languages)
            self.assertIn("US", game.regions)
            self.assertEqual(len(game.assets), 1)
            self.assertEqual(game.assets[0].verification_state, AssetVerificationState.UNCHECKED)

    def test_loads_when_source_is_launchbox_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            launchbox_root = Path(temp_dir) / "LaunchBox"
            platform_dir = launchbox_root / "Data" / "Platforms"
            platform_dir.mkdir(parents=True, exist_ok=True)
            (launchbox_root / "Games").mkdir(parents=True, exist_ok=True)

            xml_content = """<?xml version="1.0"?>
<LaunchBox>
  <Game>
    <Title>F-Zero X</Title>
    <ApplicationPath>Games/F-Zero X.z64</ApplicationPath>
  </Game>
</LaunchBox>
"""
            (platform_dir / "Nintendo 64.xml").write_text(xml_content, encoding="utf-8")

            result = LaunchBoxXmlLoader().load(LoaderInput(source_root=launchbox_root))
            self.assertEqual(len(result.warnings), 0)
            self.assertIn("n64", result.games_by_system)
            self.assertEqual(len(result.games_by_system["n64"]), 1)


if __name__ == "__main__":
    unittest.main()
