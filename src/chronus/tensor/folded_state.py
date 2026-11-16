"""Selective, reversible folded-state representation for tensor residency.

Reuses Chronus's M15 byte-pair transform (integers mod 256 — reversible
mapping, not compression and not cryptographic authentication). Partial
reads reconstruct only the byte pairs covering the requested range; they
do not call the full reconstruction path. Byte ratio is reported, never
as a compression or speedup claim.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np

from functools import lru_cache


@lru_cache(maxsize=1)
def _pair_luts() -> tuple[np.ndarray, np.ndarray]:
    """Complete M15 and inverse tables over the exact 65,536 byte-pair domain.

    All arithmetic uses uint32 before modular reduction to avoid intermediary
    overflow. The tables are read-only and are created once per process.
    This is a NumPy CPU execution, NOT a GPU instruction or compression codec.
    """
    pairs = np.arange(1 << 16, dtype=np.uint32)
    first, second = pairs >> 8, pairs & 255
    folded = ((((219 * first + 98 * second) & 255) << 8) |
              ((98 * first + 121 * second) & 255)).astype(np.uint16)
    unfolded = ((((135 * first + 98 * second) & 255) << 8) |
                ((98 * first + 37 * second) & 255)).astype(np.uint16)
    folded.flags.writeable = False
    unfolded.flags.writeable = False
    return folded, unfolded


def _map_pairs(payload: bytes, *, inverse: bool) -> bytes:
    """Transform only the supplied even-length aligned range, without expansion."""
    if len(payload) % 2:
        raise ValueError("byte-pair map requires even-length aligned input")
    if not payload:
        return b""
    values = np.frombuffer(payload, dtype=np.uint8).reshape(-1, 2)
    indices = ((values[:, 0].astype(np.uint16) << 8) |
               values[:, 1].astype(np.uint16))
    mapped = _pair_luts()[1 if inverse else 0][indices]
    result = np.empty(len(payload), dtype=np.uint8)
    result[0::2] = (mapped >> 8).astype(np.uint8)
    result[1::2] = mapped.astype(np.uint8)
    return result.tobytes()




@dataclass(frozen=True)
class ExactFoldState:
    folded: bytes
    original_length: int
    source_sha256: str
    dtype: str | None = None
    shape: tuple[int, ...] | None = None

    @classmethod
    def from_bytes(cls, payload: bytes) -> "ExactFoldState":
        if not isinstance(payload, bytes) or not payload:
            raise ValueError("payload must be non-empty bytes")
        padded = payload if len(payload) % 2 == 0 else payload + b"\x00"
        return cls(
            folded=_map_pairs(padded, inverse=False),
            original_length=len(payload),
            source_sha256=hashlib.sha256(payload).hexdigest(),
        )

    @classmethod
    def from_array(cls, value: np.ndarray) -> "ExactFoldState":
        array = np.ascontiguousarray(value)
        if array.dtype.hasobject or array.dtype.fields is not None:
            raise ValueError("folded arrays require a numeric dtype without object pointers or structured fields")
        state = cls.from_bytes(array.tobytes(order="C"))
        return cls(
            folded=state.folded,
            original_length=state.original_length,
            source_sha256=state.source_sha256,
            dtype=array.dtype.str,
            shape=tuple(int(x) for x in array.shape),
        )

    def _unfold_aligned(self, pair_start: int, pair_stop: int) -> bytes:
        return _map_pairs(self.folded[pair_start:pair_stop], inverse=True)

    def unfold(self) -> bytes:
        raw = self._unfold_aligned(0, len(self.folded))[: self.original_length]
        if hashlib.sha256(raw).hexdigest() != self.source_sha256:
            raise ValueError("folded-state reconstruction digest mismatch")
        return raw

    def unfold_partial(self, start: int, stop: int) -> bytes:
        if (
            not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(stop, int)
            or isinstance(stop, bool)
            or start < 0
            or stop < start
            or stop > self.original_length
        ):
            raise ValueError("partial range must satisfy 0 <= start <= stop <= length")
        if start == stop:
            return b""
        pair_start = (start // 2) * 2
        pair_stop = ((stop + 1) // 2) * 2
        raw = self._unfold_aligned(pair_start, pair_stop)
        offset = start - pair_start
        return raw[offset : offset + (stop - start)]

    def unfold_array(self) -> np.ndarray:
        if self.dtype is None or self.shape is None:
            raise TypeError("state does not carry an array contract")
        return np.frombuffer(self.unfold(), dtype=np.dtype(self.dtype)).reshape(self.shape).copy()

    def unfold_rows(self, start: int, stop: int) -> np.ndarray:
        if self.dtype is None or self.shape is None or len(self.shape) < 1:
            raise TypeError("state does not carry an array contract")
        rows = self.shape[0]
        if start < 0 or stop < start or stop > rows:
            raise ValueError("row range outside array")
        row_width = int(np.prod(self.shape[1:], dtype=np.int64)) if len(self.shape) > 1 else 1
        row_bytes = row_width * np.dtype(self.dtype).itemsize
        raw = self.unfold_partial(start * row_bytes, stop * row_bytes)
        return np.frombuffer(raw, dtype=np.dtype(self.dtype)).reshape((stop - start, *self.shape[1:])).copy()

    @property
    def representation_sha256(self) -> str:
        return hashlib.sha256(self.folded).hexdigest()

    @property
    def byte_ratio(self) -> float:
        # This transform is reversible but not a byte-compression claim.
        return self.original_length / max(1, len(self.folded))
