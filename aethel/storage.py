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
import re
import stat
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .costs import OverheadMeter, container_bytes, metered
from .errors import (
    AethelError,
    GapDetected,
    InvalidAddress,
    SegmentMissing,
    StorageCorruption,
)
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
MAX_PAYLOAD_BYTES = 16 * 1024 * 1024
MAX_ADDRESS_INDEX = 20_000
MAX_LEDGER_ENTRIES = 250_000
MAX_JOURNAL_BYTES = 256 * 1024 * 1024
_DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")


def _validate_directory(path: Path, *, create: bool = False) -> None:
    if path.is_symlink():
        raise StorageCorruption("storage directory must not be a symlink")
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        info = path.lstat()
    except FileNotFoundError as exc:
        raise SegmentMissing("storage directory does not exist") from exc
    if not stat.S_ISDIR(info.st_mode):
        raise StorageCorruption("storage path is not a directory")
    if os.name != "nt" and info.st_mode & 0o077:
        raise StorageCorruption("storage directory must be private to its owner")
    if hasattr(os, "geteuid") and info.st_uid != os.geteuid():
        raise StorageCorruption("storage directory is not owned by this user")


def _validate_regular_file(path: Path, *, required: bool = True) -> Optional[os.stat_result]:
    try:
        info = path.lstat()
    except FileNotFoundError:
        if required:
            raise SegmentMissing("storage file is missing")
        return None
    if not stat.S_ISREG(info.st_mode):
        raise StorageCorruption("storage entry is not a regular file")
    if os.name != "nt" and info.st_mode & 0o077:
        raise StorageCorruption("storage file must be private to its owner")
    if hasattr(os, "geteuid") and info.st_uid != os.geteuid():
        raise StorageCorruption("storage file is not owned by this user")
    return info


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        # Windows does not permit opening directories via os.open; directory
        # durability relies on the file-level fsync in _atomic_write.
        return
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_write(path: Path, data: bytes) -> None:
    if len(data) > MAX_JOURNAL_BYTES:
        raise StorageCorruption("journal size limit exceeded")
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _entry_from_record(record: object, expected_seq: int) -> LedgerEntry:
    if not isinstance(record, dict):
        raise StorageCorruption("journal record must be an object")
    required = {"seq", "index", "value", "quadruple", "digest"}
    if not required.issubset(record) or set(record) - required - {"writer"}:
        raise StorageCorruption("journal record fields are invalid")
    integer_fields = ("seq", "index", "value")
    if any(
        not isinstance(record.get(field), int) or isinstance(record[field], bool)
        for field in integer_fields
    ):
        raise StorageCorruption("journal integer field is invalid")
    writer = record.get("writer", 0)
    if not isinstance(writer, int) or isinstance(writer, bool) or writer < 0:
        raise StorageCorruption("journal writer field is invalid")
    quadruple = record["quadruple"]
    if (
        not isinstance(quadruple, list)
        or len(quadruple) != 4
        or any(not isinstance(q, int) or isinstance(q, bool) for q in quadruple)
    ):
        raise StorageCorruption("journal Cassini witness is invalid")
    digest = record["digest"]
    if not isinstance(digest, str) or not _DIGEST_RE.fullmatch(digest):
        raise StorageCorruption("journal digest is invalid")
    if record["seq"] != expected_seq:
        raise GapDetected("journal sequence is not contiguous")
    if not 1 <= record["index"] <= MAX_ADDRESS_INDEX:
        raise StorageCorruption("journal index is outside the supported range")
    return LedgerEntry(
        seq=record["seq"],
        index=record["index"],
        value=record["value"],
        quadruple=tuple(quadruple),
        digest=digest,
        writer=writer,
    )


@dataclass(frozen=True)
class FibonacciAddress:
    """An address in the storage layer: Fibonacci index + value pair.

    Invariants: ``value == fibonacci(index)`` and ``index >= 1``.
    """

    index: int
    value: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.index, int)
            or isinstance(self.index, bool)
            or not 1 <= self.index <= MAX_ADDRESS_INDEX
        ):
            raise InvalidAddress(
                f"Fibonacci index must be in [1, {MAX_ADDRESS_INDEX}]"
            )
        if not isinstance(self.value, int) or isinstance(self.value, bool):
            raise InvalidAddress("Fibonacci address value must be an integer")
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
        self._lock = threading.RLock()
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
        if (
            not isinstance(index, int)
            or isinstance(index, bool)
            or index < 1
            or index > MAX_ADDRESS_INDEX
        ):
            raise InvalidAddress(
                f"Fibonacci index must be in [1, {MAX_ADDRESS_INDEX}]"
            )
        if not isinstance(writer, int) or isinstance(writer, bool) or writer < 0:
            raise InvalidAddress("writer id must be a non-negative integer")
        if value is None:
            value = fibonacci(index)
        elif (
            not isinstance(value, int)
            or isinstance(value, bool)
            or not is_fibonacci(value)
            or value != fibonacci(index)
        ):
            raise InvalidAddress(
                f"forged index/value pair: ({index}, {value}) is not on the "
                "true Fibonacci sequence"
            )
        with self._lock:
            if len(self._entries) >= MAX_LEDGER_ENTRIES:
                raise StorageCorruption("ledger entry limit exceeded")
            last_index = self._last_index.get(writer, 0)
            if index <= last_index:
                raise InvalidAddress(
                    f"index {index} regressed behind writer {writer}'s "
                    f"last index {last_index}"
                )
            if index in self._by_index:
                raise InvalidAddress(f"index {index} is already committed")
            if not isinstance(digest, str) or not _DIGEST_RE.fullmatch(digest):
                raise InvalidAddress("digest must be a lowercase SHA-256 hex string")
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
        seen_indices = set()
        for position, entry in enumerate(self._entries):
            if (
                not isinstance(entry.seq, int)
                or isinstance(entry.seq, bool)
                or entry.seq != position
            ):
                raise GapDetected(
                    f"ledger stream broken at position {position}: "
                    f"entry seq {entry.seq} != {position}"
                )
            if (
                not isinstance(entry.index, int)
                or isinstance(entry.index, bool)
                or not isinstance(entry.value, int)
                or isinstance(entry.value, bool)
                or not 1 <= entry.index <= MAX_ADDRESS_INDEX
                or entry.value != fibonacci(entry.index)
            ):
                raise InvalidAddress(
                    f"forged ledger entry at position {position}: "
                    f"fibonacci({entry.index}) != {entry.value}"
                )
            if (
                entry.quadruple != cassini_quadruple(entry.index)
                or not cassini_holds(entry.quadruple)
            ):
                raise InvalidAddress(
                    f"cassini quadruple invalid at position {position}"
                )
            if not isinstance(entry.digest, str) or not _DIGEST_RE.fullmatch(
                entry.digest
            ):
                raise InvalidAddress(f"digest invalid at position {position}")
            if entry.index in seen_indices:
                raise InvalidAddress(f"duplicate index at position {position}")
            seen_indices.add(entry.index)
            if (
                not isinstance(entry.writer, int)
                or isinstance(entry.writer, bool)
                or entry.writer < 0
            ):
                raise InvalidAddress(f"invalid writer at position {position}")
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
        max_payload_bytes: int = MAX_PAYLOAD_BYTES,
        writer: int = 0,
        ledger: Optional[CassiniLedger] = None,
        blocks: Optional[Dict[int, bytes]] = None,
    ) -> None:
        if (
            not isinstance(max_step, int)
            or isinstance(max_step, bool)
            or not 1 <= max_step <= MAX_ADDRESS_INDEX
        ):
            raise ValueError(f"max_step must be in [1, {MAX_ADDRESS_INDEX}]")
        if (
            not isinstance(max_payload_bytes, int)
            or isinstance(max_payload_bytes, bool)
            or not 0 <= max_payload_bytes <= MAX_PAYLOAD_BYTES
        ):
            raise ValueError(
                f"max_payload_bytes must be in [0, {MAX_PAYLOAD_BYTES}]"
            )
        if (
            not isinstance(start_index, int)
            or isinstance(start_index, bool)
            or not 1 <= start_index <= MAX_ADDRESS_INDEX + 1
        ):
            raise ValueError(
                f"start_index must be in [1, {MAX_ADDRESS_INDEX + 1}]"
            )
        self.max_step = int(max_step)
        self.max_payload_bytes = int(max_payload_bytes)
        if not isinstance(writer, int) or isinstance(writer, bool) or writer < 0:
            raise ValueError("writer id must be a non-negative integer")
        self.writer = writer
        self.ledger = ledger if ledger is not None else CassiniLedger()
        self._blocks = blocks if blocks is not None else {}
        # The last index this writer committed; the next write lands at
        # ``_cursor + advance`` — the bounded-advance rule of contract A5.
        self._cursor = max(0, start_index - 1)
        self._lock = self.ledger._lock
        self._costs = OverheadMeter()
        self._metrics = {
            "writes": 0,
            "reads": 0,
            "rejections": 0,
            "corruptions": 0,
            "bytes_written": 0,
            "bytes_read": 0,
        }

    def _payload(self, payload: bytes) -> bytes:
        if not isinstance(payload, (bytes, bytearray, memoryview)):
            raise TypeError("payload must be bytes-like")
        size = payload.nbytes if isinstance(payload, memoryview) else len(payload)
        if size > self.max_payload_bytes:
            raise StorageCorruption("payload size limit exceeded")
        return bytes(payload)

    # -- writes -------------------------------------------------------------

    @metered("space.write")
    def write(self, payload: bytes, advance: int = 1) -> FibonacciAddress:
        """Place a block at ``cursor + advance`` on the Fibonacci sequence.

        Raises InvalidAddress when ``advance`` exceeds ``max_step`` or the
        resulting index regresses.  Postcondition: a Cassini quadruple for
        the new index is appended to the ledger.
        """
        import hashlib

        try:
            if (
                not isinstance(advance, int)
                or isinstance(advance, bool)
                or advance < 1
                or advance > self.max_step
            ):
                raise InvalidAddress(
                    f"advance {advance} exceeds declared bound {self.max_step}"
                )
            payload = self._payload(payload)
            digest = hashlib.sha256(payload).hexdigest()
            with self._lock:
                index = self._cursor + advance
                if index in self.ledger._by_index:
                    index = max(self.ledger._by_index) + 1
                    if index - self._cursor > self.max_step:
                        raise InvalidAddress(
                            "writer index collides with a committed address"
                        )
                entry = self.ledger.append(index, digest, writer=self.writer)
                self._blocks[index] = payload
                self._cursor = index
                self._metrics["writes"] += 1
                self._metrics["bytes_written"] += len(payload)
        except (AethelError, TypeError, ValueError):
            with self._lock:
                self._metrics["rejections"] += 1
            raise
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

        try:
            payload = self._payload(payload)
            digest = hashlib.sha256(payload).hexdigest()
            with self._lock:
                entry = self.ledger.append(
                    index, digest, writer=self.writer, value=value
                )
                self._blocks[index] = payload
                if index > self._cursor:
                    self._cursor = index
                self._metrics["writes"] += 1
                self._metrics["bytes_written"] += len(payload)
        except (AethelError, TypeError, ValueError):
            with self._lock:
                self._metrics["rejections"] += 1
            raise
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
            max_payload_bytes=self.max_payload_bytes,
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
            "metrics": dict(self._metrics),
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
        if not isinstance(index, int) or isinstance(index, bool) or not (
            1 <= index <= MAX_ADDRESS_INDEX
        ):
            raise InvalidAddress(
                f"Fibonacci index must be in [1, {MAX_ADDRESS_INDEX}]"
            )
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
        import hashlib

        with self._lock:
            self._metrics["reads"] += 1
            try:
                if not isinstance(address, FibonacciAddress):
                    raise InvalidAddress("read requires a FibonacciAddress")
                self.ledger.check_consistent()
                entry = self.ledger.index_of(address.index)
                if entry is None:
                    raise GapDetected(f"index {address.index} is not in the ledger")
                block = self._blocks.get(address.index)
                if block is None:
                    raise GapDetected(f"block at index {address.index} is missing")
                if not isinstance(block, bytes) or len(block) > self.max_payload_bytes:
                    raise StorageCorruption(
                        "stored payload exceeds configured size limit"
                    )
                if hashlib.sha256(block).hexdigest() != entry.digest:
                    raise StorageCorruption("stored payload digest mismatch")
                self._metrics["bytes_read"] += len(block)
                return block
            except AethelError as exc:
                self._metrics["rejections"] += 1
                if isinstance(exc, StorageCorruption):
                    self._metrics["corruptions"] += 1
                raise

    def verify(self) -> bool:
        """Full storage-side integrity check: ledger + every block present."""
        import hashlib

        with self._lock:
            if not self.ledger.verify_ledger():
                return False
            return all(
                entry.index in self._blocks
                and isinstance(self._blocks[entry.index], bytes)
                and len(self._blocks[entry.index]) <= self.max_payload_bytes
                and hashlib.sha256(self._blocks[entry.index]).hexdigest()
                == entry.digest
                for entry in self.ledger.entries
            )

    # -- persistence ----------------------------------------------------------

    @metered("space.snapshot")
    def snapshot(self, directory: PathLike) -> None:
        """Durably publish blocks before atomically publishing their journal."""
        import hashlib

        directory = Path(directory)
        _validate_directory(directory, create=True)
        blocks_dir = directory / BLOCKS_DIR
        _validate_directory(blocks_dir, create=True)
        with self._lock:
            self.ledger.check_consistent()
            entries = tuple(self.ledger.entries)
            for entry in entries:
                payload = self._blocks.get(entry.index)
                if payload is None:
                    raise GapDetected(f"block at index {entry.index} is missing")
                if (
                    not isinstance(payload, bytes)
                    or len(payload) > self.max_payload_bytes
                    or hashlib.sha256(payload).hexdigest() != entry.digest
                ):
                    raise StorageCorruption("block failed size or digest validation")
                block_path = blocks_dir / f"{entry.index}.blk"
                _validate_regular_file(block_path, required=False)
                _atomic_write(block_path, payload)

            journal = directory / JOURNAL_NAME
            _validate_regular_file(journal, required=False)
            fd, temporary = tempfile.mkstemp(
                prefix=f".{JOURNAL_NAME}.", dir=directory
            )
            try:
                total = 0
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    for entry in entries:
                        line = json.dumps(
                            {
                                "seq": entry.seq,
                                "index": entry.index,
                                "value": entry.value,
                                "quadruple": list(entry.quadruple),
                                "digest": entry.digest,
                                "writer": entry.writer,
                            },
                            separators=(",", ":"),
                        ) + "\n"
                        total += len(line.encode("utf-8"))
                        if total > MAX_JOURNAL_BYTES:
                            raise StorageCorruption("journal size limit exceeded")
                        handle.write(line)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, journal)
                _fsync_directory(directory)
            except Exception:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass
                raise
        logger.info("snapshot: %d entries, %d blocks", len(entries), len(entries))

    @classmethod
    def attach(cls, directory: PathLike, **kwargs) -> "AddressSpace":
        """Replay only a complete, bounded journal whose every block verifies."""
        import hashlib

        directory = Path(directory)
        _validate_directory(directory)
        journal = directory / JOURNAL_NAME
        journal_info = _validate_regular_file(journal)
        if journal_info is None or journal_info.st_size > MAX_JOURNAL_BYTES:
            raise StorageCorruption("journal exceeds the configured size limit")
        blocks_dir = directory / BLOCKS_DIR
        _validate_directory(blocks_dir)
        max_payload_bytes = kwargs.get("max_payload_bytes", MAX_PAYLOAD_BYTES)
        if (
            not isinstance(max_payload_bytes, int)
            or isinstance(max_payload_bytes, bool)
            or not 0 <= max_payload_bytes <= MAX_PAYLOAD_BYTES
        ):
            raise ValueError(
                f"max_payload_bytes must be in [0, {MAX_PAYLOAD_BYTES}]"
            )

        ledger = CassiniLedger()
        blocks: Dict[int, bytes] = {}
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(journal, flags)
        with os.fdopen(fd, "rb") as handle:
            journal_stat = os.fstat(handle.fileno())
            if (
                not stat.S_ISREG(journal_stat.st_mode)
                or journal_stat.st_size > MAX_JOURNAL_BYTES
            ):
                raise StorageCorruption("journal is not a bounded regular file")
            journal_bytes = 0
            for line_no, raw_line in enumerate(handle, start=1):
                journal_bytes += len(raw_line)
                if (
                    len(ledger.entries) >= MAX_LEDGER_ENTRIES
                    or len(raw_line) > 64 * 1024
                    or journal_bytes > MAX_JOURNAL_BYTES
                    or not raw_line.endswith(b"\n")
                ):
                    raise StorageCorruption(
                        f"invalid or truncated journal at line {line_no}"
                    )
                try:
                    record = json.loads(raw_line.decode("utf-8"))
                    entry = _entry_from_record(record, len(ledger.entries))
                except (UnicodeDecodeError, json.JSONDecodeError, StorageCorruption,
                        GapDetected) as exc:
                    raise StorageCorruption(
                        f"corrupt ledger journal at line {line_no}"
                    ) from exc

                block_path = blocks_dir / f"{entry.index}.blk"
                block_info = _validate_regular_file(block_path)
                if block_info is None or block_info.st_size > max_payload_bytes:
                    raise StorageCorruption("stored block exceeds size limit")
                block_fd = os.open(block_path, flags)
                with os.fdopen(block_fd, "rb") as block_handle:
                    actual = os.fstat(block_handle.fileno())
                    if not stat.S_ISREG(actual.st_mode) or actual.st_size > max_payload_bytes:
                        raise StorageCorruption("stored block is not a bounded file")
                    payload = block_handle.read(max_payload_bytes + 1)
                if hashlib.sha256(payload).hexdigest() != entry.digest:
                    raise StorageCorruption("stored block digest mismatch")
                ledger.entries.append(entry)
                blocks[entry.index] = payload

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

    @classmethod
    def truncate_to_last_consistent_prefix(cls, directory: PathLike) -> int:
        """Back up the journal and remove its invalid suffix; never repairs data."""
        import hashlib

        directory = Path(directory)
        _validate_directory(directory)
        journal = directory / JOURNAL_NAME
        info = _validate_regular_file(journal)
        if info is None or info.st_size > MAX_JOURNAL_BYTES:
            raise StorageCorruption("journal exceeds the configured size limit")
        blocks_dir = directory / BLOCKS_DIR
        _validate_directory(blocks_dir)
        prefix: List[LedgerEntry] = []
        seen_indices = set()
        last_per_writer: Dict[int, int] = {}
        journal_bytes = 0
        try:
            with journal.open("rb") as handle:
                for raw_line in handle:
                    journal_bytes += len(raw_line)
                    if (
                        len(prefix) >= MAX_LEDGER_ENTRIES
                        or journal_bytes > MAX_JOURNAL_BYTES
                        or len(raw_line) > 64 * 1024
                        or not raw_line.endswith(b"\n")
                    ):
                        break
                    try:
                        entry = _entry_from_record(
                            json.loads(raw_line.decode("utf-8")), len(prefix)
                        )
                        if entry.index in seen_indices:
                            break
                        previous = last_per_writer.get(entry.writer, 0)
                        if entry.index <= previous:
                            break
                        if entry.quadruple != cassini_quadruple(entry.index):
                            break
                        block_path = blocks_dir / f"{entry.index}.blk"
                        block_info = _validate_regular_file(block_path)
                        if block_info is None or block_info.st_size > MAX_PAYLOAD_BYTES:
                            break
                        payload = block_path.read_bytes()
                        if hashlib.sha256(payload).hexdigest() != entry.digest:
                            break
                    except (OSError, UnicodeDecodeError, json.JSONDecodeError,
                            StorageCorruption, GapDetected, TypeError, ValueError):
                        break
                    prefix.append(entry)
                    seen_indices.add(entry.index)
                    last_per_writer[entry.writer] = entry.index
        except OSError as exc:
            raise StorageCorruption("unable to read journal for recovery") from exc

        backup = directory / f"{JOURNAL_NAME}.bak"
        suffix = 0
        while backup.exists():
            suffix += 1
            backup = directory / f"{JOURNAL_NAME}.bak.{suffix}"
        backup_fd = os.open(
            backup,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            source_fd = os.open(
                journal, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            )
        except Exception:
            os.close(backup_fd)
            os.unlink(backup)
            raise
        with os.fdopen(source_fd, "rb") as source, os.fdopen(
            backup_fd, "wb"
        ) as target:
            copied = 0
            while chunk := source.read(1024 * 1024):
                copied += len(chunk)
                if copied > MAX_JOURNAL_BYTES:
                    raise StorageCorruption("journal exceeded its size limit")
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
        _fsync_directory(directory)
        journal_bytes = b"".join(
            (
                json.dumps(
                    {
                        "seq": entry.seq,
                        "index": entry.index,
                        "value": entry.value,
                        "quadruple": list(entry.quadruple),
                        "digest": entry.digest,
                        "writer": entry.writer,
                    },
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")
            for entry in prefix
        )
        _atomic_write(journal, journal_bytes)
        return len(prefix)


PathLike = os.PathLike | str


__all__ = [
    "AddressSpace",
    "CassiniLedger",
    "DEFAULT_MAX_STEP",
    "FibonacciAddress",
    "LedgerEntry",
]
