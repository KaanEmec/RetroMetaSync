from __future__ import annotations

from retrometasync.core.loaders.base import BaseLoader, LoaderInput, LoaderResult


class LaunchBoxSqliteLoader(BaseLoader):
    ecosystem = "launchbox"

    def load(self, load_input: LoaderInput) -> LoaderResult:
        # Phase 3 keeps SQLite support as a planned extension.
        return LoaderResult(
            systems=list(load_input.systems),
            games_by_system={system.system_id: [] for system in load_input.systems},
            warnings=["LaunchBox SQLite loading is not implemented yet."],
        )

