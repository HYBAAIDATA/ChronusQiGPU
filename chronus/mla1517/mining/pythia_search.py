"""PYTHIA's canonical precomputed mining-search lattice.

The static search substrate is prepared before Stratum work starts:

    11D phi-weighted manifold
      -> dodecahedron/icosahedron 12+20 dual overlay (32 coarse directions)
      -> H4 600-cell tetrahedra
      -> 600 dual directions (the 120-cell's vertex set, up to radial scale)
      -> exact Turing 600-position Hilbert walk (10 position qubits + 1 coin)
      -> coverage-preserving nonce shards and Cassini affine schedules

A real job supplies the 76-byte header prefix. The live PYTHIA plan may also
supply a preferred coarse face. Those observations rank the precomputed coarse
directions and then the 600 dual vertices. A provenance-bound PYTHIA structural
model may refine the remaining coarse-face order after that explicit preferred
face; it never changes candidate membership. Turing's exact Hilbert walk then
reorders that complete 600-vertex manifold itinerary; it never removes a vertex
or a nonce from the lease. SHA256d, negotiated target, freshness and literal
pool acknowledgement remain the sole mining truth authorities.

No search-advantage claim is made here. This module proves composition,
coverage, deterministic exact-Hilbert traversal and provenance so measured
production outcomes can test whether the architecture is useful.

ROLES ON THE CANONICAL ROUTE (post exact-geometry migration):

* Production: SEARCH_ARCHITECTURE_ID, PythiaSearchPrecompute (the dataclass
  contract exact_search reuses), and _exact_hilbert_walk_rank (exact integer
  rank arithmetic). The canonical precompute is
  .exact_search.precompute_exact_search() (exact Q(phi) via
  chronus.exact_geometry) -- it is aliased as ``precompute_pythia_search``
  by resident_router.py and geodesic_support.py.
* NON-PRODUCTION FP64 LEGACY: precompute_pythia_search(), vertex_itinerary(),
  pythia_hilbert_600_nonces(), pythia_hendrix_nonces() and the FP64 helpers
  below are retained for tests and FP64 research consumers only. They are
  not called by the canonical route; nothing they return can produce
  certificates, receipts, or mining decisions.
"""

from __future__ import annotations

from chronos_one_igpu.reference_contract import require_reference, reference_only, require_production_context
import hashlib
import heapq
import importlib
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
from .hendrix_order import hendrix_schedule

SEARCH_ARCHITECTURE_ID = "pythia_dual32_11d_h4_600_hilbert"
HILBERT_QUBITS = 11
HILBERT_DIM = 1 << HILBERT_QUBITS
DUAL_VERTEX_COUNT = 600
COARSE_FACE_COUNT = 32
# C_600 has graph diameter 300. Accumulating the exact Born distribution from
# t=0 through t=300 is the smallest start-centred horizon over which every
# cycle position has been reachable at some time. It is a structural coverage
# horizon, not a performance-tuned mining parameter.
HILBERT_WALK_HORIZON = DUAL_VERTEX_COUNT // 2


def _load_coined_cycle_walk():
    """Load Turing's exact walk in installed-package or checkout layout."""
    module_names = (
        "turing_universal_quantum_computer.quantum_walk",
        (
            "turing_universal_quantum_computer."
            "turing_universal_quantum_computer.quantum_walk"
        ),
    )
    failures: list[str] = []
    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)
            return module.CoinedCycleWalk
        except ModuleNotFoundError as exc:
            failures.append(f"{module_name}: {exc}")
    raise RuntimeError(
        "PYTHIA canonical search requires Turing's exact quantum_walk package: "
        + "; ".join(failures)
    )


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


def _dual_adjacency(
    cells: Sequence[Sequence[int]],
) -> tuple[tuple[int, ...], ...]:
    """Adjacency of the dual 120-cell: 600 vertices, degree four."""
    face_to_cells: dict[tuple[int, int, int], list[int]] = {}
    for cell_id, tetrahedron in enumerate(cells):
        for face in itertools.combinations(tetrahedron, 3):
            key = tuple(sorted(int(v) for v in face))
            face_to_cells.setdefault(key, []).append(cell_id)
    adjacency = [set() for _ in cells]
    for owners in face_to_cells.values():
        if len(owners) != 2:
            raise ArithmeticError(
                "600-cell triangular face must have exactly two owners"
            )
        left, right = owners
        adjacency[left].add(right)
        adjacency[right].add(left)
    result = tuple(tuple(sorted(neighbours)) for neighbours in adjacency)
    if len(result) != DUAL_VERTEX_COUNT or any(
        len(neighbours) != 4 for neighbours in result
    ):
        raise ArithmeticError(
            "dual 120-cell adjacency must contain 600 degree-four vertices"
        )
    return result


def _exact_hilbert_walk_rank() -> tuple[tuple[int, ...], str]:
    """Return a complete 600-position rank from Turing's exact Hilbert walk.

    ``CoinedCycleWalk(600)`` uses ten position qubits plus one coin qubit, so
    the walk itself lives in an exact 11-qubit sparse Hilbert register. We
    accumulate exact Born mass over the cycle-diameter horizon. Position zero
    is retained as the first element so a live PYTHIA preferred-face decision
    remains the root of the job-specific manifold traversal; the remaining 599
    positions are ranked by exact cumulative mass with a stable index tie-break.
    """
    CoinedCycleWalk = _load_coined_cycle_walk()
    walk = CoinedCycleWalk(DUAL_VERTEX_COUNT, start=0)
    if walk.n_qubits != HILBERT_QUBITS or walk.register.dim != HILBERT_DIM:
        raise ArithmeticError("600-position Turing walk must occupy exactly 11 qubits")

    cumulative: dict[int, Any] = {}
    reached: set[int] = set()
    for step in range(HILBERT_WALK_HORIZON + 1):
        distribution = walk.position_distribution()
        if sum(distribution.values(), 0) != 1:
            raise ArithmeticError("exact quantum walk lost unit Born mass")
        for position, probability in distribution.items():
            cumulative[position] = cumulative.get(position, 0) + probability
            if probability != 0:
                reached.add(int(position))
        if step != HILBERT_WALK_HORIZON:
            walk.step()

    if reached != set(range(DUAL_VERTEX_COUNT)):
        raise ArithmeticError(
            "exact Hilbert walk horizon did not reach all 600 positions"
        )

    ranked_tail = sorted(
        range(1, DUAL_VERTEX_COUNT),
        key=lambda position: (-cumulative.get(position, 0), position),
    )
    rank = (0, *ranked_tail)
    if len(rank) != DUAL_VERTEX_COUNT or len(set(rank)) != DUAL_VERTEX_COUNT:
        raise ArithmeticError(
            "exact Hilbert walk rank must contain all 600 positions once"
        )

    digest = hashlib.sha256(
        json.dumps(
            {
                "walk": "turing_exact_coined_cycle",
                "positions": DUAL_VERTEX_COUNT,
                "qubits": HILBERT_QUBITS,
                "horizon": HILBERT_WALK_HORIZON,
                "rank": rank,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return rank, digest


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
    hilbert_walk_rank: tuple[int, ...]
    hilbert_walk_digest: str
    digest: str

    def summary(self) -> dict[str, Any]:
        edges = sum(len(neighbours) for neighbours in self.adjacency) // 2
        return {
            "schema": "pythia.search_precompute/2",
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
            "hilbert_walk": "turing_exact_coined_cycle",
            "hilbert_walk_horizon": HILBERT_WALK_HORIZON,
            "hilbert_walk_positions_reached": len(self.hilbert_walk_rank),
            "hilbert_walk_digest": self.hilbert_walk_digest,
            "all_coarse_faces_occupied": (
                len(set(self.coarse_anchor)) == COARSE_FACE_COUNT
            ),
            "digest": self.digest,
            "claim_boundary": (
                "exact Hilbert evolution and coverage-preserving search ordering only; "
                "SHA256d, target, freshness and literal pool acknowledgement remain authoritative"
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
                    "role": "hilbert_walk",
                    "owner": "Turing",
                    "authority": (
                        "exact 600-position traversal ranking; never Bitcoin proof"
                    ),
                },
                {
                    "role": "physical_execution",
                    "owner": "Chronus",
                    "authority": (
                        "execute exact authorised nonce batches on proven lanes"
                    ),
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
                    "authority": (
                        "bounded detect/repair/reprobe and measured retain/rollback"
                    ),
                },
                {
                    "role": "outcome_learning",
                    "owner": "PYTHIA",
                    "authority": (
                        "learn from measured execution and literal pool outcomes"
                    ),
                },
            ],
        }


@reference_only('pythia_search.fp64')
@lru_cache(maxsize=1)
def precompute_pythia_search() -> PythiaSearchPrecompute:
    """Build and validate the job-independent search substrate once per process."""
    require_reference('pythia_search.fp64')
    coarse_faces = build_search_crystal()
    if len(coarse_faces) != COARSE_FACE_COUNT:
        raise ArithmeticError(
            "PYTHIA coarse dual overlay must contain 12 + 20 = 32 faces"
        )
    coarse_frames = tuple(tuple(face.direction_11d) for face in coarse_faces)

    h4_vertices = generate_600cell_vertices()
    h4_cells = generate_600cell_cells(h4_vertices)
    if len(h4_vertices) != 120 or len(h4_cells) != DUAL_VERTEX_COUNT:
        raise ArithmeticError(
            "H4 600-cell must contain 120 vertices and 600 tetrahedral cells"
        )

    # The normalized cell-centroid directions are the vertices of the dual
    # 120-cell up to a common radial scale: exactly 600 high-resolution search
    # directions, preserving the repository's existing H4 construction.
    dual_vertices = tuple(cell_normals(h4_vertices, h4_cells))
    if len(dual_vertices) != DUAL_VERTEX_COUNT:
        raise ArithmeticError("dual 120-cell must contain exactly 600 vertices")
    frames_11d = tuple(tuple(lift_fold_11d(vertex)[0]) for vertex in dual_vertices)

    coarse_anchor = tuple(
        max(
            range(COARSE_FACE_COUNT),
            key=lambda face_id: _phi_dot(frame, coarse_frames[face_id]),
        )
        for frame in frames_11d
    )
    if len(set(coarse_anchor)) != COARSE_FACE_COUNT:
        raise ArithmeticError(
            "all 32 dodecahedron/icosahedron directions must own dual vertices"
        )

    adjacency = _dual_adjacency(h4_cells)

    # 600 manifold vertices are injectively labelled inside Turing's exact
    # 11-qubit basis. The separate exact coined walk below actually evolves
    # amplitudes over the 600-position subspace before mining begins.
    hilbert_basis = tuple(range(DUAL_VERTEX_COUNT))
    if max(hilbert_basis) >= HILBERT_DIM:
        raise ArithmeticError(
            "600 vertices must fit inside the exact 11-qubit Hilbert basis"
        )
    hilbert_walk_rank, hilbert_walk_digest = _exact_hilbert_walk_rank()

    digest_body = {
        "architecture_id": SEARCH_ARCHITECTURE_ID,
        "h4_cells": [list(cell) for cell in h4_cells],
        "coarse_anchor": list(coarse_anchor),
        "adjacency": [list(neighbours) for neighbours in adjacency],
        "hilbert_basis": list(hilbert_basis),
        "hilbert_walk_horizon": HILBERT_WALK_HORIZON,
        "hilbert_walk_rank": list(hilbert_walk_rank),
        "hilbert_walk_digest": hilbert_walk_digest,
    }
    digest = hashlib.sha256(
        json.dumps(
            digest_body,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    return PythiaSearchPrecompute(
        architecture_id=SEARCH_ARCHITECTURE_ID,
        coarse_frames_11d=coarse_frames,
        dual_vertices_4d=dual_vertices,
        frames_11d=frames_11d,
        coarse_anchor=coarse_anchor,
        adjacency=adjacency,
        hilbert_basis=hilbert_basis,
        hilbert_walk_rank=hilbert_walk_rank,
        hilbert_walk_digest=hilbert_walk_digest,
        digest=digest,
    )


def vertex_itinerary(
    header: bytes,
    precompute: PythiaSearchPrecompute | None = None,
    *,
    preferred_face: int | None = None,
    structure_face_scores: Sequence[float | None] | None = None,
) -> tuple[int, ...]:
    """Return the complete job-ranked manifold after exact Hilbert traversal.

    First, the real header and optional PYTHIA preferred face produce a
    connected best-first traversal of the 600-vertex dual manifold. When the
    trained structural model is active, its 32 coarse-face similarities refine
    the remaining face order after the explicit preferred face. Second, the
    precomputed exact Turing walk rank is applied to the *positions* of that
    complete manifold traversal. Position zero remains first, preserving
    PYTHIA's selected search basin; all 600 vertices remain present exactly once.
    """
    require_reference('pythia_search.fp64')
    if len(header) != 80:
        raise ValueError("header must be exactly 80 bytes")
    if preferred_face is not None and not 0 <= int(preferred_face) < COARSE_FACE_COUNT:
        raise ValueError("preferred_face must be in [0, 31]")
    if structure_face_scores is not None:
        if len(structure_face_scores) != COARSE_FACE_COUNT:
            raise ValueError("structure_face_scores must contain exactly 32 entries")
        for value in structure_face_scores:
            if value is not None and not math.isfinite(float(value)):
                raise ValueError("structure_face_scores must be finite or None")
    state = precompute or precompute_pythia_search()
    direction = _header_direction(bytes(header[:76]))

    def coarse_key(face_id: int) -> tuple[int, float, float, int]:
        preferred_rank = (
            0 if preferred_face is not None and face_id == preferred_face else 1
        )
        learned_score = (
            0.0
            if structure_face_scores is None or structure_face_scores[face_id] is None
            else float(structure_face_scores[face_id])
        )
        return (
            preferred_rank,
            -learned_score,
            -_phi_dot(direction, state.coarse_frames_11d[face_id]),
            face_id,
        )

    coarse = sorted(range(COARSE_FACE_COUNT), key=coarse_key)
    coarse_rank = {face_id: rank for rank, face_id in enumerate(coarse)}
    score = [
        (
            coarse_rank[state.coarse_anchor[vertex_id]],
            -_phi_dot(direction, frame),
            vertex_id,
        )
        for vertex_id, frame in enumerate(state.frames_11d)
    ]
    root = min(
        range(DUAL_VERTEX_COUNT),
        key=lambda vertex_id: score[vertex_id],
    )

    visited = {root}
    geometric_order = [root]
    frontier: list[tuple[tuple[int, float, int], int]] = []
    for neighbour in state.adjacency[root]:
        heapq.heappush(frontier, (score[neighbour], neighbour))
    while frontier:
        _priority, vertex_id = heapq.heappop(frontier)
        if vertex_id in visited:
            continue
        visited.add(vertex_id)
        geometric_order.append(vertex_id)
        for neighbour in state.adjacency[vertex_id]:
            if neighbour not in visited:
                heapq.heappush(frontier, (score[neighbour], neighbour))
    if (
        len(geometric_order) != DUAL_VERTEX_COUNT
        or len(set(geometric_order)) != DUAL_VERTEX_COUNT
    ):
        raise ArithmeticError("600-vertex geometric itinerary lost manifold coverage")

    order = tuple(geometric_order[position] for position in state.hilbert_walk_rank)
    if len(order) != DUAL_VERTEX_COUNT or len(set(order)) != DUAL_VERTEX_COUNT:
        raise ArithmeticError(
            "exact Hilbert traversal lost 600-vertex manifold coverage"
        )
    return order


def pythia_hilbert_600_nonces(
    header: bytes,
    base: int,
    window: int,
    *,
    position: int = 0,
    count: int | None = None,
    precompute: PythiaSearchPrecompute | None = None,
    preferred_face: int | None = None,
) -> list[int]:
    """Coverage-complete nonce permutation driven by the 600-vertex itinerary."""
    require_reference('pythia_search.fp64')
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

    # Structural training refines the supporting itinerary only. Hendrix
    # remains the plan-bound default search algorithm and candidate membership
    # remains the complete authorised lease.
    from Intelligence.mining_structure_advisor import advise_faces

    structure_advice = advise_faces(base, window)
    structure_scores = (
        structure_advice.scores if structure_advice.state == "ACTIVE" else None
    )

    state = precompute or precompute_pythia_search()
    itinerary = vertex_itinerary(
        header,
        state,
        preferred_face=preferred_face,
        structure_face_scores=structure_scores,
    )
    shards = partition_interval(base, window, DUAL_VERTEX_COUNT)
    seed = int.from_bytes(
        hashlib.sha256(bytes(header[:76])).digest()[:8],
        "big",
    )

    entries = []
    for vertex_id in itinerary:
        interval = shards[vertex_id]
        if not interval.size:
            continue
        schedule = cassini_permutation(interval.size, vertex_id, seed)
        entries.append((interval, schedule))
    if not entries:
        return []

    starts = np.array(
        [interval.start for interval, _ in entries],
        dtype=np.int64,
    )
    widths = np.array(
        [interval.size for interval, _ in entries],
        dtype=np.int64,
    )
    strides = np.array(
        [schedule.stride for _, schedule in entries],
        dtype=np.int64,
    )
    origins = np.array(
        [schedule.origin for _, schedule in entries],
        dtype=np.int64,
    )
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
        raise ArithmeticError(
            "PYTHIA 600-vertex schedule failed unique full-window coverage"
        )
    if order and (min(order) < base or max(order) >= base + window):
        raise ArithmeticError("PYTHIA 600-vertex schedule escaped its nonce lease")
    return [int(value) for value in order[position : position + take]]


def pythia_hendrix_nonces(
    header: bytes,
    base: int,
    window: int,
    *,
    position: int = 0,
    count: int | None = None,
    precompute: PythiaSearchPrecompute | None = None,
    preferred_face: int | None = None,
) -> list[int]:
    """PYTHIA's canonical Hendrix traversal over the complete structured itinerary.

    PYTHIA first constructs the complete 32 -> 11D -> 600-vertex/Turing
    structural itinerary. Hendrix then supplies the default traversal of that
    complete itinerary by applying its verified coprime-stride permutation to
    itinerary positions. The composition changes order only: every nonce in
    the authorised lease remains present exactly once.
    """
    require_reference('pythia_search.fp64')
    if type(window) is not int or window < 0:
        raise ValueError("window must be a non-negative integer")
    if type(position) is not int or not 0 <= position <= window:
        raise ValueError("position must be inside the window")
    take = window - position if count is None else count
    if type(take) is not int or take < 0 or position + take > window:
        raise ValueError("count must fit inside the remaining window")
    if window == 0 or take == 0:
        return []

    structural = pythia_hilbert_600_nonces(
        header,
        base,
        window,
        precompute=precompute,
        preferred_face=preferred_face,
    )
    schedule = hendrix_schedule(window)
    if not schedule.verify():
        raise ArithmeticError("Hendrix schedule invariant failure")
    order = [structural[schedule.nonce_at(index)] for index in range(window)]
    if len(order) != window or len(set(order)) != window:
        raise ArithmeticError("Hendrix composition lost full-window coverage")
    if order and (min(order) < base or max(order) >= base + window):
        raise ArithmeticError("Hendrix composition escaped its nonce lease")
    return order[position : position + take]


__all__ = [
    "COARSE_FACE_COUNT",
    "DUAL_VERTEX_COUNT",
    "HILBERT_DIM",
    "HILBERT_QUBITS",
    "HILBERT_WALK_HORIZON",
    "PythiaSearchPrecompute",
    "SEARCH_ARCHITECTURE_ID",
    "precompute_pythia_search",
    "pythia_hilbert_600_nonces",
    "pythia_hendrix_nonces",
    "vertex_itinerary",
]
