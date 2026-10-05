"""PYTHIA's canonical precomputed mining-search lattice.

The static search substrate is prepared before Stratum work starts:

    11D phi-weighted manifold
      -> dodecahedron/icosahedron 12+20 dual overlay (32 coarse directions)
      -> H4 600-cell tetrahedra
      -> 600 dual directions (the 120-cell's vertex set, up to radial scale)
      -> injective addresses in the exact 11-qubit Hilbert basis C^2048
      -> coverage-preserving nonce shards and Cassini affine schedules

A real job supplies the 76-byte header prefix. That observation ranks the
precomputed coarse directions and then the 600 dual vertices; it never changes
the membership of the nonce lease. The result is a deterministic permutation
of exactly the leased nonce interval. SHA256d, negotiated target, freshness and
literal pool acknowledgement remain the sole mining truth authorities.

No search-advantage claim is made here. This module proves composition,
coverage, determinism and provenance so measured production outcomes can test
whether the architecture is useful.
"""

from __future__ import annotations

import hashlib
import heapq
import itertools
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Sequence

import numpy as np

from Intelligence.search_crystal import (
    build_search_crystal,
    cassini_permutation,
    partition_interval,
)
from chronus.h4_600 import (
    DIM,
    PHI,
    cell_normals,
    generate_600cell_cells,
    generate_600cell_vertices,
    lift_fold_11d,
)
from mtheory.hilbert import QuantumRegister

SEARCH_ARCHITECTURE_ID = "pythia_dual32_11d_h4_600_hilbert"
HILBERT_QUBITS = 11
HILBERT_DIM = 1 << HILBERT_QUBITS
DUAL_VERTEX_COUNT = 600
COARSE_FACE_COUNT = 32


def _phi_dot(a: Sequence[float], b: Sequence[float]) -> float:
    n = min(len(a), len(b), DIM)
    return sum((PHI ** (-(i + 1))) * float(a[i]) * float(b[i]) for i in range(n))


def _header_direction(header_prefix: bytes) -> tuple[float, ...]:
    if len(header_prefix) != 76:
        raise ValueError("header_prefix must be exactly 76 bytes")
    digest = hashlib.sha256(header_prefix).digest()
    raw = tuple((digest[index] - 127.5) / 127.5 for index in range(DIM))
    norm_sq = sum((PHI ** (-(i + 1))) * value * value for i, value in enumerate(raw))
    scale = 1.0 / math.sqrt(1.0 + norm_sq)
    return tuple(value * scale for value in raw)


def _dual_adjacency(cells: Sequence[Sequence[int]]) -> tuple[tuple[int, ...], ...]:
    """Adjacency of the dual 120-cell: 600 vertices, degree four.

    Each vertex in the dual corresponds to one tetrahedral cell of the
    600-cell. Two dual vertices are adjacent exactly when those tetrahedra
    share one triangular face.
    """
    face_to_cells: dict[tuple[int, int, int], list[int]] = {}
    for cell_id, tetrahedron in enumerate(cells):
        for face in itertools.combinations(tetrahedron, 3):
            key = tuple(sorted(int(v) for v in face))
            face_to_cells.setdefault(key, []).append(cell_id)
    adjacency = [set() for _ in cells]
    for owners in face_to_cells.values():
        if len(owners) != 2:
            raise ArithmeticError("600-cell triangular face must have exactly two owners")
        left, right = owners
        adjacency[left].add(right)
        adjacency[right].add(left)
    result = tuple(tuple(sorted(neighbours)) for neighbours in adjacency)
    if len(result) != DUAL_VERTEX_COUNT or any(len(neighbours) != 4 for neighbours in result):
        raise ArithmeticError("dual 120-cell adjacency must contain 600 degree-four vertices")
    return result


@dataclass(frozen=True)
class PythiaSearchPrecompute:
    """Immutable startup artifact consumed by every PYTHIA mining plan."""

    architecture_id: str
    coarse_frames_11d: tuple[tuple[float, ...], ...]
    dual_vertices_4d: tuple[tuple[float, float, float, float], ...]
    frames_11d: tuple[tuple[float, ...], ...]
    coarse_anchor: tuple[int, ...]
    adjacency: tuple[tuple[int, ...], ...]
    hilbert_basis: tuple[int, ...]
    digest: str

    def summary(self) -> dict[str, Any]:
        edges = sum(len(neighbours) for neighbours in self.adjacency) // 2
        return {
            "schema": "pythia.search_precompute/1",
            "architecture_id": self.architecture_id,
            "state": "READY",
            "prepared_before_pool_work": True,
            "coarse_dual_faces": len(self.coarse_frames_11d),
            "dual_vertices": len(self.dual_vertices_4d),
            "dual_edges": edges,
            "manifold_dimension": DIM,
            "hilbert_qubits": HILBERT_QUBITS,
            "hilbert_dimension": HILBERT_DIM,
            "hilbert_addresses": len(self.hilbert_basis),
            "all_coarse_faces_occupied": len(set(self.coarse_anchor)) == COARSE_FACE_COUNT,
            "digest": self.digest,
            "claim_boundary": (
                "precomputed coverage/search ordering only; SHA256d, target, freshness and "
                "literal pool acknowledgement remain authoritative"
            ),
        }

    def workforce_manifest(self) -> dict[str, Any]:
        """One PYTHIA workforce, many bounded roles; no duplicate authorities."""
        return {
            "schema": "pythia.agentic_mining_workforce/1",
            "composition_root": "PYTHIA",
            "enterprise_orchestrator": "EUCLID",
            "roles": [
                {
                    "role": "world_model_and_causal_intelligence",
                    "owner": "PYTHIA",
                    "authority": "predict/diagnose/rank; never proof",
                },
                {
                    "role": "agentic_search_planner",
                    "owner": "AgenticMiningController",
                    "authority": "bounded plan + exclusive nonce lease",
                },
                {
                    "role": "search_topology",
                    "owner": "PYTHIA",
                    "authority": self.architecture_id,
                },
                {
                    "role": "physical_execution",
                    "owner": "Chronus",
                    "authority": "execute exact authorised nonce batches on capability-proven lanes",
                },
                {
                    "role": "proof_and_epoch_guardian",
                    "owner": "StratumProofAdapter",
                    "authority": "SHA256d + target + current work",
                },
                {
                    "role": "submission",
                    "owner": "IntelligentPoolCoordinator",
                    "authority": "single serialized mining.submit writer",
                },
                {
                    "role": "healing_and_optimisation",
                    "owner": "Salamander",
                    "authority": "bounded detect/repair/reprobe and measured retain/rollback",
                },
                {
                    "role": "outcome_learning",
                    "owner": "PYTHIA",
                    "authority": "learn from measured execution and literal pool outcomes",
                },
            ],
        }


@lru_cache(maxsize=1)
def precompute_pythia_search() -> PythiaSearchPrecompute:
    """Build and validate the job-independent search substrate once per process."""
    coarse_faces = build_search_crystal()
    if len(coarse_faces) != COARSE_FACE_COUNT:
        raise ArithmeticError("PYTHIA coarse dual overlay must contain 12 + 20 = 32 faces")
    coarse_frames = tuple(tuple(face.direction_11d) for face in coarse_faces)

    h4_vertices = generate_600cell_vertices()
    h4_cells = generate_600cell_cells(h4_vertices)
    if len(h4_vertices) != 120 or len(h4_cells) != DUAL_VERTEX_COUNT:
        raise ArithmeticError("H4 600-cell must contain 120 vertices and 600 tetrahedral cells")

    # The normalized cell-centroid directions are the vertices of the dual
    # 120-cell up to a common radial scale: exactly 600 high-resolution search
    # directions, preserving the existing H4 construction rather than adding a
    # second hand-written polytope implementation.
    dual_vertices = tuple(cell_normals(h4_vertices, h4_cells))
    if len(dual_vertices) != DUAL_VERTEX_COUNT:
        raise ArithmeticError("dual 120-cell must contain exactly 600 vertices")
    frames_11d = tuple(tuple(lift_fold_11d(vertex)[0]) for vertex in dual_vertices)

    coarse_anchor = tuple(
        max(range(COARSE_FACE_COUNT), key=lambda face_id: _phi_dot(frame, coarse_frames[face_id]))
        for frame in frames_11d
    )
    if len(set(coarse_anchor)) != COARSE_FACE_COUNT:
        raise ArithmeticError("all 32 dodecahedron/icosahedron directions must own dual vertices")

    adjacency = _dual_adjacency(h4_cells)

    # 600 search vertices fit injectively into the exact 11-qubit Hilbert
    # basis. The geometry remains in the 11D frames/graph; the basis addresses
    # are a lossless identity map, not a fabricated amplitude claim.
    register = QuantumRegister(HILBERT_QUBITS)
    if register.dim != HILBERT_DIM or DUAL_VERTEX_COUNT > register.dim:
        raise ArithmeticError("600 vertices must fit inside the exact 11-qubit Hilbert basis")
    hilbert_basis = tuple(range(DUAL_VERTEX_COUNT))

    digest_body = {
        "architecture_id": SEARCH_ARCHITECTURE_ID,
        "h4_cells": [list(cell) for cell in h4_cells],
        "coarse_anchor": list(coarse_anchor),
        "adjacency": [list(neighbours) for neighbours in adjacency],
        "hilbert_basis": list(hilbert_basis),
    }
    digest = hashlib.sha256(
        json.dumps(digest_body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    return PythiaSearchPrecompute(
        architecture_id=SEARCH_ARCHITECTURE_ID,
        coarse_frames_11d=coarse_frames,
        dual_vertices_4d=dual_vertices,
        frames_11d=frames_11d,
        coarse_anchor=coarse_anchor,
        adjacency=adjacency,
        hilbert_basis=hilbert_basis,
        digest=digest,
    )


def vertex_itinerary(
    header: bytes,
    precompute: PythiaSearchPrecompute | None = None,
) -> tuple[int, ...]:
    """Rank and graph-traverse all 600 Hilbert-addressed search vertices.

    The header is real job data. The 32-face dual overlay supplies coarse
    ranking; the 600 11D directions supply fine ranking. A best-first walk over
    the precomputed dual graph ensures every newly visited vertex is connected
    to the already explored search manifold. Membership is never pruned.
    """
    if len(header) != 80:
        raise ValueError("header must be exactly 80 bytes")
    state = precompute or precompute_pythia_search()
    direction = _header_direction(bytes(header[:76]))

    coarse = sorted(
        range(COARSE_FACE_COUNT),
        key=lambda face_id: (-_phi_dot(direction, state.coarse_frames_11d[face_id]), face_id),
    )
    coarse_rank = {face_id: rank for rank, face_id in enumerate(coarse)}
    score = [
        (coarse_rank[state.coarse_anchor[vertex_id]], -_phi_dot(direction, frame), vertex_id)
        for vertex_id, frame in enumerate(state.frames_11d)
    ]
    root = min(range(DUAL_VERTEX_COUNT), key=lambda vertex_id: score[vertex_id])

    visited = {root}
    order = [root]
    frontier: list[tuple[tuple[int, float, int], int]] = []
    for neighbour in state.adjacency[root]:
        heapq.heappush(frontier, (score[neighbour], neighbour))
    while frontier:
        _priority, vertex_id = heapq.heappop(frontier)
        if vertex_id in visited:
            continue
        visited.add(vertex_id)
        order.append(vertex_id)
        for neighbour in state.adjacency[vertex_id]:
            if neighbour not in visited:
                heapq.heappush(frontier, (score[neighbour], neighbour))
    if len(order) != DUAL_VERTEX_COUNT or len(set(order)) != DUAL_VERTEX_COUNT:
        raise ArithmeticError("600-vertex Hilbert itinerary lost manifold coverage")
    return tuple(order)


def pythia_hilbert_600_nonces(
    header: bytes,
    base: int,
    window: int,
    *,
    position: int = 0,
    count: int | None = None,
    precompute: PythiaSearchPrecompute | None = None,
) -> list[int]:
    """Coverage-complete nonce permutation driven by the 600-vertex itinerary."""
    if len(header) != 80:
        raise ValueError("header must be exactly 80 bytes")
    if type(base) is not int or not 0 <= base <= 0xFFFFFFFF:
        raise ValueError("base must be uint32")
    if type(window) is not int or window < 0 or base + window > 1 << 32:
        raise ValueError("window must fit inside the uint32 nonce space")
    if type(position) is not int or not 0 <= position <= window:
        raise ValueError("position must be inside the window")
    take = window - position if count is None else count
    if type(take) is not int or take < 0 or position + take > window:
        raise ValueError("count must fit inside the remaining window")
    if window == 0 or take == 0:
        return []

    state = precompute or precompute_pythia_search()
    itinerary = vertex_itinerary(header, state)
    shards = partition_interval(base, window, DUAL_VERTEX_COUNT)
    seed = int.from_bytes(hashlib.sha256(bytes(header[:76])).digest()[:8], "big")

    entries = []
    for vertex_id in itinerary:
        interval = shards[vertex_id]
        if not interval.size:
            continue
        schedule = cassini_permutation(interval.size, vertex_id, seed)
        entries.append((interval, schedule))
    if not entries:
        return []

    starts = np.array([interval.start for interval, _ in entries], dtype=np.int64)
    widths = np.array([interval.size for interval, _ in entries], dtype=np.int64)
    strides = np.array([schedule.stride for _, schedule in entries], dtype=np.int64)
    origins = np.array([schedule.origin for _, schedule in entries], dtype=np.int64)
    shortest = int(widths.min())
    positions = np.arange(shortest, dtype=np.int64)
    block = starts[:, None] + (
        (origins[:, None] + positions[None, :] * strides[:, None]) % widths[:, None]
    )
    order = block.T.ravel().tolist()
    for p in range(shortest, int(widths.max())):
        mask = widths > p
        if mask.any():
            order.extend((starts + (origins + p * strides) % widths)[mask].tolist())

    if len(order) != window or len(set(order)) != window:
        raise ArithmeticError("PYTHIA 600-vertex schedule failed unique full-window coverage")
    if order and (min(order) < base or max(order) >= base + window):
        raise ArithmeticError("PYTHIA 600-vertex schedule escaped its nonce lease")
    return [int(value) for value in order[position : position + take]]


__all__ = [
    "COARSE_FACE_COUNT",
    "DUAL_VERTEX_COUNT",
    "HILBERT_DIM",
    "HILBERT_QUBITS",
    "PythiaSearchPrecompute",
    "SEARCH_ARCHITECTURE_ID",
    "precompute_pythia_search",
    "pythia_hilbert_600_nonces",
    "vertex_itinerary",
]
