"""Durable, deterministic mining lifecycle and the Pythia winner-memory API.

Only confirmed pool outcomes enter memory. Learned operators are complete
cyclic permutations of the 32 lanes; neither learning nor state changes
modify a header, target, or proof predicate.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from pathlib import Path

from lucas.ladder import FULL_LADDER
from lucas.fold import t_phi_fold, iter_original_u8

THEOREM_PROVEN = False
EDGES = {
    "SEARCHING": "SUBMITTING",
    "SUBMITTING": "WAITING_EXTERNAL",
    "WAITING_EXTERNAL": "COOLDOWN",
    "COOLDOWN": "SEARCHING",
}
# Bounded so frequent share acceptances cannot grow the persisted session.
WINNER_MEMORY_LIMIT = 256


def digest(header: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(header).digest()).digest()


class PythiaWinnerMemory:
    """Exact winner records and a closed family of discovered lane rotations."""

    def __init__(self, records: list[dict] | None = None) -> None:
        self.records = list(records or [])
        self.primitives: dict[str, tuple[int, ...]] = {}
        for record in self.records:
            self._validate(record)
            self._discover(record)

    @staticmethod
    def _validate(record: dict) -> None:
        folded = bytes.fromhex(record["folded_header"])
        if len(folded) != 80:
            raise ValueError("invalid folded winner length")
        stream_hash = hashlib.sha256()
        nonce = 0
        for index, value in enumerate(iter_original_u8(folded, 80)):
            stream_hash.update(bytes((value,)))
            if index >= 76:
                nonce |= value << (8 * (index - 76))
        proof = hashlib.sha256(stream_hash.digest()).digest()
        if proof[::-1].hex() != record["block_hash"] or nonce != record["nonce"]:
            raise ValueError("invalid winner header/digest")
        target = record["target"]
        if type(target) is not int or not 0 < target < 2**256:
            raise ValueError("invalid winner target")
        if int.from_bytes(proof, "little") > target:
            raise ValueError("winner does not meet recorded target")
        if record["cell_fate"] != "germ_line" or record["accepted"] is not True:
            raise ValueError("unconfirmed winner record")
        if record["raw_buffer_materialized"] is not False:
            raise ValueError("winner memory must remain folded")

    def _discover(self, record: dict) -> None:
        lane = record["nonce"] % 32
        name = f"rotate_lane_{lane}"
        self.primitives[name] = tuple((lane + i) % 32 for i in range(32))

    def consolidate(self, header: bytes, target: int, job_id: str) -> None:
        record = {
            "folded_header": t_phi_fold(header).hex(),
            "nonce": int.from_bytes(header[76:80], "little"),
            "raw_buffer_materialized": False,
            "theorem_proven": False,
            "block_hash": digest(header)[::-1].hex(),
            "target": target,
            "job_id": job_id,
            "accepted": True,
            "cell_fate": "germ_line",
        }
        self._validate(record)
        if any(r["block_hash"] == record["block_hash"] for r in self.records):
            return
        self.records.append(record)
        del self.records[:-WINNER_MEMORY_LIMIT]
        self._discover(record)

    def lane_order(self) -> tuple[int, ...] | None:
        if not self.records:
            return None
        nonce = self.records[-1]["nonce"]
        return self.primitives[f"rotate_lane_{nonce % 32}"]


class MiningSession:
    """One persisted four-state loop; interrupted submissions remain blocked."""

    def __init__(
        self, path: str | Path | None = None, *, cooldown_seconds: float = 1.0, clock=time.time
    ) -> None:
        if not math.isfinite(cooldown_seconds) or cooldown_seconds < 0:
            raise ValueError("cooldown must be finite and non-negative")
        self.path = Path(path) if path is not None else None
        self.clock = clock
        self.cooldown_seconds = cooldown_seconds
        self.state = "SEARCHING"
        self.history = [self.state]
        self.cycles = 0
        self.pending: dict | None = None
        self.external: dict | None = None
        self.cooldown_until: float | None = None
        self.memory = PythiaWinnerMemory()
        self.last_block_hash: str | None = None
        self.last_share: dict | None = None
        self._lock_file = None
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._lock_file = self.path.with_suffix(self.path.suffix + ".lock").open("a+b")
            try:
                _acquire_exclusive_lock(self._lock_file)
                if self.path.exists():
                    self._restore(json.loads(self.path.read_text()))
                self._save()
            except BaseException:
                self.close()
                raise

    @property
    def rung(self) -> int:
        return FULL_LADDER[min(self.cycles, len(FULL_LADDER) - 1)]

    def _restore(self, data: dict) -> None:
        if data.get("version") != 1 or data.get("theorem_proven") is not False:
            raise ValueError("unsupported mining session")
        state = data["state"]
        history = data["history"]
        if (
            state not in EDGES
            or not history
            or history[0] != "SEARCHING"
            or history[-1] != state
            or any(EDGES.get(a) != b for a, b in zip(history, history[1:]))
        ):
            raise ValueError("invalid persisted lifecycle")
        cycles = data["cycles"]
        if type(cycles) is not int or cycles != history.count("SEARCHING") - 1:
            raise ValueError("invalid cycle count")
        self.state, self.history, self.cycles = state, history, cycles
        self.last_block_hash = data.get("last_block_hash")
        if self.last_block_hash is not None and (
            not isinstance(self.last_block_hash, str)
            or len(self.last_block_hash) != 64
            or any(c not in "0123456789abcdef" for c in self.last_block_hash)
        ):
            raise ValueError("invalid last block safety evidence")
        self.pending = data["pending"]
        self.external = data["external"]
        self.cooldown_until = data["cooldown_until"]
        self.last_share = data.get("last_share")
        self.memory = PythiaWinnerMemory(data["winners"])
        if state != "SEARCHING" and not self.pending:
            raise ValueError("active lifecycle is missing submission evidence")
        if state == "COOLDOWN" and (
            not self.external
            or self.cooldown_until is None
            or not math.isfinite(self.cooldown_until)
        ):
            raise ValueError("cooldown evidence missing")
        if self.pending and self.pending.get("outcome") is True:
            self.memory.consolidate(
                bytes.fromhex(self.pending["header"]),
                self.pending["target"],
                self.pending["job_id"],
            )

    def _save(self) -> None:
        if self.path is None:
            return
        payload = {
            "version": 1,
            "state": self.state,
            "history": self.history,
            "cycles": self.cycles,
            "pending": self.pending,
            "external": self.external,
            "cooldown_until": self.cooldown_until,
            "winners": self.memory.records,
            "theorem_proven": False,
            "last_block_hash": self.last_block_hash,
            "last_share": self.last_share,
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)
        if os.name != "nt":  # directory fsync is POSIX-only
            descriptor = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

    def _go(self, state: str) -> None:
        if EDGES.get(self.state) != state:
            raise RuntimeError(f"illegal mining transition: {self.state} -> {state}")
        self.state = state
        self.history.append(state)

    def begin_submission(
        self,
        *,
        header: bytes,
        target: int,
        job_id: str,
        parent_hash: str,
        parent_height: int,
        block_candidate: bool,
        submission_id: str | None = None,
    ) -> None:
        if self.state != "SEARCHING":
            raise RuntimeError("mining lifecycle blocks submission")
        if len(header) != 80 or type(target) is not int or not 0 < target < 2**256:
            raise ValueError("invalid submission proof")
        if int.from_bytes(digest(header), "little") > target:
            raise ValueError("submission is not a winner")
        if (
            type(parent_height) is not int
            or parent_height < 0
            or header[4:36][::-1].hex() != parent_hash
            or type(block_candidate) is not bool
        ):
            raise ValueError("verified chain parent required")
        if parent_hash == self.last_block_hash:
            raise RuntimeError("cannot mine directly on our previous block after a reorg")
        self.pending = {
            "header": header.hex(),
            "target": target,
            "job_id": job_id,
            "block_hash": digest(header)[::-1].hex(),
            "parent_hash": parent_hash,
            "parent_height": parent_height,
            "block_candidate": block_candidate,
            "outcome": None,
            "submission_id": submission_id,
        }
        self._go("SUBMITTING")
        self._save()  # durable before the network write

    def submission_finished(self, accepted: bool | None) -> None:
        if self.state != "SUBMITTING" or self.pending is None:
            raise RuntimeError("no submission in progress")
        if accepted is not None and type(accepted) is not bool:
            raise ValueError("pool outcome must be boolean or unknown")
        self.pending["outcome"] = accepted
        if accepted is not None and not self.pending["block_candidate"]:
            self._resolve_share(accepted)
            return
        self._go("WAITING_EXTERNAL")
        self._save()
        if accepted is True:
            if self.pending["block_candidate"]:
                # Our block was accepted by the pool: mark it so the reorg
                # guard refuses to mine directly on it later.
                self.last_block_hash = self.pending["block_hash"]
            self.memory.consolidate(
                bytes.fromhex(self.pending["header"]),
                self.pending["target"],
                self.pending["job_id"],
            )
            self._save()

    def _resolve_share(self, accepted: bool) -> None:
        """A share with a literal pool answer is fully resolved.

        It carries no chain-height evidence to wait for, so the lifecycle
        returns to SEARCHING without consuming a block cycle (the rung is
        unchanged). Block candidates and unknown outcomes keep the
        external-chain gate.
        """
        pending = self.pending
        self.history.pop()
        self.state = "SEARCHING"
        self.pending = None
        self.last_share = {
            "job_id": pending["job_id"],
            "block_hash": pending["block_hash"],
            "submission_id": pending.get("submission_id"),
            "outcome": accepted,
        }
        if accepted:
            self.memory.consolidate(
                bytes.fromhex(pending["header"]), pending["target"], pending["job_id"]
            )
        self._save()

    def observe_external(
        self, *, block_hash: str, height: int, own_block_height: int | None = None
    ) -> bool:
        """Consume a tip verified by the configured Bitcoin node adapter."""
        if self.state != "WAITING_EXTERNAL" or self.pending is None:
            return False
        if block_hash in (self.pending["block_hash"], self.pending["parent_hash"]):
            return False
        floor = self.pending["parent_height"]
        if (
            type(height) is not int
            or height <= floor
            or not isinstance(block_hash, str)
            or len(block_hash) != 64
            or any(c not in "0123456789abcdef" for c in block_hash)
        ):
            return False
        if self.pending["block_candidate"] and self.pending["outcome"] is not False:
            # A share acknowledgement cannot establish a block's chain height.
            if own_block_height is None:
                if self.pending["outcome"] == "unconfirmed":
                    # The pending block is already resolved as not landed —
                    # its height is fixed by its parent — so this verified
                    # tip is legitimate chain-progress evidence.
                    pass
                else:
                    # A verified tip past our parent that is not the pending
                    # candidate means the block did not land there. Record the
                    # honest outcome, but leave the tip unconsumed: the caller
                    # cannot distinguish it from our own block's landing.
                    self.pending["outcome"] = "unconfirmed"
                    self._save()
                    return False
            else:
                self.last_block_hash = self.pending["block_hash"]
                floor = max(floor, own_block_height)
                if height <= floor:
                    return False
        self.external = {"block_hash": block_hash, "height": height}
        self.cooldown_until = self.clock() + self.cooldown_seconds
        self._go("COOLDOWN")
        self._save()
        return True

    def replace_external(self, *, block_hash: str, height: int) -> bool:
        """Re-anchor the cooldown when the recorded external block was orphaned.

        A cooldown anchored on a block that left the active chain can never
        complete honestly; the current verified tip becomes the new anchor
        and the cooldown restarts from it.
        """
        if self.state != "COOLDOWN" or self.pending is None:
            return False
        if block_hash in (self.pending["block_hash"], self.pending["parent_hash"]):
            return False
        if (
            type(height) is not int
            or height <= self.pending["parent_height"]
            or not isinstance(block_hash, str)
            or len(block_hash) != 64
            or any(c not in "0123456789abcdef" for c in block_hash)
        ):
            return False
        self.external = {"block_hash": block_hash, "height": height}
        self.cooldown_until = self.clock() + self.cooldown_seconds
        self._save()
        return True

    def finish_cooldown(self) -> bool:
        if self.state != "COOLDOWN" or self.clock() < self.cooldown_until:
            return False
        self._go("SEARCHING")
        self.cycles += 1
        self.pending = self.external = None
        self.cooldown_until = None
        self._save()
        return True

    def close(self) -> None:
        if self._lock_file is not None:
            _release_lock(self._lock_file)
            self._lock_file.close()
            self._lock_file = None


def _acquire_exclusive_lock(fileobj) -> None:
    """OS-native non-blocking exclusive lock; raises OSError when contended."""
    try:
        import fcntl
    except ModuleNotFoundError:
        import msvcrt

        fileobj.seek(0)
        try:
            msvcrt.locking(fileobj.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:  # msvcrt reports contention as PermissionError
            raise BlockingIOError(exc.errno, "session lock is held") from exc
    else:
        fcntl.flock(fileobj, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _release_lock(fileobj) -> None:
    try:
        import fcntl
    except ModuleNotFoundError:
        import msvcrt

        fileobj.seek(0)
        try:
            msvcrt.locking(fileobj.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
    else:
        fcntl.flock(fileobj, fcntl.LOCK_UN)
