"""Metadata loaders for supported library ecosystems."""

from retrometasync.core.loaders.base import BaseLoader, LoaderInput, LoaderResult
from retrometasync.core.loaders.es_gamelist import ESGamelistLoader
from retrometasync.core.loaders.launchbox_sqlite import LaunchBoxSqliteLoader
from retrometasync.core.loaders.launchbox_xml import LaunchBoxXmlLoader

__all__ = [
    "BaseLoader",
    "LoaderInput",
    "LoaderResult",
    "ESGamelistLoader",
    "LaunchBoxSqliteLoader",
    "LaunchBoxXmlLoader",
]
