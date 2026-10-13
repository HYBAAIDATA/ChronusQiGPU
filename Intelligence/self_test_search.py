"""Self-test: intelligence -> 11D search topology wiring.

Verifies the ontology end to end against the hardened substrate:

1. The 32-face compass builds with a Cassini certificate on every face.
2. ``find`` reaches the exact anchor a state was stored at and retrieves
   its payload through the anchor index.
3. ``navigate`` walks the geodesic between two anchors, materialising and
   verifying each anchor on the path.
4. A corrupted node's stored record is repaired from the prime-exponent
   substrate when traversal reaches its anchor.
5. The agentic controller, orchestrator, and plasticity layers all drive
   the same engine.

Run directly (``python -m Intelligence.self_test_search``) or through
``tests/test_search_ontology.py`` under pytest.
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: search_api + hardened_unified_substrate

from __future__ import annotations

import asyncio
from typing import Any, Dict

try:
    from .hardened_unified_substrate import (
        ManifoldCurvature,
        PrimeStorageManifold,
        TensorCoreGPU_Context,
    )
except ImportError:  # pragma: no cover - top-level script use
    from hardened_unified_substrate import (
        ManifoldCurvature,
        PrimeStorageManifold,
        TensorCoreGPU_Context,
    )

from .agentic_controller_search import AgenticSearchController
from .orchestrator_search import SearchAwareOrchestrator
from .poincare_cassini_search import (
    DodecaIcosahedron32,
    anchor_of,
    anchor_to_vector,
)
from .plasticity_search import PlasticitySearch
from .search_api import SearchAPI


def _build_manifold() -> tuple:
    gpu = TensorCoreGPU_Context()
    manifold = PrimeStorageManifold(gpu, n_primes=25)
    return gpu, manifold


def test_compass_construction() -> Dict[str, Any]:
    overlay = DodecaIcosahedron32()
    assert len(overlay) == 32
    assert all(f.cassini_determinant in (-1, 1) for f in overlay.faces)
    norms = [f.golden_norm for f in overlay.faces]
    assert all(abs(n - 1.0) < 1e-12 for n in norms)
    return {"status": "PASS", "faces": len(overlay)}


def test_anchor_lift_roundtrip() -> Dict[str, Any]:
    for a in (0, 1, 7, 18, 29, 47, 76, 89):
        assert anchor_of(anchor_to_vector(a)) == a
    return {"status": "PASS"}


def test_search_api_find() -> Dict[str, Any]:
    gpu, manifold = _build_manifold()
    try:
        payload = b"test payload for search"
        uid = manifold.ingest_sync(payload, ManifoldCurvature.GOLDEN_DENSE)
        anchor = manifold.tensors[uid].integer_anchor

        search = SearchAPI(manifold)
        response = search.find({"anchor": float(anchor)})
        assert response.cassini_valid, "Cassini validation failed"
        assert response.found, "search did not converge"
        assert response.anchor == anchor
        assert response.payload == payload
        return {"status": "PASS", "anchor": anchor, "iterations": response.iterations}
    finally:
        gpu.shutdown()


def test_search_api_navigate() -> Dict[str, Any]:
    gpu, manifold = _build_manifold()
    try:
        uid1 = manifold.ingest_sync(b"payload1", ManifoldCurvature.GOLDEN_DENSE)
        uid2 = manifold.ingest_sync(b"payload2", ManifoldCurvature.GOLDEN_DENSE)
        a1 = manifold.tensors[uid1].integer_anchor
        a2 = manifold.tensors[uid2].integer_anchor

        search = SearchAPI(manifold)
        response = search.navigate(a1, a2)
        assert response.found
        assert response.anchor == a2
        assert response.path[-1] == a2
        return {"status": "PASS", "path_length": len(response.path)}
    finally:
        gpu.shutdown()


def test_search_repairs_corrupted_node() -> Dict[str, Any]:
    gpu, manifold = _build_manifold()
    try:
        payload = b"precious state record"
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
        assert manifold.self_healing.heal_log
        return {"status": "PASS", "healed_anchor": anchor}
    finally:
        gpu.shutdown()


def test_agentic_controller_decide() -> Dict[str, Any]:
    gpu, manifold = _build_manifold()
    try:
        controller = AgenticSearchController(manifold)
        decision = controller.decide({"action": "test", "value": 42})
        assert "decision" in decision
        assert controller.verify_state()
        return {"status": "PASS", "decision": decision["decision"]}
    finally:
        gpu.shutdown()


def test_search_orchestrator() -> Dict[str, Any]:
    gpu, manifold = _build_manifold()
    try:
        orchestrator = SearchAwareOrchestrator(manifold)
        result = asyncio.run(orchestrator.execute_intent({"type": "verify", "anchor": 1}))
        assert "valid" in result
        return {"status": "PASS", "result": result}
    finally:
        gpu.shutdown()


def test_plasticity_pathway() -> Dict[str, Any]:
    gpu, manifold = _build_manifold()
    try:
        plastic = PlasticitySearch(manifold)
        path = plastic.discover_pathway({"anchor": 1.0}, {"anchor": 18.0})
        assert path is not None and path[-1] == 18
        plastic.reinforce_pathway(path, reward=1.0)
        report = plastic.report()
        assert isinstance(report, dict)
        return {"status": "PASS", "path_length": len(path)}
    finally:
        gpu.shutdown()


def test_full_wiring() -> Dict[str, Any]:
    gpu, manifold = _build_manifold()
    try:
        orchestrator = SearchAwareOrchestrator(manifold)
        controller = AgenticSearchController(manifold)

        uid = manifold.ingest_sync(b"full wiring test", ManifoldCurvature.GOLDEN_DENSE)
        anchor = manifold.tensors[uid].integer_anchor

        response = orchestrator.search.find({"anchor": float(anchor)})
        assert response.cassini_valid and response.anchor == anchor

        decision = controller.decide({"action": "full_wiring", "anchor": anchor})
        assert "decision" in decision
        return {"status": "PASS", "full_wiring": True}
    finally:
        gpu.shutdown()


def run_all() -> Dict[str, Any]:
    results = {}
    for test in (
        test_compass_construction,
        test_anchor_lift_roundtrip,
        test_search_api_find,
        test_search_api_navigate,
        test_search_repairs_corrupted_node,
        test_agentic_controller_decide,
        test_search_orchestrator,
        test_plasticity_pathway,
        test_full_wiring,
    ):
        results[test.__name__] = test()
    return results


if __name__ == "__main__":
    print("Testing full intelligence -> 11D search topology wiring...")
    for name, result in run_all().items():
        print(f"  {name}: {result['status']} {result}")
