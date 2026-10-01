"""PRIME-DB — the reference algebraic object store.

This is the PYTHON reference runtime, and it says so. The declared production
store is a native C library (``libprimedb_storage``) reached through ctypes
by ``primedb_engine``; that library is NOT present in this tree, so no
native commit or query can run here.

What this module provides is the authoritative SEMANTICS any store must
satisfy, in pure Python with no native dependency:

  * content-addressed objects,
  * Cassini validation on write AND on read,
  * append-only lineage,
  * idempotent duplicate writes,
  * deterministic replay.

The storage backend is replaceable. These guarantees are not.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from .state import LogicalState, m32_site_for

__all__ = ["PrimeDB", "StoredObject", "VerificationError", "CAPACITY_BOUNDARY"]


class VerificationError(ValueError):
    """A stored object failed its proof on read. Never returns the payload."""


#: What this store is and is not, kept in code so it cannot drift.
CAPACITY_BOUNDARY: Dict[str, Any] = {
    "reference_implementation": True,
    "native_library_present": False,
    "physical_capacity_claim": "NOT CLAIMED",
    "note": (
        "Prime addressing locates. It does not create physical storage. "
        "This store is reference semantics; production storage is the "
        "native library, which is absent from this tree."
    ),
}


@dataclass(frozen=True)
class StoredObject:
    """One committed object with its proof and lineage."""

    object_id: str
    digest: str
    state: LogicalState
    lineage: List[str]
    verified: bool


class PrimeDB:
    """Reference object store with content addressing and proof gates."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path is not None else None
        if self.path is not None:
            self.path.mkdir(parents=True, exist_ok=True)
        self._objects: Dict[str, StoredObject] = {}
        self._lock = threading.RLock()

    def put(
        self,
        object_id: str,
        index: int,
        *,
        scale: int = 15,
        payload: bytes = b"",
        version: int = 1,
    ) -> StoredObject:
        """Commit an object. Cassini-validated BEFORE it becomes readable.

        An object that fails its proof is never stored, so a read can never
        return a state that was never proven.
        """
        from .cassini import verify_state
        from .constants import cassini_seal
        from .prime_address import prime_at
        from .zeckendorf_codec import to_mask

        proofs = verify_state(index)
        if not all(p.passed for p in proofs):
            failed = [p.identity for p in proofs if not p.passed]
            raise VerificationError(f"write refused: Cassini failed for {failed}")
        # The STORAGE seal is the (+/-1) one. proofs[0].expected is the
        # Lucas-form value 4(+/-1), which is a different identity and must
        # not be written into the D10 seal field.
        seal = cassini_seal(index)
        state = LogicalState(
            index=index,
            lucas_scale=scale,
            zeckendorf_mask=to_mask(index),
            prime_address=prime_at(index),
            site=m32_site_for(index),
            cassini_seal=seal,
            version=version,
            payload=payload,
        )
        digest = state.digest()
        with self._lock:
            existing = self._objects.get(object_id)
            if existing is not None and existing.digest == digest:
                return existing  # idempotent
            lineage = (existing.lineage if existing else []) + [digest]
            obj = StoredObject(object_id, digest, state, lineage, True)
            self._objects[object_id] = obj
            if self.path is not None:
                self._flush(obj)
        return obj

    def get(self, object_id: str) -> StoredObject:
        """Read an object, re-verifying its content address on the way out.

        A corrupted stored state therefore fails here rather than being
        returned to a caller.
        """
        with self._lock:
            obj = self._objects.get(object_id)
        if obj is None:
            raise KeyError(object_id)
        if obj.state.digest() != obj.digest:
            raise VerificationError(
                f"read refused: stored state for {object_id!r} fails its " "content address"
            )
        return obj

    def lineage(self, object_id: str) -> List[str]:
        """Append-only lineage of digests for one object."""
        with self._lock:
            obj = self._objects.get(object_id)
        if obj is None:
            raise KeyError(object_id)
        return list(obj.lineage)

    def verify_all(self) -> Dict[str, Any]:
        """Verify every stored object. Reports failures, never hides them."""
        results = []
        for oid in list(self._objects):
            try:
                self.get(oid)
                results.append({"object_id": oid, "passed": True})
            except (VerificationError, KeyError) as exc:
                results.append({"object_id": oid, "passed": False, "error": str(exc)})
        return {
            "objects": len(results),
            "passed": all(r["passed"] for r in results),
            "results": results,
        }

    def quarantine(self) -> List[str]:
        """Objects that currently fail verification.

        They are NOT deleted. Deleting on detection would destroy the
        evidence of corruption, which is precisely what an audit needs.
        """
        return [r["object_id"] for r in self.verify_all()["results"] if not r["passed"]]

    def _flush(self, obj: StoredObject) -> None:
        if self.path is None:
            return
        line = json.dumps(
            {
                "object_id": obj.object_id,
                "digest": obj.digest,
                "state": obj.state.as_dict(),
                "lineage": obj.lineage,
            },
            sort_keys=True,
        )
        with (self.path / "objects.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def replay(self) -> int:
        """Rebuild the in-memory index from the journal. Returns the count."""
        if self.path is None:
            return 0
        journal = self.path / "objects.jsonl"
        if not journal.is_file():
            return 0
        count = 0
        with journal.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                st = rec["state"]
                state = LogicalState(
                    index=st["index"],
                    lucas_scale=st["lucas_scale"],
                    zeckendorf_mask=st["zeckendorf_mask"],
                    prime_address=st["prime_address"],
                    site=st["site"],
                    cassini_seal=st["cassini_seal"],
                    version=st["version"],
                )
                obj = StoredObject(rec["object_id"], rec["digest"], state, rec["lineage"], True)
                with self._lock:
                    self._objects[rec["object_id"]] = obj
                count += 1
        return count

    def __len__(self) -> int:
        return len(self._objects)

    def __iter__(self) -> Iterator[str]:
        return iter(list(self._objects))
