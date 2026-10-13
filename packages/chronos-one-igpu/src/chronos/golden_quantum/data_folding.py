"""Reversible numerical preconditioning and lossless physical byte storage."""
import zlib
import numpy as np
from .constants import GoldenConstants
class GoldenTransform:
    def forward(self, values):
        a = np.asarray(values, dtype=np.complex128)
        if not 1 <= a.ndim <= 3 or not a.size or not np.isfinite(a).all(): raise ValueError("finite 1D/2D/3D array required")
        phase = np.exp(1j * GoldenConstants().golden_angle * np.arange(a.size)).reshape(a.shape)
        return a * phase
    def inverse(self, values):
        a = np.asarray(values, dtype=np.complex128)
        if not 1 <= a.ndim <= 3 or not a.size or not np.isfinite(a).all(): raise ValueError("finite 1D/2D/3D array required")
        phase = np.exp(-1j * GoldenConstants().golden_angle * np.arange(a.size)).reshape(a.shape)
        return a * phase
class DataFoldingEngine:
    MAX_BYTES = 16 * 1024 * 1024
    def fold(self, data):
        if not isinstance(data, bytes) or len(data) > self.MAX_BYTES: raise ValueError("bounded bytes required")
        return zlib.compress(data)
    def unfold(self, data):
        if not isinstance(data, bytes) or len(data) > self.MAX_BYTES: raise ValueError("bounded compressed bytes required")
        decoder = zlib.decompressobj()
        out = decoder.decompress(data, self.MAX_BYTES + 1)
        if len(out) > self.MAX_BYTES or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ValueError("invalid or oversized compressed state")
        return out
