"""ctypes query boundary for the native Aethel/PRIME-DB vertex store.

The C library scans mapped vertex files and invokes the callback only for
states matching the D5 mask.  Python therefore receives matches, not the
full mapped dataset.  This is a control-plane binding, not a claim that
callbacks are zero-cost or that mmap implies NVMe durability.
"""

from __future__ import annotations

import ctypes as C
import os
from pathlib import Path
from typing import Any

STATE_BYTES = 64
VERTEX_COUNT = 20


class MLA1517State(C.Structure):
    _fields_ = [
        ("d1_nonce", C.c_uint64),
        ("d2_lucas", C.c_uint32),
        ("d3_pisot", C.c_uint32),
        ("d4_fib", C.c_uint32),
        ("d5_zeckendorf", C.c_uint32),
        ("d6_binet", C.c_uint32),
        ("d7_prime_addr", C.c_uint32),
        ("d8_route", C.c_uint32),
        ("d9_eigen", C.c_uint32),
        ("d10_cassini", C.c_int32),
        ("d11_time_state", C.c_uint32),
        ("d12_gauge", C.c_uint32),
        ("reserved1", C.c_uint32),
        ("reserved2", C.c_uint32),
        ("reserved3", C.c_uint32),
    ]


if C.sizeof(MLA1517State) != STATE_BYTES:
    raise RuntimeError("MLA1517State ctypes layout is not 64 bytes")

MatchCallback = C.CFUNCTYPE(
    C.c_int,
    C.c_uint32,
    C.c_uint64,
    C.POINTER(MLA1517State),
    C.c_void_p,
)


def _library_path(path: str | os.PathLike[str] | None) -> Path:
    if path:
        return Path(path)
    configured = os.getenv("MLA1517_PRIMEDB_LIBRARY")
    if configured:
        return Path(configured)
    return Path(__file__).parents[1] / "mla1517_platform" / "host" / "libprimedb_storage.so"


class NativePrimeDB:
    """Native vertex-store query/commit adapter."""

    def __init__(
        self,
        data_dir: str | os.PathLike[str],
        *,
        capacity_per_vertex: int = 4096,
        library_path: str | os.PathLike[str] | None = None,
    ) -> None:
        path = _library_path(library_path)
        try:
            self._lib = C.CDLL(str(path))
        except OSError as exc:
            raise RuntimeError(f"cannot load PRIME-DB library {path}: {exc}") from exc
        handle_t = C.c_void_p
        self._lib.primedb_storage_open.argtypes = [C.c_char_p, C.c_uint64]
        self._lib.primedb_storage_open.restype = handle_t
        self._lib.primedb_storage_close.argtypes = [handle_t]
        self._lib.primedb_storage_close.restype = None
        self._lib.primedb_storage_commit.argtypes = [
            handle_t,
            C.POINTER(MLA1517State),
            C.POINTER(C.c_uint32),
            C.POINTER(C.c_uint64),
        ]
        self._lib.primedb_storage_commit.restype = C.c_int
        self._lib.primedb_storage_query_d5.argtypes = [
            handle_t,
            C.c_uint32,
            C.c_uint32,
            MatchCallback,
            C.c_void_p,
            C.POINTER(C.c_uint64),
        ]
        self._lib.primedb_storage_query_d5.restype = C.c_int
        if capacity_per_vertex <= 0:
            raise ValueError("capacity_per_vertex must be positive")
        self._handle = self._lib.primedb_storage_open(
            os.fspath(data_dir).encode(), capacity_per_vertex
        )
        if not self._handle:
            raise RuntimeError(f"unable to open PRIME-DB data directory {data_dir}")

    def commit(self, state: MLA1517State) -> tuple[int, int]:
        vertex = C.c_uint32()
        slot = C.c_uint64()
        result = self._lib.primedb_storage_commit(
            self._handle, C.byref(state), C.byref(vertex), C.byref(slot)
        )
        if result == 0:
            raise ValueError("state rejected by the Cassini gate")
        if result < 0:
            raise RuntimeError("PRIME-DB vertex capacity exhausted")
        return int(vertex.value), int(slot.value)

    def find_resonant_blocks(
        self,
        vertex_id: int,
        d5_mask: int,
        *,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        if not 0 <= vertex_id < VERTEX_COUNT:
            raise ValueError("vertex_id must be in [0, 19]")
        if not 0 <= d5_mask <= 0xFFFFFFFF:
            raise ValueError("d5_mask must be a uint32")
        results: list[dict[str, Any]] = []

        def on_match(
            _vertex: int,
            slot: int,
            pointer: C.POINTER(MLA1517State),
            _context: int,
        ) -> int:
            state = pointer.contents
            results.append(
                {
                    "vertex_id": int(_vertex),
                    "slot_id": int(slot),
                    "nonce": int(state.d1_nonce),
                    "zeckendorf": int(state.d5_zeckendorf),
                    "prime_addr": int(state.d7_prime_addr),
                    "cassini": int(state.d10_cassini),
                    "time_state": int(state.d11_time_state),
                }
            )
            return 1 if limit is not None and len(results) >= limit else 0

        callback = MatchCallback(on_match)
        matches = C.c_uint64()
        result = self._lib.primedb_storage_query_d5(
            self._handle,
            vertex_id,
            d5_mask,
            callback,
            None,
            C.byref(matches),
        )
        if result != 0:
            raise RuntimeError("PRIME-DB resonance query failed")
        return results

    def close(self) -> None:
        if self._handle:
            self._lib.primedb_storage_close(self._handle)
            self._handle = None

    def __enter__(self) -> "NativePrimeDB":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
