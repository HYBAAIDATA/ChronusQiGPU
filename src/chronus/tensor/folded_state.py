"""Selective, reversible folded-state representation for tensor residency.

The representation reuses Chronus's M15 byte-pair transform. Partial reads
reconstruct only the byte pairs covering the requested range; they do not call
the full reconstruction path.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np

from chronus.execution.structural import fold_pair, unfold_pair


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
        folded = bytearray(len(padded))
        for i in range(0, len(padded), 2):
            a, b = fold_pair(padded[i], padded[i + 1])
            folded[i], folded[i + 1] = a, b
        return cls(
            folded=bytes(folded),
            original_length=len(payload),
            source_sha256=hashlib.sha256(payload).hexdigest(),
        )

    @classmethod
    def from_array(cls, value: np.ndarray) -> "ExactFoldState":
        array = np.ascontiguousarray(value)
        state = cls.from_bytes(array.tobytes(order="C"))
        return cls(
            folded=state.folded,
            original_length=state.original_length,
            source_sha256=state.source_sha256,
            dtype=array.dtype.str,
            shape=tuple(int(x) for x in array.shape),
        )

    def _unfold_aligned(self, pair_start: int, pair_stop: int) -> bytes:
        output = bytearray(pair_stop - pair_start)
        out = 0
        for i in range(pair_start, pair_stop, 2):
            a, b = unfold_pair(self.folded[i], self.folded[i + 1])
            output[out], output[out + 1] = a, b
            out += 2
        return bytes(output)

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
