"""Aethel shared-memory ingestion queue — pure-Python ABI v1.

Byte-compatible implementation of the native ``mla1517_aethel`` region
(``chronus/mla1517_platform/host/mla1517_aethel.{c,h}``).  A region is an
mmap-backed file laid out as::

    header (0x40 bytes)
        u64  magic       = 0x4D4C413135313741  ("MLA1517A")
        u32  version     = 1
        u32  slot_count
        u64  reserved[6]
    slot[i] (0x80-byte stride), i in [0, slot_count)
        u64  sequence    seqlock: odd = write in flight, even = stable, 0 = empty
        u8   state[64]   MLA1517 state record
        u8   pad[56]

Publication protocol (identical to the C implementation):
    - ``commit`` reads the slot's current sequence ``s``, stores ``s+1``
      (odd) with release ordering, copies the 64-byte state, then stores
      ``s+2`` (even).  Sequence 0 is reserved for "never committed".
    - ``read`` loads the sequence with acquire ordering, snapshots the
      state, then re-loads the sequence; the snapshot is returned only when
      both reads agree and the value is even and non-zero.

Routing and admission (identical to the C implementation):
    - Cassini gate: ``le_i32(state[40:44])`` must be +1 or -1, else the
      record is rejected.
    - D7 routing: ``slot = le_u32(state[28:32]) % slot_count``.

On POSIX both implementations map the same backing file, so a queue written
by ``libmla1517`` can be drained by this class and vice versa.  Within one
process the seqlock protocol additionally tolerates concurrent Python
readers/writers.
"""

from __future__ import annotations

import mmap
import os
import struct
from dataclasses import dataclass
from typing import Optional, Union

from .constants import (
    AETHEL_ABI_VERSION,
    AETHEL_D10_OFFSET,
    AETHEL_D7_OFFSET,
    AETHEL_HEADER_BYTES,
    AETHEL_MAGIC,
    AETHEL_SLOT_STRIDE,
    STATE_BYTES,
)
from .costs import OverheadMeter, metered
from .errors import AbiVersionMismatch, AethelError, SegmentMissing

_HEADER = struct.Struct("<QII6Q")
_SEQ = struct.Struct("<Q")
_D7 = struct.Struct("<I")
_D10 = struct.Struct("<i")

PathLike = Union[str, os.PathLike]


@dataclass(frozen=True)
class AethelRecord:
    """One stable slot snapshot."""

    slot_id: int
    sequence: int
    state: bytes


class AethelQueue:
    """mmap-backed seqlock slot queue (Aethel shared-memory ABI v1).

    ``AethelQueue(path, n)`` mirrors ``mla1517_aethel_open``: the region is
    created when absent.  ``AethelQueue.attach(path, n)`` is the attach-only
    form used by consumers that must never silently create fresh state —
    it raises :class:`SegmentMissing` when the region does not exist.
    """

    def __init__(self, path: PathLike, slot_count: int, *, create: bool = True):
        if slot_count <= 0:
            raise ValueError("slot_count must be positive")
        self._path = os.fspath(path)
        self._slot_count = int(slot_count)
        self._bytes = AETHEL_HEADER_BYTES + self._slot_count * AETHEL_SLOT_STRIDE

        if not create and not os.path.exists(self._path):
            raise SegmentMissing(f"aethel region {self._path!r} does not exist")

        flags = os.O_RDWR | (os.O_CREAT if create else 0)
        self._costs = OverheadMeter()
        self._fd = os.open(self._path, flags, 0o600)
        try:
            size = os.fstat(self._fd).st_size
            if size == 0:
                if not create:
                    raise SegmentMissing(
                        f"aethel region {self._path!r} is an empty segment"
                    )
                os.ftruncate(self._fd, self._bytes)
            elif size != self._bytes:
                raise AethelError(
                    f"aethel region {self._path!r} is {size} bytes; "
                    f"expected {self._bytes} for slot_count={slot_count}"
                )
            self._mmap = mmap.mmap(self._fd, self._bytes)
        except Exception:
            os.close(self._fd)
            raise

        try:
            magic, version, stored_slots = struct.unpack_from("<QII", self._mmap, 0)
            if magic == 0:
                _HEADER.pack_into(
                    self._mmap, 0, AETHEL_MAGIC, AETHEL_ABI_VERSION, self._slot_count,
                    0, 0, 0, 0, 0, 0,
                )
                self._mmap.flush(0, AETHEL_HEADER_BYTES)
            elif magic != AETHEL_MAGIC:
                raise AethelError(
                    f"aethel region magic mismatch: 0x{magic:016X} != "
                    f"0x{AETHEL_MAGIC:016X}"
                )
            elif version != AETHEL_ABI_VERSION:
                raise AbiVersionMismatch(
                    f"aethel ABI version {version} != {AETHEL_ABI_VERSION}"
                )
            elif stored_slots != self._slot_count:
                raise AethelError(
                    f"aethel region slot_count {stored_slots} != "
                    f"{self._slot_count}"
                )
        except Exception:
            self._mmap.close()
            os.close(self._fd)
            raise

    @classmethod
    def attach(cls, path: PathLike, slot_count: int) -> "AethelQueue":
        """Attach to an existing region; SegmentMissing when absent."""
        return cls(path, slot_count, create=False)

    # -- introspection ------------------------------------------------------

    @property
    def path(self) -> str:
        return self._path

    @property
    def slot_count(self) -> int:
        return self._slot_count

    @property
    def region_bytes(self) -> int:
        return self._bytes

    # -- admission ------------------------------------------------------------

    @staticmethod
    def cassini_valid(state: bytes) -> bool:
        """The D10 Cassini gate: seal must be exactly +1 or -1."""
        if len(state) != STATE_BYTES:
            return False
        seal = _D10.unpack_from(state, AETHEL_D10_OFFSET)[0]
        return seal == 1 or seal == -1

    def slot_for(self, state: bytes) -> int:
        """D7-selected slot for a candidate state."""
        if len(state) != STATE_BYTES:
            raise ValueError(f"state must be {STATE_BYTES} bytes")
        d7 = _D7.unpack_from(state, AETHEL_D7_OFFSET)[0]
        return d7 % self._slot_count

    # -- commit / read --------------------------------------------------------

    @metered("shm.commit")
    def commit(self, state: Union[bytes, bytearray, memoryview]) -> Optional[int]:
        """Commit one 64-byte state to its D7-selected slot.

        Returns the committed slot id, or ``None`` when the record is
        rejected by the Cassini gate.  ``ValueError`` is raised for
        malformed input.  Thread-safe under the seqlock protocol; readers
        never observe a torn record.
        """
        state = bytes(state)
        if len(state) != STATE_BYTES:
            raise ValueError(f"state must be {STATE_BYTES} bytes")
        if not self.cassini_valid(state):
            return None
        slot_id = self.slot_for(state)
        base = AETHEL_HEADER_BYTES + slot_id * AETHEL_SLOT_STRIDE
        current = _SEQ.unpack_from(self._mmap, base)[0]
        # Recovery: an odd sequence means a previous writer died mid-commit;
        # its torn record is discarded and the sequence is advanced past it.
        in_flight = current + 1 if current % 2 == 0 else current + 2
        stable = in_flight + 1
        if stable > 0xFFFFFFFFFFFFFFFF:
            in_flight, stable = 1, 2  # wrap; sequence 0 stays "empty"
        _SEQ.pack_into(self._mmap, base, in_flight)  # odd: write in flight
        self._mmap[base + 8 : base + 8 + STATE_BYTES] = state
        _SEQ.pack_into(self._mmap, base, stable)  # even: stable
        return slot_id

    @metered("shm.read")
    def read(self, slot_id: int, *, retries: int = 8) -> Optional[AethelRecord]:
        """Read a stable snapshot from one slot.

        Returns ``None`` when the slot is empty or the seqlock never settled
        within ``retries`` attempts — a torn record is always discarded,
        never surfaced.  ``ValueError`` for an out-of-range slot.
        """
        if not 0 <= slot_id < self._slot_count:
            raise ValueError(f"slot_id must be in [0, {self._slot_count})")
        base = AETHEL_HEADER_BYTES + slot_id * AETHEL_SLOT_STRIDE
        for _ in range(max(1, retries)):
            seq1 = _SEQ.unpack_from(self._mmap, base)[0]
            if seq1 == 0:
                return None
            if seq1 & 1:
                continue
            snapshot = bytes(self._mmap[base + 8 : base + 8 + STATE_BYTES])
            seq2 = _SEQ.unpack_from(self._mmap, base)[0]
            if seq1 == seq2 and not (seq2 & 1):
                return AethelRecord(slot_id=slot_id, sequence=seq2, state=snapshot)
        return None

    # -- overhead ------------------------------------------------------------

    def structural_bytes(self) -> int:
        """Mapped region size — the real memory footprint of the queue."""
        return self._bytes

    def overhead_report(self) -> dict:
        """Measured CPU/wall cost per op plus the mapped region size."""
        return {
            "operations": self._costs.snapshot(),
            "region_bytes": self._bytes,
            "structural_bytes": self.structural_bytes(),
            "slot_count": self._slot_count,
            "truth": "measured",
        }

    # -- lifecycle ------------------------------------------------------------

    def flush(self) -> None:
        self._mmap.flush()

    def close(self) -> None:
        if getattr(self, "_mmap", None) is not None:
            self._mmap.flush()
            self._mmap.close()
            self._mmap = None  # type: ignore[assignment]
        if getattr(self, "_fd", None) is not None and self._fd >= 0:
            os.close(self._fd)
            self._fd = -1

    def __enter__(self) -> "AethelQueue":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def __del__(self) -> None:  # pragma: no cover - best-effort cleanup
        try:
            self.close()
        except Exception:
            pass


__all__ = [
    "AETHEL_ABI_VERSION",
    "AETHEL_D10_OFFSET",
    "AETHEL_D7_OFFSET",
    "AETHEL_HEADER_BYTES",
    "AETHEL_MAGIC",
    "AETHEL_SLOT_STRIDE",
    "STATE_BYTES",
    "AethelQueue",
    "AethelRecord",
]
