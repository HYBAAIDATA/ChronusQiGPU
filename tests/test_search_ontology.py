"""Ontology contract tests: intelligence -> 11D search topology.

Dedicated CI check for the search ontology. Covers the four roles of the
topology — map (anchors), compass (32 faces), pathfinder (geodesic
traversal), verifier (Cassini + parity repair) — plus the six wiring
points between the intelligence layer and the engine.
"""

from __future__ import annotations

import asyncio

import numpy as np
import pytest

from Intelligence.hardened_unified_substrate import (
    ManifoldCurvature,
    PrimeStorageManifold,
    TensorCoreGPU_Context,
)

from Intelligence.agentic_controller_search import AgenticSearchController
from Intelligence.intent_compiler import Intent, IntentCompiler
from Intelligence.orchestrator_search import SearchAwareOrchestrator
from Intelligence.poincare_cassini_search import (
    DodecaIcosahedron32,
    PoincareCassiniSearch,
    anchor_of,
    anchor_to_vector,
    weighted_norm,
)
from Intelligence.plasticity_search import PlasticitySearch
from Intelligence.search_api import SearchAPI


@pytest.fixture()
def manifold():
    gpu = TensorCoreGPU_Context()
    m = PrimeStorageManifold(gpu, n_primes=25)
    yield m
    gpu.shutdown()


# ----------------------------------------------------------------------
# Compass
# ----------------------------------------------------------------------


def test_compass_has_32_cassini_certified_faces():
    overlay = DodecaIcosahedron32()
    assert len(overlay) == 32
    solids = {f.solid for f in overlay.faces}
    assert solids == {"dodecahedron", "icosahedron"}
    assert sum(1 for f in overlay.faces if f.solid == "dodecahedron") == 12
    assert sum(1 for f in overlay.faces if f.solid == "icosahedron") == 20
    for face in overlay.faces:
        assert face.cassini_determinant in (-1, 1)
        assert abs(face.golden_norm - 1.0) < 1e-12


def test_anchor_lift_is_exact_inverse():
    for anchor in range(90):
        assert anchor_of(anchor_to_vector(anchor)) == anchor


# ----------------------------------------------------------------------
# Pathfinder
# ----------------------------------------------------------------------


def test_geodesic_search_converges_to_target_anchor(manifold):
    engine = PoincareCassiniSearch(manifold=manifold)
    for target in (3, 18, 29, 47, 76, 89):
        result = engine.navigate(1, target)
        assert result.converged, f"did not converge to anchor {target}"
        assert result.target_anchor == target
        assert result.path[-1] == target
        assert result.final_precision < 1e-8
        assert result.cassini_valid
        assert result.faces_fired >= 32
        assert result.faces_fired % 32 == 0


def test_search_converges_in_log_steps(manifold):
    """Pisot-style geometric convergence: far targets in O(log 1/eps) steps."""
    engine = PoincareCassiniSearch(manifold=manifold, epsilon=1e-8)
    result = engine.navigate(1, 89)
    assert result.converged
    assert result.iterations <= 40


def test_traversal_materialises_anchors(manifold):
    engine = PoincareCassiniSearch(manifold=manifold)
    result = engine.navigate(1, 47)
    assert result.converged
    for anchor in result.path:
        assert manifold.get_by_anchor(anchor) is not None


# ----------------------------------------------------------------------
# Verifier + self-healing
# ----------------------------------------------------------------------


def test_corrupted_node_repaired_from_prime_exponents(manifold):
    payload = b"state record that must survive"
    uid = manifold.ingest_sync(payload, ManifoldCurvature.GOLDEN_DENSE)
    tensor = manifold.tensors[uid]
    anchor = tensor.integer_anchor

    tensor.cassini_parity = -tensor.cassini_parity
    tensor.sparse_topology = {0: 1}

    search = SearchAPI(manifold)
    response = search.find({"anchor": float(anchor)})
    assert response.found
    assert anchor in response.healed_anchors
    assert tensor.cassini_parity == (-1) ** anchor
    assert response.payload == payload
    assert any(
        event.get("kind") == "prime_exponent_restore" for event in manifold.self_healing.heal_log
    )


# ----------------------------------------------------------------------
# Intent compiler
# ----------------------------------------------------------------------


def test_intent_compiler_anchor_roundtrip(manifold):
    compiler = IntentCompiler(manifold)
    for anchor in (1, 11, 47, 89):
        for kind, key in (
            ("verify", "anchor"),
            ("navigate", "target_anchor"),
            ("expand", "current_anchor"),
        ):
            v = compiler.compile(Intent(intent_type=kind, payload={key: anchor}))
            expected = anchor if kind != "expand" else (anchor + 1) % 90
            assert anchor_of(v) == expected


def test_intent_compiler_find_is_deterministic(manifold):
    compiler = IntentCompiler(manifold)
    features = {"density": 0.7, "entropy": 0.2}
    v1 = compiler.compile(Intent(intent_type="find", payload={"features": features}))
    v2 = compiler.compile(Intent(intent_type="find", payload={"features": features}))
    assert np.allclose(v1, v2)
    assert weighted_norm(v1) < 90


# ----------------------------------------------------------------------
# API + controller + orchestrator + plasticity
# ----------------------------------------------------------------------


def test_search_api_find_retrieve_and_create(manifold):
    payload = b"payload through the anchor index"
    uid = manifold.ingest_sync(payload, ManifoldCurvature.GOLDEN_DENSE)
    anchor = manifold.tensors[uid].integer_anchor

    search = SearchAPI(manifold)
    response = search.find({"anchor": float(anchor)})
    assert response.found and response.anchor == anchor
    assert response.payload == payload

    again = search.search_or_create({"anchor": float(anchor)}, b"ignored")
    assert again == anchor


def test_agentic_controller_decide_and_navigate(manifold):
    controller = AgenticSearchController(manifold)
    created = controller.decide({"action": "x", "value": 1})
    assert created["decision"] == "create"
    assert controller.verify_state()

    reused = controller.decide({"action": "x", "value": 1})
    assert reused["decision"] in ("reuse", "create")

    nav = controller.navigate_to(18)
    assert nav["arrived"]
    assert controller.current_anchor == 18


def test_orchestrator_execute_intent(manifold):
    orch = SearchAwareOrchestrator(manifold)
    out = asyncio.run(orch.execute_intent({"type": "verify", "anchor": 7}))
    assert out == {"valid": True}

    nav = asyncio.run(orch.execute_intent({"type": "navigate", "from_anchor": 1, "to_anchor": 29}))
    assert nav["arrived"] and nav["anchor"] == 29

    stats = orch.stats()
    assert stats["manifold_tensors"] >= 1


def test_plasticity_discovers_and_reinforces_pathway(manifold):
    plastic = PlasticitySearch(manifold)
    path = plastic.discover_pathway({"anchor": 1.0}, {"anchor": 29.0})
    assert path is not None and path[-1] == 29
    plastic.reinforce_pathway(path, reward=1.0)
    report = plastic.report()
    assert isinstance(report, dict)
