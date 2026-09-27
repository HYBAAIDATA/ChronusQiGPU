"""Low-overhead ctypes binding for the MLA1517 MMIO/Aethel bridge.

The native library is intentionally small and ABI-stable. Python is the
control/orchestration layer; the C library owns mapped I/O and the 64-byte
state snapshot boundary. The binding never guesses a device path and never
opens /dev/mem implicitly.
"""

from __future__ import annotations

import ctypes as C
import os
from dataclasses import dataclass
from pathlib import Path

STATE_BYTES = 64
MEMORY_NODES = 20


class MLA1517HardwareError(RuntimeError):
    """Raised for MMIO mapping, register, or vault-read failures."""


class _VaultRecord(C.Structure):
    _fields_ = [
        ("node_id", C.c_uint32),
        ("sequence", C.c_uint64),
        ("state", C.c_uint8 * STATE_BYTES),
    ]


@dataclass(frozen=True)
class VaultRecord:
    node_id: int
    sequence: int
    state: bytes


def _load_library(path: str | os.PathLike[str] | None) -> C.CDLL:
    library_path = path or os.getenv("MLA1517_MMIO_LIBRARY")
    if not library_path:
        library_path = Path(__file__).parents[2] / "host" / "libmla1517_mmio.so"
    try:
        library = C.CDLL(str(library_path))
    except OSError as exc:
        raise MLA1517HardwareError(
            f"cannot load MLA1517 MMIO library {library_path!s}: {exc}"
        ) from exc

    device_p = C.c_void_p
    library.mla1517_open.argtypes = [C.c_char_p, C.c_uint64]
    library.mla1517_open.restype = device_p
    library.mla1517_close.argtypes = [device_p]
    library.mla1517_close.restype = None
    library.mla1517_set_difficulty_mask.argtypes = [device_p, C.c_uint32]
    library.mla1517_set_difficulty_mask.restype = C.c_int
    library.mla1517_set_base_step.argtypes = [device_p, C.c_uint64]
    library.mla1517_set_base_step.restype = C.c_int
    library.mla1517_start.argtypes = [device_p]
    library.mla1517_start.restype = C.c_int
    library.mla1517_stop.argtypes = [device_p]
    library.mla1517_stop.restype = C.c_int
    library.mla1517_update_polyhedral_mask.argtypes = [device_p, C.c_uint32]
    library.mla1517_update_polyhedral_mask.restype = C.c_int
    library.mla1517_quarantine_lane.argtypes = [device_p, C.c_uint32, C.c_int]
    library.mla1517_quarantine_lane.restype = C.c_int
    library.mla1517_stage_polyhedral_mask.argtypes = [device_p, C.c_uint32]
    library.mla1517_stage_polyhedral_mask.restype = C.c_int
    library.mla1517_stage_lane_mask.argtypes = [device_p, C.c_uint32]
    library.mla1517_stage_lane_mask.restype = C.c_int
    library.mla1517_request_supervisor_commit.argtypes = [device_p]
    library.mla1517_request_supervisor_commit.restype = C.c_int
    library.mla1517_supervisor_commit_ack.argtypes = [device_p]
    library.mla1517_supervisor_commit_ack.restype = C.c_int
    library.mla1517_poll_vault.argtypes = [
        device_p,
        C.c_int,
        C.POINTER(_VaultRecord),
    ]
    library.mla1517_poll_vault.restype = C.c_int
    library.mla1517_shm_open.argtypes = [C.c_char_p, C.c_uint32]
    library.mla1517_shm_open.restype = device_p
    library.mla1517_shm_close.argtypes = [device_p]
    library.mla1517_shm_close.restype = None
    library.mla1517_poll_vault_to_shm.argtypes = [
        device_p,
        device_p,
        C.c_int,
        C.POINTER(_VaultRecord),
    ]
    library.mla1517_poll_vault_to_shm.restype = C.c_int
    library.mla1517_last_error.argtypes = [device_p]
    library.mla1517_last_error.restype = C.c_uint32
    library.mla1517_last_error_string.argtypes = [device_p]
    library.mla1517_last_error_string.restype = C.c_char_p
    return library


class MMIOBridge:
    """Context-managed host driver for a mapped MLA1517 control/vault region."""

    def __init__(
        self,
        device_path: str | os.PathLike[str],
        *,
        map_bytes: int = 0x2000,
        library_path: str | os.PathLike[str] | None = None,
    ) -> None:
        self._library = _load_library(library_path)
        self._handle = self._library.mla1517_open(os.fspath(device_path).encode(), map_bytes)
        if not self._handle:
            raise MLA1517HardwareError(f"unable to map MLA1517 device {device_path!s}")
        self._ring_handle: C.c_void_p | None = None

    def _check(self, result: int) -> None:
        if result != 0:
            message = self._library.mla1517_last_error_string(self._handle)
            text = message.decode(errors="replace") if message else "unknown error"
            raise MLA1517HardwareError(text)

    def set_difficulty_mask(self, mask: int) -> None:
        if not 0 <= mask <= 0xFFFFFFFF:
            raise ValueError("difficulty mask must be a uint32")
        self._check(self._library.mla1517_set_difficulty_mask(self._handle, mask))

    def set_base_step(self, base_step: int) -> None:
        if not 0 <= base_step <= 0xFFFFFFFFFFFFFFFF:
            raise ValueError("base_step must be a uint64")
        self._check(self._library.mla1517_set_base_step(self._handle, base_step))

    def start(self) -> None:
        self._check(self._library.mla1517_start(self._handle))

    def stop(self) -> None:
        self._check(self._library.mla1517_stop(self._handle))

    def update_polyhedral_mask(self, mask: int) -> None:
        if not 0 <= mask <= 0xFFFFFFFF:
            raise ValueError("polyhedral mask must be a uint32")
        self._check(self._library.mla1517_update_polyhedral_mask(self._handle, mask))

    def quarantine_lane(self, lane_id: int, quarantine: bool = True) -> None:
        if not 0 <= lane_id < 32:
            raise ValueError("lane_id must be in [0, 31]")
        self._check(self._library.mla1517_quarantine_lane(self._handle, lane_id, int(quarantine)))

    def stage_lane_mask(self, mask: int) -> None:
        self._check(self._library.mla1517_stage_lane_mask(self._handle, mask))

    def stage_polyhedral_mask(self, mask: int) -> None:
        self._check(self._library.mla1517_stage_polyhedral_mask(self._handle, mask))

    def request_supervisor_commit(self) -> None:
        self._check(self._library.mla1517_request_supervisor_commit(self._handle))

    def supervisor_commit_ack(self) -> bool:
        return bool(self._library.mla1517_supervisor_commit_ack(self._handle))

    def poll_vault(self, timeout_ms: int = 100) -> VaultRecord | None:
        if timeout_ms < 0:
            raise ValueError("timeout_ms must be non-negative")
        record = _VaultRecord()
        result = self._library.mla1517_poll_vault(self._handle, timeout_ms, C.byref(record))
        if result < 0:
            self._check(result)
        if result == 0:
            return None
        return VaultRecord(
            node_id=int(record.node_id),
            sequence=int(record.sequence),
            state=bytes(record.state),
        )

    def poll_vault_to_ring(
        self,
        ring_path: str | os.PathLike[str],
        timeout_ms: int = 100,
        capacity: int = 1024,
    ) -> VaultRecord | None:
        """Path A + Path B poll with ring backpressure."""
        if self._ring_handle is None:
            self._ring_handle = self._library.mla1517_shm_open(
                os.fspath(ring_path).encode(), capacity
            )
            if not self._ring_handle:
                raise MLA1517HardwareError(f"unable to open PRIME-DB ring {ring_path!s}")
        record = _VaultRecord()
        result = self._library.mla1517_poll_vault_to_shm(
            self._handle,
            self._ring_handle,
            timeout_ms,
            C.byref(record),
        )
        if result < 0:
            self._check(result)
        if result == 0:
            return None
        return VaultRecord(
            node_id=int(record.node_id),
            sequence=int(record.sequence),
            state=bytes(record.state),
        )

    def reset_ring(self) -> None:
        """Close the PRIME-DB ring handle; the next poll reopens it.

        Used by the recovery plane to drain/reset the persistence cursor
        without dropping staged records.
        """
        if self._ring_handle:
            self._library.mla1517_shm_close(self._ring_handle)
            self._ring_handle = None

    def last_error(self) -> int:
        """Observed device error code (0 = no fault)."""
        return int(self._library.mla1517_last_error(self._handle))

    def close(self) -> None:
        if self._ring_handle:
            self._library.mla1517_shm_close(self._ring_handle)
            self._ring_handle = None
        if self._handle:
            self._library.mla1517_close(self._handle)
            self._handle = None

    def __enter__(self) -> "MMIOBridge":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
