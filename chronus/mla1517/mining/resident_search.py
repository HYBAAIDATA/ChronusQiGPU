"""PYTHIA issuance of compact resident execution descriptions.

Canonical geometry and Hendrix constructors are reused unchanged. This is
planning-side code: Chronus consumes the sealed result, not the live advisor.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache

from chronus.resident_hendrix import SCHEMA, ResidentHendrix, plan_identity, seal


def m32_manifest():
    from chronus.exact_geometry import m32, m32_relations

    faces = m32()
    adj, dual = m32_relations()
    return {
        "version": "exact_icosahedral_dual32/2",
        "face_ids": list(range(32)),
        "directions_3d": [r.transport() for r in faces],
        "adjacency": [list(x) for x in adj],
        "dual_incidence": [list(x) for x in dual],
    }


def geometry_manifest(state):
    from .exact_search import ExactSearchState
    from lucas.fold import t_phi_fold, t_phi_unfold

    if not isinstance(state, ExactSearchState):
        raise ValueError("numerical geometry cannot enter the production exact profile")
    raw = state.geometry_encoded.encode()
    folded = t_phi_fold(raw)
    if t_phi_unfold(folded, len(raw)) != raw:
        raise ArithmeticError("exact transport restoration failed")
    value = {
        "version": "exact_dual32_phi11d_h4_600/2",
        "math_domain": state.math_domain,
        "precompute_digest": state.digest,
        "m32": m32_manifest(),
        "coarse_anchor": list(state.coarse_anchor),
        "adjacency": [list(x) for x in state.adjacency],
        "transport": {
            "encoding": "lucas.M15.exact_q_phi_positive_radicals_v2",
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
    from Intelligence.search_crystal import cassini_permutation, partition_interval
    from .hendrix_order import hendrix_schedule
    from .exact_search import ExactSearchState, exact_vertex_itinerary, exact_face_order

    if plan.nonce_order != "hendrix_coprime_stride":
        raise ValueError("only canonical Hendrix may be resident-lowered")
    if len(header) != 80 or len(target_be) != 32:
        raise ValueError("canonical header80 and target256 required")
    if plan.evidence_refs.get("search_precompute_digest") != state.digest:
        raise ValueError("SearchPlan references a different mathematical substrate")
    if not isinstance(state, ExactSearchState):
        raise ValueError(
            "exact first-principles substrate required; no approximate fallback"
        )
    if tuple(plan.lane_order) != exact_face_order(header, state):
        raise ValueError(
            "learned/advisory lane ordering is excluded from exact profile"
        )
    if plan.schedule:
        raise ValueError("advisory nonce proposals are excluded from exact profile")
    itinerary = exact_vertex_itinerary(
        header, state, preferred_face=plan.preferred_face, use_hilbert=use_hilbert
    )
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
                "structure_advice": {
                    "state": "EXCLUDED_BY_EXACT_CONTRACT",
                    "heuristics_used": False,
                },
            },
            "authority": {"plan": "PYTHIA", "execution": "Chronus", "proof": "SHA256d"},
        }
    )
    result.validate()
    return result
