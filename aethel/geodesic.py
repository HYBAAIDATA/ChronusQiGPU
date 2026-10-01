"""Geodesic handoff — the ONLY interface between aethel and the engine.

Aethel does not implement retrieval or search.  Retrieval IS the geodesic
engine — the same 32-face Poincare-Cassini engine that orders the Bitcoin
nonce space (``Intelligence.search_crystal.PoincareCassiniSearchEngine``)
plus the 11-D Pathfinder frame navigator (``Intelligence.pathfinder``).
This adapter maps aethel storage blocks to points the engine navigates,
and back.

Two mapping contracts:

* ``to_manifold(address) -> ManifoldPoint`` — a block's Fibonacci address
  becomes an engine-space position (its global sequence rank) plus a
  76-byte routing key the engine's coverage enumeration accepts verbatim.
* ``from_manifold(point) -> bytes`` — the position resolves back through
  the Cassini ledger to the stored payload; integrity is re-verified.

The engine's own invariant checks (``build_search_crystal``,
``partition_interval``, ``cassini_permutation``) are invoked against the
storage interval unchanged — aethel inherits the engine's coverage
guarantee rather than restating it.
"""

from __future__ import annotations

import hashlib
import importlib
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np

from .constants import DIM, PHI
from .errors import EngineUnavailable, GapDetected, HandoffRejection
from .storage import AddressSpace, FibonacciAddress

logger = logging.getLogger("aethel.geodesic")

_CRYSTAL = None
_PATHFINDER = None


def _search_crystal():
    """Lazy handle on the coverage engine module (heavy package init)."""
    global _CRYSTAL
    if _CRYSTAL is None:
        try:
            _CRYSTAL = importlib.import_module("Intelligence.search_crystal")
        except Exception as exc:  # pragma: no cover - environment dependent
            raise EngineUnavailable(
                f"geodesic engine (Intelligence.search_crystal) unavailable: {exc}"
            ) from exc
    return _CRYSTAL


def _pathfinder_cls():
    """Lazy handle on the 11-D Pathfinder class."""
    global _PATHFINDER
    if _PATHFINDER is None:
        try:
            mod = importlib.import_module("Intelligence.pathfinder")
            _PATHFINDER = mod.Pathfinder
        except Exception as exc:  # pragma: no cover - environment dependent
            raise EngineUnavailable(
                f"geodesic navigator (Intelligence.pathfinder) unavailable: {exc}"
            ) from exc
    return _PATHFINDER


@dataclass(frozen=True)
class ManifoldPoint:
    """An engine-space coordinate for one stored block.

    ``position`` is the block's global write rank inside the storage
    interval [0, capacity); ``index`` its Fibonacci address index; ``key``
    the 76-byte routing key accepted by the engine's coverage enumeration;
    ``vector`` the 11-D Poincare direction for frame navigation.
    """

    position: int
    index: int
    key: bytes
    vector: Tuple[float, ...]


class GeodesicHandoff:
    """STABLE adapter: aethel storage manifold <-> geodesic engine.

    Versioned with the package: ``adapter.version`` reads
    ``aethel.__version__`` — the single source of truth.

    Precondition: ``space`` is a consistent AddressSpace (ledger verifies).
    Thread-safety: read paths are pure once the engine is built; key
    registration is guarded by the underlying ledger lock.
    """

    def __init__(self, space: AddressSpace, *, capacity: Optional[int] = None) -> None:
        self.space = space
        self._capacity = capacity
        self._engine = None
        self._positions: Dict[bytes, int] = {}
        self._by_position: Dict[int, bytes] = {}

    # -- versioning -----------------------------------------------------------

    @property
    def version(self) -> str:
        import aethel

        return aethel.__version__

    # -- engine ---------------------------------------------------------------

    def engine(self):
        """The coverage engine bound to this storage interval.

        The engine itself validates its domain: non-positive or
        over-uint32 intervals raise its own ValueError — schema validation
        is the engine's, not the adapter's.
        """
        if self._engine is None:
            crystal = _search_crystal()
            start, size = self.storage_interval()
            self._engine = crystal.PoincareCassiniSearchEngine(
                total_nonce_space=size, nonce_start=start
            )
        return self._engine

    def storage_interval(self) -> Tuple[int, int]:
        """(start, size) of the storage manifold in engine coordinates."""
        size = self._capacity
        if size is None:
            size = max(1, len(self.space.ledger))
        return 0, int(size)

    # -- direction ------------------------------------------------------------

    @staticmethod
    def _direction(key: bytes) -> Tuple[float, ...]:
        """The engine's own direction lift: sha256 -> 11-D Poincare ray."""
        digest = hashlib.sha256(key).digest()
        raw = [(digest[i] - 127.5) / 127.5 for i in range(DIM)]
        norm_sq = sum((float(PHI) ** -(i + 1)) * v * v for i, v in enumerate(raw))
        scale = 1.0 / (1.0 + norm_sq) ** 0.5
        return tuple(v * scale for v in raw)

    @staticmethod
    def block_key(index: int, digest_hex: str) -> bytes:
        """Deterministic routing key for a stored block (76 bytes, the
        schema the coverage engine accepts as a header prefix)."""
        seed = f"aethel:{index}:{digest_hex}".encode()
        out = hashlib.sha256(seed).digest()
        # 76 bytes: sha256(seed) chained twice + truncation, deterministic.
        out = (out + hashlib.sha256(out).digest() + hashlib.sha256(seed + b"2").digest())[:76]
        return out

    # -- handoff --------------------------------------------------------------

    def to_manifold(self, address: FibonacciAddress) -> ManifoldPoint:
        """Map a stored block's Fibonacci address to an engine point.

        Raises GapDetected when the ledger stream is broken or the address
        is not committed; HandoffRejection when the ledger has no entry.
        """
        self.space.ledger.check_consistent()
        entry = self.space.ledger.index_of(address.index)
        if entry is None:
            raise GapDetected(f"address index {address.index} not in ledger")
        position = entry.seq
        key = self.block_key(entry.index, entry.digest)
        point = ManifoldPoint(
            position=position,
            index=entry.index,
            key=key,
            vector=self._direction(key),
        )
        self._positions[key] = position
        self._by_position[position] = key
        logger.debug(
            "to_manifold: index=%d -> position=%d", entry.index, position
        )
        return point

    def from_manifold(self, point: ManifoldPoint) -> bytes:
        """Map an engine point back to the stored payload bytes.

        Postcondition: the block's ledger digest equals the digest embedded
        in ``point.key`` — mismatched points raise HandoffRejection.
        """
        self.space.ledger.check_consistent()
        if point.position < 0 or point.position >= len(self.space.ledger.entries):
            raise HandoffRejection(
                f"position {point.position} outside storage interval"
            )
        entry = self.space.ledger.entries[point.position]
        if entry.index != point.index:
            raise HandoffRejection(
                f"position {point.position} maps to index {entry.index}, "
                f"not {point.index}"
            )
        if self.block_key(entry.index, entry.digest) != point.key:
            raise HandoffRejection("point key does not match ledger digest")
        return self.space.read(FibonacciAddress(entry.index, entry.value))

    def _blocks(self) -> Dict[int, bytes]:
        return self.space._blocks  # storage-layer internal, same package trust

    def register(self, address: FibonacciAddress) -> ManifoldPoint:
        """Alias of to_manifold kept for call-site readability."""
        return self.to_manifold(address)

    def retrieve(self, key: bytes) -> bytes:
        """Engine-mediated retrieval: resolve key -> position -> block.

        The engine enumerates the coverage order over the storage interval
        with this key as the routing prefix; the position must appear in
        that order — the engine's coverage certificate applied to the
        storage manifold.
        """
        position = self._positions.get(key)
        if position is None:
            raise HandoffRejection("unknown key: block was never handed off")
        order = self.engine().enumerate_nonces(key)
        if position not in order:
            raise HandoffRejection(
                "engine coverage does not include the block position"
            )
        entry = self.space.ledger.entries[position]
        point = ManifoldPoint(
            position=position, index=entry.index, key=key,
            vector=self._direction(key),
        )
        return self.from_manifold(point)

    # -- engine invariant handoff ----------------------------------------------

    def check_engine_invariants(self) -> Dict[str, Any]:
        """Run the engine's OWN invariant checks against this manifold.

        Every check below is an engine function imported unchanged —
        aethel reimplements nothing:

        * ``build_search_crystal`` — 32-face dual construction, each face
          Cassini-certified (raises ArithmeticError on failure).
        * ``partition_interval`` — gapless, non-overlapping coverage of the
          storage interval (raises ArithmeticError on failure).
        * ``cassini_permutation`` — unimodular affine schedule, coprime
          stride (raises ArithmeticError on failure).
        * ``enumerate_nonces`` — the emitted order is asserted to cover
          every position exactly once (the engine's declared postcondition).
        """
        crystal = _search_crystal()
        start, size = self.storage_interval()

        faces = crystal.build_search_crystal()

        intervals = crystal.partition_interval(start, size, len(faces))
        covered = sum(iv.size for iv in intervals)
        contiguous = all(
            intervals[i].stop == intervals[i + 1].start
            for i in range(len(intervals) - 1)
        )
        coverage_ok = covered == size and contiguous and intervals[0].start == start

        schedules = [
            crystal.cassini_permutation(max(1, iv.size), face.face_id, 0)
            for face, iv in zip(faces, intervals)
        ]
        schedules_ok = all(s.cassini_determinant in (-1, 1) for s in schedules)

        key = self.block_key(0, "invariant-probe")
        order = self.engine().enumerate_nonces(key)
        enumeration_ok = len(order) == size and set(order) == set(
            range(start, start + size)
        )

        return {
            "faces": len(faces),
            "interval_size": size,
            "coverage_complete": bool(coverage_ok),
            "schedules_unimodular": bool(schedules_ok),
            "enumeration_exact": bool(enumeration_ok),
            "engine": crystal.SEARCH_ENGINE_ID,
        }

    def navigate(self, point: ManifoldPoint, *, max_iter: int = 20) -> Dict[str, Any]:
        """Pathfinder navigation to the block's Fibonacci anchor.

        Returns the engine's own navigation record (``converged``,
        ``iterations``, ``final_precision``, ``trajectory``) — the
        bounded-hops guarantee the engine already provides on the nonce
        manifold, applied to the storage manifold.
        """
        pathfinder_cls = _pathfinder_cls()
        pf = pathfinder_cls(n_faces=32)
        r0 = np.zeros(DIM, dtype=np.float64)
        r0[0] = float(point.index) * float(np.sqrt((1 + np.sqrt(5)) / 2))
        result = pf.navigate(r0, float(point.index), max_iter=max_iter, tol=1e-8)
        result["target_index"] = point.index
        return result


__all__ = ["GeodesicHandoff", "ManifoldPoint"]
