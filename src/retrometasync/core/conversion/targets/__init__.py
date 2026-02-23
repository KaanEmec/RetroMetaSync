"""Target-specific output path planning."""

from retrometasync.core.conversion.targets import batocera, es_classic, es_de, launchbox, retrobat

TARGET_MODULES = {
    "batocera": batocera,
    "es_classic": es_classic,
    "es_de": es_de,
    "launchbox": launchbox,
    "retrobat": retrobat,
}
