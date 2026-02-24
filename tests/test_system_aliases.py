from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from retrometasync.config.system_aliases import canonicalize_system_id, expand_search_tokens


class SystemAliasTests(unittest.TestCase):
    def test_canonicalize_common_aliases(self) -> None:
        self.assertEqual(canonicalize_system_id("Nintendo 64"), "n64")
        self.assertEqual(canonicalize_system_id("gc"), "gamecube")
        self.assertEqual(canonicalize_system_id("SEGA_CD"), "segacd")
        self.assertEqual(canonicalize_system_id("PlayStation Portable"), "psp")
        self.assertEqual(canonicalize_system_id("Amiga CD32"), "amigacd32")
        self.assertEqual(canonicalize_system_id("Sega Genesis"), "genesis")

    def test_expand_search_tokens_for_alias_id(self) -> None:
        tokens = set(expand_search_tokens("commodore_amiga_cd32"))
        self.assertIn("amiga cd32", tokens)
        self.assertIn("cd32", tokens)
        self.assertIn("amigacd32", tokens)


if __name__ == "__main__":
    unittest.main()
