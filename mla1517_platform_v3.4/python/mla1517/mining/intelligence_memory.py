"""Aethel-backed memory for the mining intelligence.

Each checkpoint of learned state is a block on an Aethel Fibonacci address
space, chained in the Cassini ledger. On boot the journal is replayed and the
ledger verified before anything is trusted; the latest block's SHA-256 must
equal its ledger digest. Any defect leaves the intelligence on a clean
baseline and is reported, never silently repaired.

Fibonacci values grow without bound, so the memory rotates to a new
generation directory every ``rotate_after`` checkpoints, seeding it with the
latest state and keeping the previous generation for audit.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from pathlib import Path
from typing import Any

from aethel.errors import AethelError
from aethel.storage import AddressSpace

LOG = logging.getLogger("mla1517.mining.memory")

_SCHEMA = "pythia.intelligence.memory/1"


class IntelligenceMemory:
    def __init__(self, directory: str | Path, *, rotate_after: int = 256) -> None:
        if rotate_after < 2:
            raise ValueError("rotate_after must be at least 2")
        self.root = Path(directory)
        self.rotate_after = rotate_after
        self.last_error: str | None = None
        self.checkpoints = 0
        self._generation, self._space = self._open_latest()

    def _generations(self) -> list[int]:
        if not self.root.is_dir():
            return []
        return sorted(
            int(p.name.split("-", 1)[1])
            for p in self.root.iterdir()
            if p.is_dir() and p.name.startswith("gen-") and p.name.split("-", 1)[1].isdigit()
        )

    def _dir(self, generation: int) -> Path:
        return self.root / f"gen-{generation:06d}"

    def _open_latest(self) -> tuple[int, AddressSpace]:
        generations = self._generations()
        if not generations:
            return 1, AddressSpace()
        latest = generations[-1]
        try:
            space = AddressSpace.attach(self._dir(latest))
            if not space.verify():
                raise AethelError("ledger verification failed")
            return latest, space
        except (AethelError, OSError, ValueError, KeyError) as exc:
            self.last_error = f"generation {latest} rejected: {exc}"
            LOG.warning("intelligence memory %s", self.last_error)
            return latest + 1, AddressSpace()

    def load(self) -> dict[str, Any] | None:
        """The latest verified checkpoint, or None (clean baseline)."""
        entries = self._space.ledger.entries
        if not entries:
            return None
        entry = entries[-1]
        try:
            block = self._space.read(self._space.address_of_index(entry.index))
        except AethelError as exc:
            self.last_error = f"read failed: {exc}"
            return None
        if hashlib.sha256(block).hexdigest() != entry.digest:
            self.last_error = "checkpoint digest does not match its ledger entry"
            return None
        try:
            body = json.loads(block.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.last_error = f"checkpoint is not valid JSON: {exc}"
            return None
        if body.get("schema") != _SCHEMA:
            self.last_error = f"unsupported checkpoint schema {body.get('schema')!r}"
            return None
        return body["state"]

    def checkpoint(self, state: dict[str, Any]) -> dict[str, Any]:
        """Append ``state`` and persist atomically; returns the ledger position."""
        payload = json.dumps(
            {"schema": _SCHEMA, "state": state}, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        if len(self._space.ledger) >= self.rotate_after:
            self._rotate()
        address = self._space.write(payload)
        target = self._dir(self._generation)
        self._space.snapshot(target)
        self.checkpoints += 1
        return {
            "generation": self._generation,
            "index": address.index,
            "digest": hashlib.sha256(payload).hexdigest(),
            "entries": len(self._space.ledger),
        }

    def _rotate(self) -> None:
        self._generation += 1
        self._space = AddressSpace()
        for old in self._generations()[:-1]:
            shutil.rmtree(self._dir(old), ignore_errors=True)

    def snapshot(self) -> dict[str, Any]:
        return {
            "backend": "aethel",
            "directory": str(self.root),
            "generation": self._generation,
            "entries": len(self._space.ledger),
            "ledger_verified": self._space.verify(),
            "checkpoints_this_run": self.checkpoints,
            "last_error": self.last_error,
        }
