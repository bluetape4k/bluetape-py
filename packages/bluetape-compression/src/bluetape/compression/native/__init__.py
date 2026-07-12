"""Optional native compression providers."""

from ._lz4 import Lz4Compressor
from ._snappy import SnappyCompressor

__all__ = ["Lz4Compressor", "SnappyCompressor"]
