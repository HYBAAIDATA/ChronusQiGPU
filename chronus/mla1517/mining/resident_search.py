"""PYTHIA issuance of compact resident execution descriptions.

Canonical geometry and Hendrix constructors are reused unchanged. This is
planning-side code: Chronus consumes the sealed result, not the live advisor.
"""

from __future__ import annotations

import hashlib
import struct
from functools import lru_cache

from chronus.resident_hendrix import SCHEMA, ResidentHendrix, plan_identity, seal


def m32_manifest():
    """Canonical 12 dual-dodecahedral + 20 icosahedral face identities."""
    import math

    try:
        from pythia_turing_math import generate_dual_overlay_frame
    except ImportError:
        from chronus.mla1517_platform.python.pythia_turing_math import generate_dual_overlay_frame

    directions = generate_dual_overlay_frame()

    def dot(a, b):
        return sum(x * y for x, y in zip(a, b))

    adjacency, dual = [], []
    for i, point in enumerate(directions):
        same = range(12) if i < 12 else range(12, 32)
        other = range(12, 32) if i < 12 else range(12)
        near = max(dot(point, directions[j]) for j in same if j != i)
        incidence = max(dot(point, directions[j]) for j in other)
        adjacency.append(
            [
                j
                for j in same
                if j != i and math.isclose(dot(point, directions[j]), near, abs_tol=1e-12)
            ]
        )
        dual.append(
            [j for j in other if math.isclose(dot(point, directions[j]), incidence, abs_tol=1e-12)]
        )
    if any(
        len(adjacency[i]) != (5 if i < 12 else 3) or len(dual[i]) != (5 if i < 12 else 3)
        for i in range(32)
    ):
        raise ArithmeticError("canonical M32 dual incidence failed")
    return {
        "version": "icosahedral_dual32/1",
        "directions_3d": directions,
        "face_ids": list(range(32)),
        "adjacency": adjacency,
        "dual_incidence": dual,
        "face_kind": ["dual_dodecahedron_face"] * 12 + ["icosahedron_face"] * 20,
    }


def geometry_manifest(state):
    from lucas.fold import t_phi_fold, t_phi_unfold

    floats = [
        x
        for group in (state.coarse_frames_11d, state.frames_11d, state.dual_vertices_4d)
        for row in group
        for x in row
    ]
    raw = struct.pack("<" + "d" * len(floats), *floats)
    folded = t_phi_fold(raw)
    if t_phi_unfold(folded, len(raw)) != raw:
        raise ArithmeticError("canonical exact geometry transport failed")
    value = {
        "version": "dual32_phi11d_h4_600/1",
        "precompute_digest": state.digest,
        "m32": m32_manifest(),
        "coarse_anchor": list(state.coarse_anchor),
        "adjacency": [list(x) for x in state.adjacency],
        "transport": {
            "encoding": "lucas.M15.ieee754_binary64_le",
            "original_bytes": len(raw),
            "folded_hex": folded.hex(),
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
        },
    }
    return {**value, "digest": seal(value)}


@lru_cache(maxsize=4)
def _geometry(state):
    return geometry_manifest(state)


def compile_hendrix_plan(plan, header, target_be, state, *, use_hilbert=True):
    """Called by PYTHIA after its authority decision, never by an optimiser."""
    from Intelligence.mining_structure_advisor import advise_faces
    from Intelligence.search_crystal import cassini_permutation, partition_interval
    from .hendrix_order import hendrix_schedule
    from .pythia_search import vertex_itinerary

    if plan.nonce_order != "hendrix_coprime_stride":
        raise ValueError("only canonical Hendrix may be resident-lowered")
    if len(header) != 80 or len(target_be) != 32:
        raise ValueError("canonical header80 and target256 required")
    if plan.evidence_refs.get("search_precompute_digest") != state.digest:
        raise ValueError("SearchPlan references a different mathematical substrate")
    advice = advise_faces(plan.base_step, plan.window)
    scores = advice.scores if advice.state == "ACTIVE" else None
    # The legacy reference always selects the Turing walk. Plans can now
    # explicitly decline it; no capability invocation is silently introduced.
    itinerary = vertex_itinerary(
        header, state, preferred_face=plan.preferred_face, structure_face_scores=scores
    )
    if not use_hilbert:
        restored = [0] * 600
        for output_position, source_position in enumerate(state.hilbert_walk_rank):
            restored[source_position] = itinerary[output_position]
        itinerary = tuple(restored)
    parts = partition_interval(plan.base_step, plan.window, 600)
    seed = int.from_bytes(hashlib.sha256(header[:76]).digest()[:8], "big")
    shards = []
    for vertex in itinerary:
        part = parts[vertex]
        schedule = cassini_permutation(part.size, vertex, seed) if part.size else None
        shards.append(
            [
                vertex,
                state.coarse_anchor[vertex],
                part.start,
                part.size,
                schedule.stride if schedule else 1,
                schedule.origin if schedule else 0,
                schedule.cassini_determinant if schedule else (-1) ** (vertex + 2),
            ]
        )
    result = ResidentHendrix.issue(
        {
            "schema": SCHEMA,
            "algorithm": plan.nonce_order,
            "plan_digest": seal(plan_identity(plan)),
            "plan_id": plan.plan_id,
            "generation": plan.generation,
            "pool_session_id": plan.pool_session_id,
            "header_digest": hashlib.sha256(header[:76]).hexdigest(),
            "target_hex": target_be.hex(),
            "base": plan.base_step,
            "window": plan.window,
            "hendrix_stride": hendrix_schedule(plan.window).stride,
            "shards": shards,
            "geometry": _geometry(state),
            "support": {
                "turing_hilbert": bool(use_hilbert),
                "hilbert_digest": state.hilbert_walk_digest if use_hilbert else None,
                "structure_advice": advice.as_dict(),
            },
            "authority": {"plan": "PYTHIA", "execution": "Chronus", "proof": "SHA256d"},
        }
    )
    result.validate()
    return result
