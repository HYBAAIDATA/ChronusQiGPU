"""PYTHIA exact geometry and genuine exact coined quantum-walk preparation."""

from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
import hashlib
import heapq
import json
import threading
from collections import OrderedDict
from chronus.math.exact_geometry import (
    Q,
    encode,
    score,
    m32,
    h4,
    m32_relations,
    exact_walk_reference,
)
from typing import Any

SEARCH_ARCHITECTURE_ID = "pythia_dual32_11d_h4_600_hilbert"
HILBERT_QUBITS = 11
HILBERT_DIM = 1 << HILBERT_QUBITS
DUAL_VERTEX_COUNT = 600
COARSE_FACE_COUNT = 32
DIM = 11
HILBERT_WALK_HORIZON = 300

def _exact_hilbert_walk_rank() -> tuple[tuple[int, ...], str]:
    """Return a complete 600-position rank from Turing's exact Hilbert walk.

    ``CoinedCycleWalk(600)`` uses ten position qubits plus one coin qubit, so
    the walk itself lives in an exact 11-qubit sparse Hilbert register. We
    accumulate exact Born mass over the cycle-diameter horizon. Position zero
    is retained as the first element so a live PYTHIA preferred-face decision
    remains the root of the job-specific manifold traversal; the remaining 599
    positions are ranked by exact cumulative mass with a stable index tie-break.
    """
    from turing.exact.geometry.coined_cycle import CoinedCycleWalk
    walk = CoinedCycleWalk(DUAL_VERTEX_COUNT, start=0)
    if walk.n_qubits != HILBERT_QUBITS or walk.register.space.dimension != HILBERT_DIM:
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



def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


@dataclass(frozen=True)
class ExactSearchState:
    architecture_id: str
    coarse_frames_11d: tuple
    dual_vertices_4d: tuple
    frames_11d: tuple
    coarse_anchor: tuple
    adjacency: tuple
    hilbert_basis: tuple
    hilbert_walk_rank: tuple
    hilbert_walk_digest: str
    digest: str
    geometry_encoded: str
    math_domain: str = "exact_q_phi_positive_radicals"

    def summary(self) -> dict[str, Any]:
        edges = sum(len(neighbours) for neighbours in self.adjacency) // 2
        return {
            "schema": "pythia.search_precompute/2",
            "architecture_id": self.architecture_id,
            "state": "READY",
            "prepared_before_pool_work": None,
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


@lru_cache(maxsize=1)
def precompute_exact_search():
    faces = m32()
    vertices, cells, normals, adj = h4()
    coarse = tuple(r.fold11() for r in faces)
    fine = tuple(r.fold11() for r in normals)
    # Common positive denominator of each source ray cancels in this comparison.
    anchors = tuple(
        max(range(32), key=lambda i: score(r.numerator, coarse[i])) for r in fine
    )
    if set(anchors) != set(range(32)):
        raise ArithmeticError("32 exact regions must all be occupied")
    rank, walk_digest = _exact_hilbert_walk_rank()
    if (rank, walk_digest) != exact_walk_reference():
        raise ArithmeticError(
            "Turing quantum walk disagrees with independent exact amplitude replay"
        )
    a, d = m32_relations()
    payload = {
        "schema": "chronus.exact_geometry/2",
        "vertices": [[encode(x) for x in v] for v in vertices],
        "cells": [list(c) for c in cells],
        "m32": [r.transport() for r in faces],
        "coarse_11d": [r.transport() for r in coarse],
        "normals_4d": [r.transport() for r in normals],
        "frames_11d": [r.transport() for r in fine],
        "m32_adjacency": [list(x) for x in a],
        "m32_dual_incidence": [list(x) for x in d],
        "coarse_anchor": list(anchors),
        "adjacency": [list(x) for x in adj],
        "quantum": {
            "algorithm": "turing_exact_coined_cycle",
            "coin": "exact_Hadamard",
            "shift": "unitary_C600_permutation",
            "register_qubits": 11,
            "basis_dimension": 2048,
            "steps": 300,
            "rank": list(rank),
            "digest": walk_digest,
            "not_physical_qpu_claim": True,
        },
        "approximations_used": False,
        "learned_scores_used": False,
    }
    return ExactSearchState(
        SEARCH_ARCHITECTURE_ID,
        coarse,
        normals,
        fine,
        anchors,
        adj,
        tuple(range(600)),
        rank,
        walk_digest,
        digest(payload),
        canonical(payload),
    )


# Exact results are pure functions of (header[:76], geometry). Every nonce
# lease of one job/extranonce shares header[:76], so recomputing the exact
# rational scores for each plan repeated ~1 s of identical arithmetic on the
# mining event loop. A small bounded memo returns the identical tuples; the
# inputs are still validated on every call. Keyed by the geometry's content
# digests and the state object (entries hold no reference, so the bounded
# LRU is the only lifetime).
_EXACT_MEMO_SIZE = 64
_exact_memo: "OrderedDict[tuple, tuple]" = OrderedDict()
_exact_memo_lock = threading.Lock()


def _memo(key, compute):
    with _exact_memo_lock:
        hit = _exact_memo.get(key)
        if hit is not None:
            _exact_memo.move_to_end(key)
            return hit
    value = compute()
    with _exact_memo_lock:
        _exact_memo[key] = value
        _exact_memo.move_to_end(key)
        while len(_exact_memo) > _EXACT_MEMO_SIZE:
            _exact_memo.popitem(last=False)
    return value


def _state_key(state):
    # Content digests plus the object itself: a different state object that
    # merely claims the same digest never reuses another object's result.
    return (state.digest, state.hilbert_walk_digest, id(state))


def exact_face_order(header, state=None):
    """Header-bound exact geometric ordering; no predictor/advisory input."""
    if not isinstance(header, bytes) or len(header) != 80:
        raise ValueError("header80 required")
    state = state or precompute_exact_search()
    if not isinstance(state, ExactSearchState):
        raise ValueError("exact geometry required")
    return _memo(
        ("faces", bytes(header[:76]), _state_key(state)),
        lambda: _exact_face_order(header, state),
    )


def _exact_face_order(header, state):
    h = hashlib.sha256(header[:76]).digest()
    direction = tuple(Q(Fraction(2 * h[i] - 255, 255)) for i in range(11))
    return tuple(
        sorted(
            range(32), key=lambda i: (-score(direction, state.coarse_frames_11d[i]), i)
        )
    )


@dataclass(frozen=True)
class ExactMiningDirective:
    lane_order: tuple
    header_digest: str
    target_hex: str
    base_step: int
    window: int
    geometry_digest: str
    quantum_digest: str

    def as_evidence(self):
        return {
            "schema": "pythia.exact_mining_directive/1",
            "authority": "PYTHIA",
            "algorithm": "hendrix_coprime_stride",
            "lane_order": list(self.lane_order),
            "header_digest": self.header_digest,
            "target_hex": self.target_hex,
            "base_step": self.base_step,
            "window": self.window,
            "geometry_digest": self.geometry_digest,
            "quantum_digest": self.quantum_digest,
            "approximations_used": False,
            "heuristics_used": False,
            "physical_qpu_executed": False,
            "quantum_algorithm": "turing_exact_coined_cycle",
        }


def exact_mining_directive(*, header, target_be, base_step, window, state=None):
    """PYTHIA's exact production planning contract, not Chronus intelligence."""
    if not isinstance(target_be, bytes) or len(target_be) != 32:
        raise ValueError("target256 required")
    if (
        type(base_step) is not int
        or type(window) is not int
        or window <= 0
        or base_step < 0
        or base_step + window > 2**32
    ):
        raise ValueError("bounded uint32 lease required")
    state = state or precompute_exact_search()
    lanes = exact_face_order(header, state)
    return ExactMiningDirective(
        lanes,
        hashlib.sha256(header[:76]).hexdigest(),
        target_be.hex(),
        base_step,
        window,
        state.digest,
        state.hilbert_walk_digest,
    )


def exact_vertex_itinerary(
    header, state=None, *, preferred_face=None, use_hilbert=True
):
    if not isinstance(header, bytes) or len(header) != 80:
        raise ValueError("header80 required")
    if preferred_face is not None and (
        type(preferred_face) is not int or not 0 <= preferred_face < 32
    ):
        raise ValueError("authorised face0..31 required")
    state = state or precompute_exact_search()
    if not isinstance(state, ExactSearchState):
        raise ValueError("exact geometry required; no numerical fallback")
    canonical_faces = exact_face_order(header, state)
    if preferred_face is not None and preferred_face != canonical_faces[0]:
        raise ValueError("advisory face cannot enter exact first-principles profile")
    return _memo(
        ("itinerary", bytes(header[:76]), _state_key(state), bool(use_hilbert)),
        lambda: _exact_vertex_itinerary(header, state, canonical_faces, use_hilbert),
    )


def _exact_vertex_itinerary(header, state, canonical_faces, use_hilbert):
    h = hashlib.sha256(header[:76]).digest()
    direction = tuple(Q(Fraction(2 * h[i] - 255, 255)) for i in range(11))
    coarse = canonical_faces
    ranks = {f: i for i, f in enumerate(coarse)}
    priority = tuple(
        (ranks[state.coarse_anchor[i]], -score(direction, r), i)
        for i, r in enumerate(state.frames_11d)
    )
    root = min(range(600), key=lambda i: priority[i])
    seen = {root}
    order = [root]
    queue = []
    for n in state.adjacency[root]:
        heapq.heappush(queue, (priority[n], n))
    while queue:
        _p, i = heapq.heappop(queue)
        if i in seen:
            continue
        seen.add(i)
        order.append(i)
        for n in state.adjacency[i]:
            if n not in seen:
                heapq.heappush(queue, (priority[n], n))
    if len(seen) != 600:
        raise ArithmeticError("exact geometry lost coverage")
    return (
        tuple(order[i] for i in state.hilbert_walk_rank)
        if use_hilbert
        else tuple(order)
    )


def exact_reference_nonces(header, base, window, *, preferred_face=None):
    """Independent bounded reference, not used by resident hot execution."""
    from .cassini import cassini_permutation, partition_interval
    from .cassini import hendrix_stride

    if type(window) is not int or not 0 < window <= 65536:
        raise ValueError("bounded reference window required")
    parts = partition_interval(base, window, 600)
    seed = int.from_bytes(hashlib.sha256(header[:76]).digest()[:8], "big")
    segments = []
    for i in exact_vertex_itinerary(header, preferred_face=preferred_face):
        p = parts[i]
        if p.size:
            s = cassini_permutation(p.size, i, seed)
            segments.append(
                [p.start + (s.origin + j * s.stride) % p.size for j in range(p.size)]
            )
    order = [
        s[i] for i in range(max(map(len, segments))) for s in segments if i < len(s)
    ]
    stride = hendrix_stride(window)
    return [order[(i * stride) % window] for i in range(window)]
