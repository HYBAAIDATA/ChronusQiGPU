"""Small ctypes writer for out-of-band MLA1517 telemetry counters."""

from __future__ import annotations

import ctypes as C
import os
from pathlib import Path


class TelemetryWriter:
    """Increment producer counters without adding logging or socket work."""

    def __init__(
        self,
        path: str | os.PathLike[str],
        library_path: str | os.PathLike[str] | None = None,
    ) -> None:
        library = library_path or os.getenv("MLA1517_MMIO_LIBRARY")
        if not library:
            library = Path(__file__).parents[2] / "host" / "libmla1517_mmio.so"
        self._lib = C.CDLL(str(library))
        handle_t = C.c_void_p
        self._lib.mla1517_telemetry_open.argtypes = [C.c_char_p]
        self._lib.mla1517_telemetry_open.restype = handle_t
        self._lib.mla1517_telemetry_close.argtypes = [handle_t]
        self._lib.mla1517_telemetry_close.restype = None
        self._lib.mla1517_telemetry_add_accepted.argtypes = [handle_t, C.c_uint64]
        self._lib.mla1517_telemetry_add_accepted.restype = None
        self._handle = self._lib.mla1517_telemetry_open(os.fspath(path).encode())
        if not self._handle:
            raise RuntimeError(f"unable to open telemetry block {path!s}")

    def add_accepted(self, amount: int = 1) -> None:
        if amount < 0:
            raise ValueError("amount must be non-negative")
        self._lib.mla1517_telemetry_add_accepted(self._handle, amount)

    def close(self) -> None:
        if self._handle:
            self._lib.mla1517_telemetry_close(self._handle)
            self._handle = None
