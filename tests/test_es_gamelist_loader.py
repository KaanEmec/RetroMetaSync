from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from retrometasync.core.loaders import ESGamelistLoader, LoaderInput
from retrometasync.core.models import MetadataSource, System


class ESGamelistLoaderTests(unittest.TestCase):
    def test_loads_single_game_and_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            snes_dir = root / "roms" / "snes"
            (snes_dir / "images").mkdir(parents=True, exist_ok=True)
            (snes_dir / "videos").mkdir(parents=True, exist_ok=True)
            (snes_dir / "manuals").mkdir(parents=True, exist_ok=True)

            rom_path = snes_dir / "Super Mario World.zip"
            rom_path.write_bytes(b"rom")
            image_path = snes_dir / "images" / "Super Mario World-image.png"
            image_path.write_bytes(b"img")
            video_path = snes_dir / "videos" / "Super Mario World-video.mp4"
            video_path.write_bytes(b"vid")
            manual_path = snes_dir / "manuals" / "Super Mario World.pdf"
            manual_path.write_bytes(b"pdf")

            gamelist_content = """<?xml version="1.0"?>
<gameList>
  <game>
    <path>./Super Mario World.zip</path>
    <name>Super Mario World</name>
    <sortname>Mario, Super World</sortname>
    <image>./images/Super Mario World-image.png</image>
    <fanart>./images/Super Mario World-image.png</fanart>
    <video>./videos/Super Mario World-video.mp4</video>
    <manual>./manuals/Super Mario World.pdf</manual>
    <genre>Platformer, Action</genre>
    <lang>en, jp</lang>
    <region>US, EU</region>
    <favorite>true</favorite>
    <hidden>false</hidden>
    <players>1-2</players>
    <playcount>3</playcount>
    <lastplayed>20250101T103000</lastplayed>
  </game>
</gameList>
"""
            gamelist_path = snes_dir / "gamelist.xml"
            gamelist_path.write_text(gamelist_content, encoding="utf-8")

            system = System(
                system_id="snes",
                display_name="SNES",
                rom_root=snes_dir,
                metadata_source=MetadataSource.GAMELIST_XML,
                metadata_paths=[gamelist_path],
            )

            result = ESGamelistLoader().load(LoaderInput(source_root=root, systems=[system]))
            self.assertEqual(len(result.warnings), 0)
            self.assertIn("snes", result.games_by_system)
            self.assertEqual(len(result.games_by_system["snes"]), 1)

            game = result.games_by_system["snes"][0]
            self.assertEqual(game.title, "Super Mario World")
            self.assertEqual(game.sort_title, "Mario, Super World")
            self.assertEqual(game.rom_path, rom_path.resolve())
            self.assertGreaterEqual(len(game.assets), 2)
            self.assertTrue(game.favorite)
            self.assertFalse(game.hidden)
            self.assertEqual(game.players, "1-2")
            self.assertEqual(game.playcount, 3)
            self.assertIn("Platformer", game.genres)
            self.assertIn("en", game.languages)


if __name__ == "__main__":
    unittest.main()
