"""Tests for game list ViewModel and selection integrity (high-scale UI plan)."""
from __future__ import annotations

from datetime import datetime
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
from retrometasync.core.asset_verifier import verify_unchecked_assets
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
            genres=["Action", "Platform"],
            rating=4.5,
            release_date=datetime(1991, 1, 1),
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

    def test_rating_genre_year_fields_are_mapped(self) -> None:
        lib = _make_library()
        vm = GameListViewModel(lib)
        game_c = lib.games_by_system["nes"][0]
        key = _build_key("nes", game_c)
        row = vm.rows_by_key()[key]
        self.assertEqual(row.rating, "4.5")
        self.assertEqual(row.year, "1991")
        self.assertIn("Action", row.genre)
        self.assertIn("Platform", row.genre)


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

    def test_tree_has_new_columns_and_horizontal_scroll(self) -> None:
        import customtkinter as ctk
        from retrometasync.ui.game_list import GameListPane

        root = ctk.CTk()
        root.withdraw()
        pane = GameListPane(root)
        pane.set_library(_make_library())
        for _ in range(5):
            root.update_idletasks()

        self.assertIn("rating", pane._tree["columns"])
        self.assertIn("genre", pane._tree["columns"])
        self.assertIn("year", pane._tree["columns"])
        self.assertTrue(bool(pane._tree.cget("xscrollcommand")))

        root.destroy()

    def test_check_unchecked_visible_uses_callback_without_changing_selection(self) -> None:
        import customtkinter as ctk
        from retrometasync.ui.game_list import GameListPane

        root = ctk.CTk()
        root.withdraw()
        pane = GameListPane(root)
        lib = _make_library()
        pane.set_library(lib)
        for _ in range(5):
            root.update_idletasks()

        called = {"count": 0}

        def on_check() -> None:
            called["count"] += 1

        pane._set_all_selection(True)
        before = pane.selected_count()
        pane.set_on_check_unchecked_visible(on_check)
        pane._handle_check_unchecked_visible()
        self.assertEqual(called["count"], 1)
        self.assertEqual(pane.selected_count(), before)

        root.destroy()

    def test_search_enter_filters_by_title_within_visible_subset(self) -> None:
        import customtkinter as ctk
        from retrometasync.ui.game_list import GameListPane

        root = ctk.CTk()
        root.withdraw()
        pane = GameListPane(root)
        pane.set_library(_make_library())
        for _ in range(5):
            root.update_idletasks()

        pane.system_filter_var.set("snes")
        pane._apply_filter_refresh()
        pane.search_filter_var.set("game b")
        pane._on_search_enter(None)
        for _ in range(5):
            root.update_idletasks()

        self.assertEqual(len(pane._visible_keys), 1)
        self.assertTrue(pane._visible_keys[0].startswith("snes::"))
        self.assertIn("b.zip", pane._visible_keys[0])

        root.destroy()

    def test_search_enter_filters_by_filename_case_insensitive(self) -> None:
        import customtkinter as ctk
        from retrometasync.ui.game_list import GameListPane

        root = ctk.CTk()
        root.withdraw()
        pane = GameListPane(root)
        pane.set_library(_make_library())
        for _ in range(5):
            root.update_idletasks()

        pane.search_filter_var.set("C.NES")
        pane._on_search_enter(None)
        for _ in range(5):
            root.update_idletasks()

        self.assertEqual(len(pane._visible_keys), 1)
        self.assertIn("c.nes", pane._visible_keys[0])

        root.destroy()

    def test_search_empty_restores_current_filter_rows(self) -> None:
        import customtkinter as ctk
        from retrometasync.ui.game_list import GameListPane

        root = ctk.CTk()
        root.withdraw()
        pane = GameListPane(root)
        pane.set_library(_make_library())
        for _ in range(5):
            root.update_idletasks()

        pane.system_filter_var.set("snes")
        pane._apply_filter_refresh()
        for _ in range(5):
            root.update_idletasks()
        self.assertEqual(len(pane._visible_keys), 2)

        pane.search_filter_var.set("game a")
        pane._on_search_enter(None)
        for _ in range(5):
            root.update_idletasks()
        self.assertEqual(len(pane._visible_keys), 1)

        pane.search_filter_var.set("")
        pane._on_search_enter(None)
        for _ in range(5):
            root.update_idletasks()
        self.assertEqual(len(pane._visible_keys), 2)

        root.destroy()

    def test_search_applies_within_asset_filtered_visible_list(self) -> None:
        import customtkinter as ctk
        from retrometasync.ui.game_list import GameListPane

        root = ctk.CTk()
        root.withdraw()
        pane = GameListPane(root)
        pane.set_library(_make_library())
        for _ in range(5):
            root.update_idletasks()

        pane.asset_filter_var.set("Has Video")
        pane._apply_filter_refresh()
        for _ in range(5):
            root.update_idletasks()
        self.assertEqual(len(pane._visible_keys), 1)
        self.assertIn("b.zip", pane._visible_keys[0])

        pane.search_filter_var.set("game c")
        pane._on_search_enter(None)
        for _ in range(5):
            root.update_idletasks()
        self.assertEqual(len(pane._visible_keys), 0)

        pane.search_filter_var.set("b.zip")
        pane._on_search_enter(None)
        for _ in range(5):
            root.update_idletasks()
        self.assertEqual(len(pane._visible_keys), 1)
        self.assertIn("b.zip", pane._visible_keys[0])

        root.destroy()

    def test_refresh_asset_states_for_keys_updates_asset_tags(self) -> None:
        import customtkinter as ctk
        import tempfile
        from retrometasync.ui.game_list import GameListPane

        with tempfile.TemporaryDirectory() as temp_dir:
            root_dir = Path(temp_dir)
            rom_path = root_dir / "test.rom"
            rom_path.write_bytes(b"rom")
            image_path = root_dir / "image.png"
            image_path.write_bytes(b"img")
            missing_video_path = root_dir / "video.mp4"

            game = Game(
                rom_path=rom_path,
                system_id="snes",
                title="Test Game",
                assets=[
                    Asset(asset_type=AssetType.BOX_FRONT, file_path=image_path),
                    Asset(asset_type=AssetType.VIDEO, file_path=missing_video_path),
                ],
            )
            system = System(
                system_id="snes",
                display_name="SNES",
                rom_root=root_dir,
                metadata_source=MetadataSource.GAMELIST_XML,
            )
            library = Library(source_root=root_dir, systems={"snes": system}, games_by_system={"snes": [game]})

            root = ctk.CTk()
            root.withdraw()
            pane = GameListPane(root)
            pane.set_library(library)
            for _ in range(5):
                root.update_idletasks()

            key = pane.visible_unchecked_game_keys()[0]
            before_assets = pane._view_model.rows_by_key()[key].assets  # type: ignore[union-attr]
            self.assertIn("UNCHECKED-IMG", before_assets)
            self.assertIn("UNCHECKED-VID", before_assets)

            verify_unchecked_assets(game)
            pane.refresh_asset_states_for_keys([key])
            for _ in range(5):
                root.update_idletasks()
            after_assets = pane._view_model.rows_by_key()[key].assets  # type: ignore[union-attr]
            self.assertIn("IMG", after_assets)
            self.assertIn("NO-VID", after_assets)
            self.assertNotIn("UNCHECKED-IMG", after_assets)
            self.assertNotIn("UNCHECKED-VID", after_assets)

        root.destroy()

    def test_visible_system_scope_changes_with_filters(self) -> None:
        import customtkinter as ctk
        from retrometasync.ui.game_list import GameListPane

        root = ctk.CTk()
        root.withdraw()
        pane = GameListPane(root)
        pane.set_library(_make_library())
        for _ in range(5):
            root.update_idletasks()

        self.assertFalse(pane.has_active_filters())
        self.assertEqual(set(pane.visible_system_ids()), {"nes", "snes"})

        pane.system_filter_var.set("snes")
        pane._apply_filter_refresh()
        for _ in range(5):
            root.update_idletasks()
        self.assertTrue(pane.has_active_filters())
        self.assertEqual(pane.visible_system_ids(), ["snes"])

        root.destroy()
