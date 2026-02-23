"""Core domain and processing modules for RetroMetaSync."""

from retrometasync.core.conversion import ConversionEngine, ConversionRequest, ConversionResult
from retrometasync.core.detection import DetectionResult, LibraryDetector
from retrometasync.core.normalizer import LibraryNormalizer, NormalizationResult

__all__ = [
    "ConversionEngine",
    "ConversionRequest",
    "ConversionResult",
    "DetectionResult",
    "LibraryDetector",
    "LibraryNormalizer",
    "NormalizationResult",
]
