"""Safe C-side seqlock reader for the MLA1517 telemetry ABI."""

from __future__ import annotations

import ctypes
import os
from typing import Any

TELEMETRY_MAGIC = 0x5A1A1517
TELEMETRY_VERSION = 3
TELEMETRY_SIZE = 960
OFF_MAGIC = 0
OFF_VERSION = 8
OFF_SEQ = 16
OFF_PARTITIONS = 64
OFF_VOIDS = 320
OFF_ACCEPTED = 384
OFF_FAULTS = 448
OFF_DROPS = 704
OFF_QUERY_FAULTS = 768
OFF_RING_OVERFLOWS = 832
OFF_CATASTROPHIC = 896


class TelemetrySnapshotError(RuntimeError):
    """Raised when the C reader cannot obtain a coherent ABI snapshot."""


class TelemetryReader:
    """Use the native C seqlock reader; never expose a live mmap to Python."""

    def __init__(
        self, path: str | os.PathLike[str], library: str | os.PathLike[str] | None = None
    ) -> None:
        self.path = os.fspath(path)
        lib_path = os.fspath(
            library or os.getenv("MLA1517_MMIO_LIBRARY", "./host/libmla1517_mmio.so")
        )
        self.lib = ctypes.CDLL(lib_path)
        self.lib.mla1517_telemetry_size.restype = ctypes.c_size_t
        self.lib.mla1517_telemetry_snapshot.argtypes = [
            ctypes.c_char_p,
            ctypes.c_void_p,
            ctypes.c_size_t,
        ]
        self.lib.mla1517_telemetry_snapshot.restype = ctypes.c_int
        size = int(self.lib.mla1517_telemetry_size())
        if size != TELEMETRY_SIZE:
            raise TelemetrySnapshotError(
                f"telemetry ABI size mismatch: C={size}, Python={TELEMETRY_SIZE}"
            )
        self.size = size

    def read(self) -> dict[str, Any]:
        raw = (ctypes.c_ubyte * self.size)()
        status = int(self.lib.mla1517_telemetry_snapshot(self.path.encode(), raw, self.size))
        if status != 0:
            raise TelemetrySnapshotError(
                f"coherent telemetry snapshot unavailable: status={status}"
            )
        data = bytes(raw)
        magic = int.from_bytes(data[OFF_MAGIC : OFF_MAGIC + 8], "little")
        version = int.from_bytes(data[OFF_VERSION : OFF_VERSION + 4], "little")
        if magic != TELEMETRY_MAGIC or version != TELEMETRY_VERSION:
            raise TelemetrySnapshotError(
                f"telemetry ABI mismatch: magic={magic:#x}, version={version}"
            )

        def u64(off: int) -> int:
            return int.from_bytes(data[off : off + 8], "little")

        return {
            "seq": u64(OFF_SEQ),
            "hashes_tested": [u64(OFF_PARTITIONS + i * 8) for i in range(32)],
            "total_tests": sum(u64(OFF_PARTITIONS + i * 8) for i in range(32)),
            "voids_found": u64(OFF_VOIDS),
            "shares_accepted": u64(OFF_ACCEPTED),
            "cassini_faults": [u64(OFF_FAULTS + i * 8) for i in range(32)],
            "stratum_drops": u64(OFF_DROPS),
            "query_cassini_faults": u64(OFF_QUERY_FAULTS),
            "ring_overflows": u64(OFF_RING_OVERFLOWS),
            "catastrophic_overflows": u64(OFF_CATASTROPHIC),
        }


def read_telemetry(path: str | os.PathLike[str]) -> dict[str, Any]:
    return TelemetryReader(path).read()
