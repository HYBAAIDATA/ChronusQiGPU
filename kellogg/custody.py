"""Tensor custody — where every Kellogg tensor core and certificate lives.

The exact tensor engine owns no private storage. Each core version is an
immutable, content-addressed payload placed in custody; the engine keeps
only the per-site reference (the payload digest, which is also the site's
Merkle leaf) and a bounded resident window of decoded cores. Folding,
eviction, tiering and durable storage are custody's job, so the overhead of
exactness is carried and accounted by custody instead of process memory.

Protocol (duck-typed; no import in either direction):

    put(payload: bytes) -> ref        content-addressed write; acquires one hold
    get(ref) -> bytes                 fails closed if released and not regenerated
    release(ref) -> header            drops one hold; at zero holds the bytes go
                                      and the identity (digest, size) stays
    regenerate(ref, payload) -> ref   re-admit bytes, proven by digest equality
    record(certificate)               append to the custody ledger
    accounting() -> dict              measured bytes per tier

Holds are counted by custody, not by the tensors, because content addressing
shares one block between every tensor (and every site) holding equal bytes.

Implementations:

* :class:`ResidentCustody` — Kellogg's built-in in-process custody.
* :class:`FoldStoreCustody` — binds to an Aethel ``PersistentFoldStore``
  (or anything exposing ``create/read/evict/status``): each payload becomes
  a phi-folded uint8 block named by its digest; release evicts the block to
  its identity header; checkpoint/restore persist the graph.

``default_custody()`` resolves the Aethel fold store when it is installed
and Kellogg's resident custody otherwise; the resolution is recorded in
``accounting()['provider']`` so no run silently changes custody.
"""

from __future__ import annotations

import hashlib
import importlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_DOMAIN = b"kellogg.custody.payload/v1\0"


class CustodyError(RuntimeError):
    """A custody read, write or identity proof failed closed."""


def payload_ref(payload: bytes) -> str:
    return hashlib.sha256(_DOMAIN + payload).hexdigest()


@dataclass
class _Entry:
    size: int
    payload: Optional[bytes]
    holds: int = 0


@dataclass
class ResidentCustody:
    """In-process custody with identity-preserving release."""

    provider: str = "kellogg.resident"
    _store: Dict[str, _Entry] = field(default_factory=dict)
    _ledger: List[Any] = field(default_factory=list)
    puts: int = 0
    gets: int = 0
    bytes_written: int = 0
    bytes_read: int = 0

    def put(self, payload: bytes) -> str:
        ref = payload_ref(payload)
        entry = self._store.get(ref)
        if entry is None:
            entry = self._store[ref] = _Entry(len(payload), bytes(payload))
            self.bytes_written += len(payload)
        elif entry.payload is None:
            entry.payload = bytes(payload)
            self.bytes_written += len(payload)
        entry.holds += 1
        self.puts += 1
        return ref

    def holds(self, ref: str) -> int:
        entry = self._store.get(ref)
        return 0 if entry is None else entry.holds

    def get(self, ref: str) -> bytes:
        entry = self._store.get(ref)
        if entry is None:
            raise CustodyError(f"unknown custody ref {ref[:16]}")
        if entry.payload is None:
            raise CustodyError(f"custody ref {ref[:16]} is released; regenerate it first")
        self.gets += 1
        self.bytes_read += entry.size
        return entry.payload

    def release(self, ref: str) -> dict:
        entry = self._store.get(ref)
        if entry is None:
            raise CustodyError(f"unknown custody ref {ref[:16]}")
        entry.holds = max(0, entry.holds - 1)
        if entry.holds == 0:
            entry.payload = None
        return {"ref": ref, "size": entry.size, "holds": entry.holds,
                "residency": "released" if entry.payload is None else "resident"}

    def regenerate(self, ref: str, payload: bytes) -> str:
        if payload_ref(payload) != ref:
            raise CustodyError("regenerated payload does not match its identity")
        entry = self._store.get(ref)
        if entry is None:
            raise CustodyError(f"unknown custody ref {ref[:16]}")
        entry.payload = bytes(payload)
        return ref

    def record(self, certificate: Any) -> None:
        self._ledger.append(certificate)

    def ledger(self) -> List[Any]:
        return list(self._ledger)

    def accounting(self) -> dict:
        resident = sum(e.size for e in self._store.values() if e.payload is not None)
        released = sum(e.size for e in self._store.values() if e.payload is None)
        return {
            "provider": self.provider,
            "blocks": len(self._store),
            "resident_bytes": resident,
            "released_bytes": released,
            "bytes_written": self.bytes_written,
            "bytes_read": self.bytes_read,
            "puts": self.puts,
            "gets": self.gets,
            "certificates": len(self._ledger),
        }


class FoldStoreCustody:
    """Custody over a folded block store (Aethel ``PersistentFoldStore``)."""

    def __init__(self, store: Any, *, namespace: str = "kellogg", depth: int = 2) -> None:
        for name in ("create", "read", "evict", "status"):
            if not hasattr(store, name):
                raise CustodyError(f"fold store lacks {name}()")
        self.store = store
        self.namespace = namespace
        self.depth = int(depth)
        self.provider = f"{type(store).__module__}.{type(store).__name__}"
        self._sizes: Dict[str, int] = {}
        self._released: Dict[str, bool] = {}
        self._holds: Dict[str, int] = {}
        self._ledger: List[Any] = []
        self.puts = 0
        self.gets = 0
        self.bytes_written = 0
        self.bytes_read = 0

    def _name(self, ref: str) -> str:
        return f"{self.namespace}/{ref}"

    @staticmethod
    def _array(payload: bytes) -> Any:
        import numpy as np

        return np.frombuffer(payload, dtype=np.uint8).copy()

    def _fold_depth(self, size: int) -> int:
        depth, retained = 0, size
        while depth < self.depth and retained >= 4:
            retained -= max(1, round(retained / 2.618033988749895))
            depth += 1
        return depth

    def holds(self, ref: str) -> int:
        return self._holds.get(ref, 0)

    def put(self, payload: bytes) -> str:
        ref = payload_ref(payload)
        self.puts += 1
        self._holds[ref] = self._holds.get(ref, 0) + 1
        if ref in self._sizes and not self._released.get(ref, False):
            return ref
        name = self._name(ref)
        if ref in self._sizes:
            self.store.regenerate(name, self._array(payload))
        else:
            self.store.create(name, self._array(payload), depth=self._fold_depth(len(payload)))
        self._sizes[ref] = len(payload)
        self._released[ref] = False
        self.bytes_written += len(payload)
        return ref

    def get(self, ref: str) -> bytes:
        if ref not in self._sizes:
            raise CustodyError(f"unknown custody ref {ref[:16]}")
        if self._released.get(ref):
            raise CustodyError(f"custody ref {ref[:16]} is evicted; regenerate it first")
        payload = bytes(self.store.read(self._name(ref)).tobytes())
        if payload_ref(payload) != ref:
            raise CustodyError("fold store returned bytes that do not match their identity")
        self.gets += 1
        self.bytes_read += len(payload)
        return payload

    def release(self, ref: str) -> dict:
        if ref not in self._sizes:
            raise CustodyError(f"unknown custody ref {ref[:16]}")
        self._holds[ref] = max(0, self._holds.get(ref, 0) - 1)
        if self._holds[ref] == 0 and not self._released.get(ref):
            self.store.evict(self._name(ref))
            self._released[ref] = True
        return {"ref": ref, "size": self._sizes[ref], "holds": self._holds[ref],
                "residency": "evicted" if self._released.get(ref) else "resident"}

    def regenerate(self, ref: str, payload: bytes) -> str:
        if payload_ref(payload) != ref:
            raise CustodyError("regenerated payload does not match its identity")
        self.store.regenerate(self._name(ref), self._array(payload))
        self._released[ref] = False
        return ref

    def record(self, certificate: Any) -> None:
        self._ledger.append(certificate)

    def ledger(self) -> List[Any]:
        return list(self._ledger)

    def checkpoint(self, path: Any) -> Any:
        return self.store.checkpoint(path)

    def accounting(self) -> dict:
        resident = sum(s for r, s in self._sizes.items() if not self._released.get(r))
        released = sum(s for r, s in self._sizes.items() if self._released.get(r))
        status = self.store.status()
        folded = sum(
            1 for name, row in status.get("blocks", {}).items()
            if name.startswith(self.namespace + "/")
        )
        return {
            "provider": self.provider,
            "blocks": len(self._sizes),
            "fold_blocks": folded,
            "resident_bytes": resident,
            "released_bytes": released,
            "bytes_written": self.bytes_written,
            "bytes_read": self.bytes_read,
            "puts": self.puts,
            "gets": self.gets,
            "certificates": len(self._ledger),
        }


def default_custody() -> Any:
    """Aethel fold-store custody when installed; Kellogg resident custody otherwise."""
    try:
        module = importlib.import_module("aethel.fold_store")
    except ImportError:
        return ResidentCustody()
    return FoldStoreCustody(module.PersistentFoldStore(default_depth=2))


__all__ = [
    "CustodyError",
    "FoldStoreCustody",
    "ResidentCustody",
    "default_custody",
    "payload_ref",
]
