"""Tests for game list ViewModel and selection integrity (high-scale UI plan)."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from retrometasync.core.models import (
    Asset,
    AssetType,
    AssetVerificationState,
    Game,
    Library,
    MetadataSource,
    System,
)
from retrometasync.ui.game_list import GameListViewModel, _build_key


def _make_library() -> Library:
    root = Path("/fake/root")
    systems = {
        "snes": System(
            system_id="snes",
            display_name="SNES",
            rom_root=root / "snes",
            metadata_source=MetadataSource.GAMELIST_XML,
        ),
        "nes": System(
            system_id="nes",
            display_name="NES",
            rom_root=root / "nes",
            metadata_source=MetadataSource.GAMELIST_XML,
        ),
    }
    snes_roms = [
        Game(rom_path=root / "snes" / "a.zip", system_id="snes", title="Game A", assets=[]),
        Game(
            rom_path=root / "snes" / "b.zip",
            system_id="snes",
            title="Game B",
            assets=[
                Asset(
                    asset_type=AssetType.VIDEO,
                    file_path=root / "snes" / "b.mp4",
                    verification_state=AssetVerificationState.VERIFIED_EXISTS,
                )
            ],
        ),
    ]
    nes_roms = [
        Game(
            rom_path=root / "nes" / "c.nes",
            system_id="nes",
            title="Game C",
            assets=[
                Asset(
                    asset_type=AssetType.BOX_FRONT,
                    file_path=root / "nes" / "c.png",
                    verification_state=AssetVerificationState.VERIFIED_EXISTS,
                )
            ],
        ),
    ]
    return Library(
        source_root=root,
        systems=systems,
        games_by_system={"snes": snes_roms, "nes": nes_roms},
    )


class GameListViewModelTests(unittest.TestCase):
    def test_filtered_keys_all_systems_any_assets(self) -> None:
        lib = _make_library()
        vm = GameListViewModel(lib)
        keys = vm.filtered_keys("All Systems", "Any Assets")
        self.assertEqual(len(keys), 3)
        self.assertEqual(len(set(keys)), 3)

    def test_filtered_keys_one_system(self) -> None:
        lib = _make_library()
        vm = GameListViewModel(lib)
        keys = vm.filtered_keys("snes", "Any Assets")
        self.assertEqual(len(keys), 2)
        for k in keys:
            self.assertTrue(k.startswith("snes::"))

    def test_filtered_keys_has_video(self) -> None:
        lib = _make_library()
        vm = GameListViewModel(lib)
        keys = vm.filtered_keys("All Systems", "Has Video")
        self.assertEqual(len(keys), 1)
        self.assertIn("b.zip", keys[0])

    def test_filtered_keys_has_images(self) -> None:
        lib = _make_library()
        vm = GameListViewModel(lib)
        keys = vm.filtered_keys("All Systems", "Has Images")
        self.assertEqual(len(keys), 1)
        self.assertIn("c.nes", keys[0])

    def test_filtered_keys_missing_video(self) -> None:
        lib = _make_library()
        vm = GameListViewModel(lib)
        keys = vm.filtered_keys("All Systems", "Missing Video")
        self.assertEqual(len(keys), 0)

    def test_unchecked_asset_tags_are_rendered(self) -> None:
        lib = _make_library()
        vm = GameListViewModel(lib)
        game_a = lib.games_by_system["snes"][0]
        key = _build_key("snes", game_a)
        assets_text = vm.rows_by_key()[key].assets
        self.assertIn("UNCHECKED-IMG", assets_text)
        self.assertIn("UNCHECKED-VID", assets_text)
        self.assertIn("UNCHECKED-MAN", assets_text)

    def test_games_by_key_matches_library(self) -> None:
        lib = _make_library()
        vm = GameListViewModel(lib)
        gbk = vm.games_by_key()
        self.assertEqual(len(gbk), 3)
        for system_id, games in lib.games_by_system.items():
            for g in games:
                key = _build_key(system_id, g)
                self.assertIn(key, gbk)
                self.assertEqual(gbk[key].title, g.title)


class GameListSelectionIntegrityTests(unittest.TestCase):
    """Selection state is key-based; bulk actions and filters must not lose selection."""

    def test_selection_count_after_set_all_and_clear_visible(self) -> None:
        import customtkinter as ctk
        from retrometasync.ui.game_list import GameListPane

        root = ctk.CTk()
        root.withdraw()
        pane = GameListPane(root)
        lib = _make_library()
        pane.set_library(lib)
        # Process chunked insert (small lib = one chunk, scheduled with after(10)).
        for _ in range(5):
            root.update_idletasks()
        self.assertIsNotNone(pane._view_model)
        self.assertEqual(pane.selected_count(), 0)

        pane._set_all_selection(True)
        self.assertEqual(pane.selected_count(), 3)
        selected = pane.get_selected_games()
        self.assertEqual(len(selected["snes"]), 2)
        self.assertEqual(len(selected["nes"]), 1)

        pane._set_visible_selection(False)
        self.assertEqual(pane.selected_count(), 0)

        pane._set_all_selection(True)
        pane._set_visible_selection(False)
        self.assertEqual(pane.selected_count(), 0)

        root.destroy()

    def test_select_visible_then_filter_selection_persists(self) -> None:
        import customtkinter as ctk
        from retrometasync.ui.game_list import GameListPane

        root = ctk.CTk()
        root.withdraw()
        pane = GameListPane(root)
        lib = _make_library()
        pane.set_library(lib)
        for _ in range(5):
            root.update_idletasks()

        pane._set_all_selection(True)
        self.assertEqual(pane.selected_count(), 3)
        pane.system_filter_var.set("snes")
        pane._apply_filter_refresh()
        for _ in range(5):
            root.update_idletasks()
        self.assertEqual(pane.selected_count(), 3)
        selected = pane.get_selected_games()
        self.assertEqual(len(selected["snes"]), 2)
        self.assertEqual(len(selected["nes"]), 1)

        root.destroy()
