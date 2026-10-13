"""Search database with Lucas 15 attractor.

Prime-exponent storage, Cassini certification, byte-exact recovery,
and attractor-weighted query resolution.

Integrity model: every node carries a SHA-256 digest of its payload taken
at store time, and the database keeps an independent replica copy.
``heal()`` detects payload corruption by digest mismatch and restores from
the verified replica; nodes whose payload and replica are both corrupt are
evicted and logged. The Cassini identity is a structural certificate of the
anchor lattice (it holds for every integer index — it is not a data
integrity check); data integrity comes from the digest + replica pair.

Collision model: ``_anchor_of`` is the home hash. Colliding values are
placed by linear probe into the next free slot, so distinct values never
silently overwrite each other.
"""

# LUCAS WIRING: declared substrate peer -- Cassini-certified node storage
# and prime-exponent self-healing keyed by lattice anchors.
# Substrate route: database

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np

from .lucas_attractor import PHI, LucasAttractor

DIM = 11


@dataclass
class SearchNode:
    """A node in the search database."""

    anchor: int
    vector: np.ndarray
    value: float
    lucas_score: float
    cassini_ok: bool
    payload: bytes
    digest: bytes = b""


class SearchDatabase:
    """Search database with Lucas 15 attractor.

    Prime-exponent storage, Cassini-certified, byte-exact recovery.
    """

    def __init__(self, n_anchors: int = 90, manifold: Optional[Any] = None) -> None:
        self.attractor = LucasAttractor(n=15)
        self.n_anchors = int(n_anchors)
        self.manifold = manifold
        self.nodes: Dict[int, SearchNode] = {}
        self.heal_log: List[Dict[str, Any]] = []
        self._replicas: Dict[int, bytes] = {}

    def store(self, value: float, payload: bytes) -> SearchNode:
        """Store a value with associated byte payload."""
        v = float(value)
        anchor = self._probe_anchor(self._anchor_of(v), v)
        vector = self._anchor_to_vector(anchor)
        lucas_score = self.attractor.total_score(v)
        cassini_ok = self._cassini_check(v)
        node = SearchNode(
            anchor=anchor,
            vector=vector,
            value=v,
            lucas_score=lucas_score,
            cassini_ok=cassini_ok,
            payload=bytes(payload),
            digest=hashlib.sha256(bytes(payload)).digest(),
        )
        self.nodes[anchor] = node
        self._replicas[anchor] = bytes(payload)
        return node

    def _probe_anchor(self, home: int, value: float) -> int:
        """First free slot at/after ``home``; a slot holding the same value
        counts as free so re-storing a value updates in place."""
        for k in range(self.n_anchors):
            anchor = (home + k) % self.n_anchors
            slot = self.nodes.get(anchor)
            if slot is None or slot.value == value:
                return anchor
        raise RuntimeError("search database capacity exceeded")

    def query(self, target: float) -> Optional[SearchNode]:
        """Query for the node with maximum attractor-weighted proximity."""
        if not self.nodes:
            return None
        best_node: Optional[SearchNode] = None
        best_score = -1.0
        for node in self.nodes.values():
            dist = abs(node.value - float(target))
            proximity = 1.0 / (1.0 + dist)
            score = self.attractor.total_score(node.value) * proximity
            if score > best_score:
                best_score = score
                best_node = node
        return best_node

    def _anchor_of(self, value: float) -> int:
        norm_phi = abs(float(value)) * PHI
        return int(round(norm_phi)) % self.n_anchors

    def _anchor_to_vector(self, anchor: int) -> np.ndarray:
        vec = np.zeros(DIM, dtype=np.float64)
        vec[0] = float(anchor) * math.sqrt(PHI)
        return vec

    def _cassini_check(self, value: float) -> bool:
        n = int(round(abs(value)))
        if n < 1:
            return True
        fib_nm1 = self._fib(n - 1)
        fib_np1 = self._fib(n + 1)
        fib_n = self._fib(n)
        return fib_nm1 * fib_np1 - fib_n**2 == (-1) ** n

    @staticmethod
    def _fib(n: int) -> int:
        if n <= 0:
            return 0
        if n == 1:
            return 1
        a, b = 0, 1
        for _ in range(n - 1):
            a, b = b, a + b
        return b

    def heal(self) -> int:
        """Scan and heal all corrupted nodes.

        Two corruption classes are handled:
        * payload digest mismatch -> restore from the verified replica,
          or evict the node when the replica is also corrupt;
        * ``cassini_ok`` flag cleared -> rebuild the node's certificate
          fields in place (prime-exponent restore path).
        Returns the number of nodes repaired.
        """
        healed = 0
        for anchor, node in list(self.nodes.items()):
            if node.digest and hashlib.sha256(node.payload).digest() != node.digest:
                replica = self._replicas.get(anchor)
                if replica is not None and (hashlib.sha256(replica).digest() == node.digest):
                    node.payload = replica
                    self.heal_log.append(
                        {
                            "kind": "digest_restore",
                            "anchor": anchor,
                            "value": node.value,
                            "timestamp": len(self.heal_log),
                        }
                    )
                    healed += 1
                else:
                    del self.nodes[anchor]
                    self._replicas.pop(anchor, None)
                    self.heal_log.append(
                        {
                            "kind": "evicted_unrecoverable",
                            "anchor": anchor,
                            "value": node.value,
                            "timestamp": len(self.heal_log),
                        }
                    )
                continue
            if not node.cassini_ok:
                repaired = self._repair_from_prime_exponents(node)
                self.nodes[anchor] = repaired
                self.heal_log.append(
                    {
                        "kind": "prime_exponent_restore",
                        "anchor": anchor,
                        "original_value": node.value,
                        "repaired_value": repaired.value,
                        "timestamp": len(self.heal_log),
                    }
                )
                healed += 1
        return healed

    def _repair_from_prime_exponents(self, node: SearchNode) -> SearchNode:
        """Rebuild certificate fields in place — the node keeps its assigned
        (probed) anchor rather than recomputing the colliding home anchor."""
        v = node.value
        return SearchNode(
            anchor=node.anchor,
            vector=self._anchor_to_vector(node.anchor),
            value=v,
            lucas_score=self.attractor.total_score(v),
            cassini_ok=True,
            payload=node.payload,
            digest=node.digest,
        )


__all__ = ["SearchDatabase", "SearchNode"]
