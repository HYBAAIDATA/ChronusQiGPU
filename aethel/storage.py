"""Aethel storage layer — Fibonacci address space + Cassini ledger.

The address space is the Fibonacci sequence: block ``k`` committed by a
writer occupies index ``n_k`` and is addressed by ``F_{n_k}``.  Per writer
the index stream is strictly increasing; a single write advances the index
by at most ``max_step`` Fibonacci steps.

Every address transition appends a Cassini quadruple
``(F_{n-1}, F_n, F_{n+1}, (-1)^n)`` to the ledger.
``verify_ledger()`` returns True iff every quadruple satisfies
``F_{n-1} * F_{n+1} - F_n^2 == (-1)^n``, every recorded value equals the
true ``fibonacci(index)``, the global write sequence is contiguous, and
each writer's index stream is strictly increasing.

This module owns *placement and integrity of the address space only*.
Retrieval and search belong to the geodesic engine (see
``aethel.geodesic``); this layer merely hands it a well-formed manifold.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .costs import OverheadMeter, container_bytes, metered
from .errors import AethelError, GapDetected, InvalidAddress, SegmentMissing
from .fibonacci import (
    cassini_holds,
    cassini_quadruple,
    fibonacci,
    fibonacci_index,
    is_fibonacci,
)

logger = logging.getLogger("aethel.storage")

DEFAULT_MAX_STEP = 4
JOURNAL_NAME = "ledger.jsonl"
BLOCKS_DIR = "blocks"


@dataclass(frozen=True)
class FibonacciAddress:
    """An address in the storage layer: Fibonacci index + value pair.

    Invariants: ``value == fibonacci(index)`` and ``index >= 1``.
    """

    index: int
    value: int

    def __post_init__(self) -> None:
        if self.index < 1:
            raise InvalidAddress(f"Fibonacci index must be >= 1, got {self.index}")
        if fibonacci(self.index) != self.value:
            raise InvalidAddress(
                f"forged address: fibonacci({self.index}) != {self.value}"
            )


@dataclass(frozen=True)
class LedgerEntry:
    """One committed address transition.

    ``seq`` is the global write order; ``index``/``value`` the Fibonacci
    address; ``quadruple`` the Cassini witness; ``digest`` the SHA-256 hex
    of the stored payload; ``writer`` the writer id.
    """

    seq: int
    index: int
    value: int
    quadruple: Tuple[int, int, int, int]
    digest: str
    writer: int = 0


class CassiniLedger:
    """Append-only ledger of Cassini-certified address transitions.

    Thread-safe: append/verify serialise on an internal lock.  The ledger
    is the single source of truth for gap and forgery detection — reads
    consult it before any payload is returned.
    """

    def __init__(self) -> None:
        self._entries: List[LedgerEntry] = []
        self._last_index: Dict[int, int] = {}
        # Per-writer rolling Fibonacci tail: (index, F_{n-1}, F_n, F_{n+1}).
        # Sequential appends roll forward with one integer addition instead
        # of three fast-doubling evaluations — the quadruple stored in each
        # entry is identical either way.
        self._tail: Dict[int, Tuple[int, int, int, int]] = {}
        self._by_index: Dict[int, LedgerEntry] = {}
        self._lock = threading.Lock()
        self._costs = OverheadMeter()

    @property
    def entries(self) -> List[LedgerEntry]:
        """The raw entry list (tests may corrupt it; reads detect it)."""
        return self._entries

    @metered("ledger.append")
    def append(
        self,
        index: int,
        digest: str,
        *,
        writer: int = 0,
        value: Optional[int] = None,
    ) -> LedgerEntry:
        """Append one transition.  Raises InvalidAddress on a forged or
        non-monotonic index.

        Precondition: ``index >= 1``; per-writer index strictly increasing;
        ``value``, if given, must equal ``fibonacci(index)``.
        Postcondition: ``entries[-1].seq == len(entries) - 1``.
        """
        if index < 1:
            raise InvalidAddress(f"Fibonacci index must be >= 1, got {index}")
        if value is None:
            value = fibonacci(index)
        elif not is_fibonacci(value) or value != fibonacci(index):
            raise InvalidAddress(
                f"forged index/value pair: ({index}, {value}) is not on the "
                "true Fibonacci sequence"
            )
        with self._lock:
            last_index = self._last_index.get(writer, 0)
            if index <= last_index:
                raise InvalidAddress(
                    f"index {index} regressed behind writer {writer}'s "
                    f"last index {last_index}"
                )
            tail = self._tail.get(writer)
            if tail is not None and index == tail[0] + 1:
                _i, _p, f_n, f_next = tail
                quadruple = (f_n, f_next, f_n + f_next, (-1) ** index)
            else:
                quadruple = cassini_quadruple(index)
            self._tail[writer] = (index, quadruple[0], quadruple[1], quadruple[2])
            entry = LedgerEntry(
                seq=len(self._entries),
                index=index,
                value=value,
                quadruple=quadruple,
                digest=digest,
                writer=writer,
            )
            self._entries.append(entry)
            self._last_index[writer] = index
            self._by_index[index] = entry
        logger.debug("ledger append seq=%d index=%d writer=%d", entry.seq, index, writer)
        return entry

    @metered("ledger.check_consistent")
    def check_consistent(self) -> None:
        """Raise GapDetected/InvalidAddress if the stream is corrupt.

        Runs the same checks as ``verify_ledger`` but raises typed errors —
        the gate every read passes through before returning payload bytes.
        """
        last_per_writer: Dict[int, int] = {}
        for position, entry in enumerate(self._entries):
            if entry.seq != position:
                raise GapDetected(
                    f"ledger stream broken at position {position}: "
                    f"entry seq {entry.seq} != {position}"
                )
            if entry.index < 1 or entry.value != fibonacci(entry.index):
                raise InvalidAddress(
                    f"forged ledger entry at position {position}: "
                    f"fibonacci({entry.index}) != {entry.value}"
                )
            if not cassini_holds(entry.quadruple):
                raise InvalidAddress(
                    f"cassini quadruple invalid at position {position}"
                )
            prev = last_per_writer.get(entry.writer)
            if prev is not None and entry.index <= prev:
                raise InvalidAddress(
                    f"writer {entry.writer} index regressed: "
                    f"{entry.index} <= {prev}"
                )
            last_per_writer[entry.writer] = entry.index

    def verify_ledger(self) -> bool:
        """True iff every quadruple satisfies the Cassini identity, the
        sequence is contiguous, and per-writer indices strictly increase."""
        try:
            self.check_consistent()
        except (GapDetected, InvalidAddress):
            return False
        return True

    @metered("ledger.index_of")
    def index_of(self, index: int) -> Optional[LedgerEntry]:
        entry = self._by_index.get(index)
        if entry is None:
            # Rebuild: the raw list may have been repaired after corruption.
            self._by_index = {e.index: e for e in self._entries}
            entry = self._by_index.get(index)
        return entry

    def __len__(self) -> int:
        return len(self._entries)

    def structural_bytes(self) -> int:
        """Measured structural memory of the ledger (a floor — allocator
        slack and page tables are not visible to ``sys.getsizeof``)."""
        return (
            container_bytes(self._entries)
            + container_bytes(self._last_index)
            + container_bytes(self._tail)
            + container_bytes(self._by_index)
        )

    def overhead_report(self) -> Dict[str, object]:
        """Measured CPU/wall cost per operation plus structural memory."""
        return {
            "operations": self._costs.snapshot(),
            "structural_bytes": self.structural_bytes(),
            "entries": len(self._entries),
            "writers": len(self._last_index),
            "truth": "measured",
        }


class AddressSpace:
    """Fibonacci-indexed block store gated by a Cassini ledger.

    Precondition for ``write``: payload is bytes; ``advance`` in
    ``[1, max_step]``.  Postcondition: the returned address satisfies
    ``fibonacci(address.index) == address.value`` and the ledger holds a
    valid quadruple for the transition.

    Thread-safety: writes serialise on an internal lock; concurrent
    writers should use ``fork()`` so each holds a private cursor over a
    shared ledger and block map.
    """

    def __init__(
        self,
        *,
        max_step: int = DEFAULT_MAX_STEP,
        start_index: int = 1,
        writer: int = 0,
        ledger: Optional[CassiniLedger] = None,
        blocks: Optional[Dict[int, bytes]] = None,
    ) -> None:
        if max_step < 1:
            raise ValueError("max_step must be positive")
        self.max_step = int(max_step)
        self.writer = int(writer)
        self.ledger = ledger if ledger is not None else CassiniLedger()
        self._blocks = blocks if blocks is not None else {}
        # The last index this writer committed; the next write lands at
        # ``_cursor + advance`` — the bounded-advance rule of contract A5.
        self._cursor = max(0, start_index - 1)
        self._lock = threading.Lock()
        self._costs = OverheadMeter()

    # -- writes -------------------------------------------------------------

    @metered("space.write")
    def write(self, payload: bytes, advance: int = 1) -> FibonacciAddress:
        """Place a block at ``cursor + advance`` on the Fibonacci sequence.

        Raises InvalidAddress when ``advance`` exceeds ``max_step`` or the
        resulting index regresses.  Postcondition: a Cassini quadruple for
        the new index is appended to the ledger.
        """
        import hashlib

        if advance < 1 or advance > self.max_step:
            raise InvalidAddress(
                f"advance {advance} exceeds declared bound {self.max_step}"
            )
        payload = bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        with self._lock:
            index = self._cursor + advance
            entry = self.ledger.append(index, digest, writer=self.writer)
            self._blocks[index] = payload
            self._cursor = index
        self._costs.record_bytes("space.write", len(payload))
        logger.debug(
            "block placed index=%d value=%d bytes=%d", index, entry.value, len(payload)
        )
        return FibonacciAddress(index, entry.value)

    @metered("space.register")
    def register(self, index: int, value: int, payload: bytes) -> FibonacciAddress:
        """Explicitly place a block at a declared (index, value) address.

        The ledger rejects any pair that is not on the true Fibonacci
        sequence — the forgery gate.
        """
        import hashlib

        digest = hashlib.sha256(bytes(payload)).hexdigest()
        with self._lock:
            entry = self.ledger.append(
                index, digest, writer=self.writer, value=value
            )
            self._blocks[index] = payload
            if index > self._cursor:
                self._cursor = index
        self._costs.record_bytes("space.register", len(payload))
        return FibonacciAddress(entry.index, entry.value)

    def fork(self, writer: int, *, start_index: Optional[int] = None) -> "AddressSpace":
        """Return an independent writer sharing this space's ledger/blocks.

        Precondition: ``writer`` differs from this writer's id.
        Postcondition: writes through the fork keep the shared ledger's
        global sequence contiguous while the fork's own index stream is
        strictly increasing.
        """
        if writer == self.writer:
            raise ValueError("fork requires a distinct writer id")
        return AddressSpace(
            max_step=self.max_step,
            start_index=start_index if start_index is not None else self._cursor + 1,
            writer=writer,
            ledger=self.ledger,
            blocks=self._blocks,
        )

    # -- overhead ------------------------------------------------------------

    def structural_bytes(self) -> int:
        """Measured structural memory: block payloads + shared ledger."""
        return container_bytes(self._blocks) + self.ledger.structural_bytes()

    def overhead_report(self) -> Dict[str, object]:
        """Measured CPU/wall cost per space op plus the shared ledger's."""
        return {
            "operations": self._costs.snapshot(),
            "ledger": self.ledger.overhead_report(),
            "structural_bytes": self.structural_bytes(),
            "blocks": len(self._blocks),
            "truth": "measured",
        }

    # -- reads ---------------------------------------------------------------

    def address_of(self, value: int) -> FibonacciAddress:
        """Resolve a Fibonacci value to its address; InvalidAddress if forged."""
        index = fibonacci_index(value)
        if index is None or index < 1:
            raise InvalidAddress(f"{value} is not a Fibonacci address value")
        return FibonacciAddress(index, value)

    def address_of_index(self, index: int) -> FibonacciAddress:
        """Resolve a ledger index to its address; InvalidAddress when the
        index is not committed (a read on it would be a gap)."""
        if index < 1:
            raise InvalidAddress(f"Fibonacci index must be >= 1, got {index}")
        if self.ledger.index_of(index) is None:
            raise GapDetected(f"index {index} is not committed")
        return FibonacciAddress(index, fibonacci(index))

    @metered("space.read")
    def read(self, address: FibonacciAddress) -> bytes:
        """Return the block at ``address`` after a full ledger-integrity gate.

        Raises GapDetected when the ledger stream is broken or the block is
        missing; InvalidAddress never escapes here because forged addresses
        cannot be constructed.
        """
        self.ledger.check_consistent()
        if self.ledger.index_of(address.index) is None:
            raise GapDetected(f"index {address.index} is not in the ledger")
        block = self._blocks.get(address.index)
        if block is None:
            raise GapDetected(f"block at index {address.index} is missing")
        return block

    def verify(self) -> bool:
        """Full storage-side integrity check: ledger + every block present."""
        if not self.ledger.verify_ledger():
            return False
        return all(entry.index in self._blocks for entry in self.ledger.entries)

    # -- persistence ----------------------------------------------------------

    @metered("space.snapshot")
    def snapshot(self, directory: PathLike) -> None:
        """Persist the ledger (JSONL) and blocks (binary files) atomically."""
        directory = Path(directory)
        blocks_dir = directory / BLOCKS_DIR
        blocks_dir.mkdir(parents=True, exist_ok=True)
        tmp = directory / (JOURNAL_NAME + ".tmp")
        with open(tmp, "w", encoding="utf-8") as handle:
            for entry in self.ledger.entries:
                handle.write(
                    json.dumps(
                        {
                            "seq": entry.seq,
                            "index": entry.index,
                            "value": entry.value,
                            "quadruple": list(entry.quadruple),
                            "digest": entry.digest,
                            "writer": entry.writer,
                        }
                    )
                    + "\n"
                )
        os.replace(tmp, directory / JOURNAL_NAME)
        for index, payload in self._blocks.items():
            (blocks_dir / f"{index}.blk").write_bytes(payload)
        logger.info("snapshot: %d entries, %d blocks", len(self.ledger), len(self._blocks))

    @classmethod
    def attach(cls, directory: PathLike, **kwargs) -> "AddressSpace":
        """Reattach a snapshotted space; SegmentMissing when absent/corrupt.

        The ledger is replayed and fully verified before the space is
        usable — a corrupt journal raises, never truncates.
        """
        directory = Path(directory)
        journal = directory / JOURNAL_NAME
        if not journal.is_file():
            raise SegmentMissing(f"no aethel ledger journal at {journal}")
        ledger = CassiniLedger()
        blocks: Dict[int, bytes] = {}
        blocks_dir = directory / BLOCKS_DIR
        with open(journal, "r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    entry = LedgerEntry(
                        seq=int(record["seq"]),
                        index=int(record["index"]),
                        value=int(record["value"]),
                        quadruple=tuple(int(q) for q in record["quadruple"]),
                        digest=str(record["digest"]),
                        writer=int(record.get("writer", 0)),
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    raise AethelError(
                        f"corrupt ledger journal at line {line_no}: {exc}"
                    ) from exc
                ledger.entries.append(entry)
                block_path = blocks_dir / f"{entry.index}.blk"
                if not block_path.is_file():
                    raise SegmentMissing(
                        f"ledger index {entry.index} has no block file"
                    )
                blocks[entry.index] = block_path.read_bytes()
        # Rebuild per-writer cursors/tails so a resumed writer keeps the
        # strict-monotonicity and rolling-quadruple invariants.
        for entry in ledger.entries:
            ledger._last_index[entry.writer] = max(
                entry.index, ledger._last_index.get(entry.writer, 0)
            )
            ledger._tail[entry.writer] = (
                entry.index,
                entry.quadruple[0],
                entry.quadruple[1],
                entry.quadruple[2],
            )
            ledger._by_index[entry.index] = entry
        space = cls(ledger=ledger, blocks=blocks, **kwargs)
        space.ledger.check_consistent()
        space._cursor = ledger._last_index.get(space.writer, 0)
        logger.info("attach: replayed %d ledger entries", len(ledger))
        return space


PathLike = os.PathLike | str


__all__ = [
    "AddressSpace",
    "CassiniLedger",
    "DEFAULT_MAX_STEP",
    "FibonacciAddress",
    "LedgerEntry",
]
