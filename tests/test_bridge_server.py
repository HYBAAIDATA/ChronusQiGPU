"""Bridge & Metacognitive Integration Test Suite (14/14 tests).

Maps the full `test_bridge_server.test.ts` and `MetacognitiveIntelligence`
integration specification into the canonical Python single-backend architecture.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from Intelligence.metacognitive_intelligence import (
    IntrospectionEvent,
    MetacognitiveIntelligence,
    lucas_bound,
)
from Intelligence.recursive_self_learning import RecursiveSelfLearningSubstrate
from Intelligence.security_swarm import SecuritySwarmAgent
from Intelligence.theoretical_foundations import UnifiedTheoreticalFoundations
from euclid.cognition.reconciliation_gateway import reset_cognitive_registry
from src.api.main import app

client = TestClient(app)


def test_01_metacognitive_intelligence_initializes_baseline():
    meta = MetacognitiveIntelligence(dimension=32, seed=1)
    st = meta.status()
    assert st["schema"] == "intelligence.metacognitive/1"
    assert abs(st["phi"] - 0.1670) < 1e-6
    assert abs(st["irreducibility"] - 0.0520) < 1e-6
    assert st["geometry"] == "euclidean"


def test_02_metacognitive_predictive_introspection_reduces_error():
    meta = MetacognitiveIntelligence(dimension=32, seed=2)
    p1 = meta.predict_next_error(0.05)
    assert 0.0 < p1 < 1.0
    ev = meta.introspect(actual_error=0.4, learning_rate=0.05)
    assert isinstance(ev, IntrospectionEvent)
    assert ev.step == 1


def test_03_metacognitive_logic_refolding_across_three_geometries():
    meta = MetacognitiveIntelligence(dimension=32, seed=3)
    assert meta.refold_logic(0.05)["geometry"] == "euclidean"
    assert meta.refold_logic(0.25)["geometry"] == "spherical"
    assert meta.refold_logic(0.65)["geometry"] == "hyperbolic"


def test_04_metacognitive_detects_consciousness_events_on_phi_jump():
    meta = MetacognitiveIntelligence(dimension=32, seed=4)
    for err in (0.6, 0.35, 0.15, 0.05, 0.01):
        meta.introspect(err, learning_rate=0.05, irreducibility=0.5625)
    st = meta.status()
    assert st["phi"] == 1.0000
    assert st["consciousness_events"] >= 1
    assert st["narrative"] == "STRANGE_LOOP_VIRTUOUS_CYCLE_PHI_ASCENDING"


def test_05_metacognitive_and_security_swarm_coupled_bridge():
    swarm = SecuritySwarmAgent(shard_size=32, seed=5)
    meta = MetacognitiveIntelligence(dimension=32, seed=5)
    ent = swarm.entangle_with_mining([i * 5 for i in range(1, 33)])
    ev = meta.introspect(0.05, learning_rate=0.04, irreducibility=ent["irreducibility"])
    assert ev.phi_after >= 0.40
    assert meta.status()["irreducibility"] == 0.5625


def test_06_strange_loop_and_theoretical_foundations_unified_bridge():
    sub = RecursiveSelfLearningSubstrate(dimension=32, seed=6)
    utf = UnifiedTheoreticalFoundations()
    for err in (0.7, 0.4, 0.2, 0.08, 0.02):
        snap = sub.evolve(err)
        utf.penrose.evaluate_superposition(
            delta_energy=1.0 - err, delta_time=0.8, phi_after=snap["phi"]
        )
    utf_snap = utf.snapshot()
    assert utf_snap["penrose_or"]["events_count"] >= 2
    assert utf_snap["du_sautoy_symmetry"]["reduction_factor"] == 16.0


def test_07_gateway_root_health_and_mode():
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json() == {"status": "EUCLID_ONLINE", "mode": "cognitive_architecture"}


def test_08_gateway_manifold_status_endpoint():
    reset_cognitive_registry()
    resp = client.get("/api/v1/euclid/manifold/status")
    assert resp.status_code == 200
    assert resp.json()["schema"] == "euclid.topological_manifold/1"


def test_09_gateway_websocket_grants_execution_for_healthy_node():
    reset_cognitive_registry()
    with client.websocket_connect("/api/v1/euclid/voice/stream") as ws:
        ws.send_json({"type": "EXECUTION_REQUEST", "target_node": "healthy_kernel"})
        msg = ws.receive_json()
        assert msg["stream_type"] == "EXECUTION_GRANTED"


def test_10_gateway_reconcile_endpoint_restores_equilibrium():
    reset_cognitive_registry()
    resp = client.post(
        "/api/v1/euclid/reconcile",
        json={
            "user_id": "operator_1",
            "target_node": "mining_scheduler",
            "remediation_constraint": "Bind Lucas L_15 stride check",
            "ricci_steps": 6,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["topological_equilibrium"] is True


def test_11_gateway_analogy_transfer_endpoint_returns_bijection():
    resp = client.post(
        "/api/v1/euclid/analogy/transfer",
        json={
            "source_node": "auth_module",
            "error_signature": "Session token leak",
            "target_domain": "quantum_decoherence",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["structural_isomorphism_verified"] is True
    assert "CoherentHilbertSubspaceRegister" in data["functor_object_mapping"].values()


def test_12_gateway_provocation_experiments_endpoint_passes_all_three():
    resp = client.get("/api/v1/euclid/experiments/run")
    assert resp.status_code == 200
    data = resp.json()
    assert data["all_hypotheses_confirmed"] is True


def test_13_control_api_prometheus_metrics_include_strange_loop_gauges():
    from chronus.mla1517_platform.python.control_api import _reason_metrics

    text = _reason_metrics([], {})
    assert "pythia_consciousness_phi" in text
    assert "pythia_cognitive_irreducibility" in text
    assert "pythia_strange_loop_depth" in text
    assert "pythia_penrose_or_events_total" in text


def test_14_metacognitive_lucas_bound_wiring():
    res = lucas_bound(10)
    assert res["module"] == "Intelligence.metacognitive_intelligence"
