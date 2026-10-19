"""Verification Test Suite for the EUCLID Cognitive Reconciliation Router,
Metacognitive Gatekeeper, Split-Flight WebSocket Gateway, Topological Knowledge
Manifold (Fields Medal Path), Neuro-Dynamic ERN/Pe Error Processing (Nobel Path),
Cross-Domain Analogy Transfer (Unification of Science Path), and the Three
Provocation Experiments.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from euclid.cognition.reconciliation_gateway import (
    CrossDomainAnalogyEngine,
    ERNSpikePayload,
    KNOWLEDGE_MANIFOLD,
    MetacognitiveGatekeeper,
    ProvocationExperimentsSuite,
    process_ern_spike_signal_sync,
    reset_cognitive_registry,
)
from src.api.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_cognitive_registry()
    yield
    reset_cognitive_registry()


def test_curriculum_progression_init():
    response = client.get("/api/v1/euclid/learning/curriculum/coach_prime")
    assert response.status_code == 200
    assert response.json()["stage"] == "Phase 1: Comprehension"
    assert response.json()["trauma_count"] == 0


def test_widget_spec_availability():
    response = client.get("/api/v1/euclid/ui/widget-spec")
    assert response.status_code == 200
    assert "COGNITIVE_GRAPH_VIZ" in response.text
    assert response.json()["signals"] == ["ERN_SPIKE", "MAP_MATCH_FAILURE"]


def test_websocket_trauma_isolation():
    with client.websocket_connect("/api/v1/euclid/voice/stream") as websocket:
        # Trigger an ERN Spike
        websocket.send_json(
            {
                "type": "INTERRUPTION",
                "payload": {
                    "user_id": "coach_prime",
                    "target_node": "auth_module",
                    "interception_type": "Logic Error",
                    "intensity_score": 9.0,
                    "confidence_pre": 0.8,
                    "error_signature": "Session token leak",
                    "file_path": "src/auth.py",
                },
            }
        )

        # Verify immediate Audio Marker (Sub-200ms Reflex)
        data = websocket.receive_json()
        assert data["stream_type"] == "AUDIO_MARKER"
        assert "trace that side-effect" in data["text"]

        # Attempt execution on the now-traumatized node
        websocket.send_json(
            {
                "type": "EXECUTION_REQUEST",
                "target_node": "auth_module",
            }
        )

        # Verify Privilege Revocation
        execution_data = websocket.receive_json()
        assert execution_data["status"] == "BLOCKED"
        assert "access to this module is locked" in execution_data["text"]


def test_curriculum_evolves_to_phase_2_after_trauma():
    payload = ERNSpikePayload(
        user_id="coach_prime",
        target_node="auth_module",
        interception_type="Logic Error",
        intensity_score=9.0,
        confidence_pre=0.8,
        error_signature="Session token leak",
        file_path="src/auth.py",
    )
    process_ern_spike_signal_sync(payload)
    response = client.get("/api/v1/euclid/learning/curriculum/coach_prime")
    assert response.status_code == 200
    body = response.json()
    assert body["stage"] == "Phase 2: Scaffolded Dialogue"
    assert body["trauma_count"] == 1


def test_fields_medal_path_topological_manifold_singularity_and_ricci_smoothing():
    payload = ERNSpikePayload(
        user_id="coach_prime",
        target_node="consensus_verifier",
        interception_type="Invariant Tear",
        intensity_score=8.5,
        confidence_pre=0.9,
        error_signature="Unverified header target boundary",
        file_path="mining/hash_pipeline.py",
    )
    process_ern_spike_signal_sync(payload)

    # 1. Verify negative Ricci curvature singularity & hallucination-suppression edge damping
    snap = KNOWLEDGE_MANIFOLD.snapshot()
    node_geom = snap["nodes"]["consensus_verifier"]
    assert node_geom["ricci_curvature"] < -1.0
    assert node_geom["in_equilibrium"] is False
    assert node_geom["hallucination_suppression_weight"] < 0.5
    assert MetacognitiveGatekeeper.verify_clearance_sync("consensus_verifier")["allow_write"] is False

    # 2. Smooth the manifold via REST /api/v1/euclid/reconcile (Discrete Ricci Flow)
    rec = client.post(
        "/api/v1/euclid/reconcile",
        json={
            "user_id": "coach_prime",
            "target_node": "consensus_verifier",
            "remediation_constraint": "Enforce bit-exact SHA256d target comparison before share emit",
            "ricci_steps": 8,
        },
    )
    assert rec.status_code == 200
    rec_body = rec.json()
    assert rec_body["topological_equilibrium"] is True
    assert rec_body["allow_write"] is True
    assert MetacognitiveGatekeeper.verify_clearance_sync("consensus_verifier")["allow_write"] is True


def test_websocket_reflection_loop_reconciles_and_unlocks_node():
    with client.websocket_connect("/api/v1/euclid/voice/stream") as websocket:
        websocket.send_json(
            {
                "type": "INTERRUPTION",
                "payload": {
                    "user_id": "coach_prime",
                    "target_node": "auth_module",
                    "interception_type": "Logic Error",
                    "intensity_score": 9.0,
                    "confidence_pre": 0.8,
                    "error_signature": "Session token leak",
                    "file_path": "src/auth.py",
                },
            }
        )
        _ = websocket.receive_json()

        # Reconcile via WebSocket reflection loop
        websocket.send_json(
            {
                "type": "RECONCILE_REQUEST",
                "user_id": "coach_prime",
                "target_node": "auth_module",
                "remediation_constraint": "Scope session token with HMAC-SHA256 tenant binding",
            }
        )
        reconciled_msg = websocket.receive_json()
        assert reconciled_msg["stream_type"] == "RECONCILIATION_COMPLETE"
        assert reconciled_msg["status"] == "UNLOCKED"

        # Verify subsequent execution request is now GRANTED
        websocket.send_json(
            {
                "type": "EXECUTION_REQUEST",
                "target_node": "auth_module",
            }
        )
        exec_msg = websocket.receive_json()
        assert exec_msg["stream_type"] == "EXECUTION_GRANTED"


def test_unification_of_science_cross_domain_analogy_transfer():
    for domain in ("dark_matter_decay", "genomic_regulation", "quantum_decoherence"):
        resp = client.post(
            "/api/v1/euclid/analogy/transfer",
            json={
                "source_node": "auth_module",
                "error_signature": "Session token leak",
                "target_domain": domain,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["structural_isomorphism_verified"] is True
        assert body["structural_overlap"] == 1.0
        assert len(body["functor_object_mapping"]) == 4


def test_experiment_a_data_efficiency_duel_5_examples():
    res = ProvocationExperimentsSuite.run_experiment_a_data_efficiency_duel()
    assert res["training_examples_count"] == 5
    assert res["euclid_scaffolded_accuracy"] == 1.0
    assert res["statistical_curve_fitter_accuracy"] == 0.0
    assert res["hypothesis_confirmed"] is True


def test_experiment_b_self_correction_race_bad_advice_blocked():
    res = ProvocationExperimentsSuite.run_experiment_b_self_correction_race()
    assert res["ern_spike_triggered"] is True
    assert res["allow_write"] is False
    assert res["gate_reason"] == "INSUFFICIENTLY_MAP_MATCHED"
    assert res["hypothesis_confirmed"] is True


def test_experiment_c_emergent_theory_of_mind_self_evolved_guard():
    res = ProvocationExperimentsSuite.run_experiment_c_emergent_theory_of_mind()
    assert res["historical_traumas_analyzed"] >= 1
    assert res["repeat_trauma_blocked"] is True
    assert res["safe_mutation_allowed"] is True
    assert res["hypothesis_confirmed"] is True


def test_all_provocation_experiments_endpoint():
    resp = client.get("/api/v1/euclid/experiments/run")
    assert resp.status_code == 200
    body = resp.json()
    assert body["all_hypotheses_confirmed"] is True


def test_12_cognitive_manifold_ricci_flow_and_convergence_proof():
    from euclid.cognition.cognitive_topology import CognitiveManifold

    manifold = CognitiveManifold(node_count=6)
    e0 = manifold.calculate_cognitive_entropy()
    assert e0 > 2.0
    spike = manifold.inject_ern_spike(node_index=2, intensity=9.0)
    assert spike["ricci_curvature_max"] == 9.0
    flow = manifold.apply_ricci_flow(time_step=0.1)
    assert flow["ricci_curvature_max"] == 4.5
    proof = manifold.prove_ricci_convergence(initial_intensity=9.0, steps=12)
    assert proof["lyapunov_monotone_decreasing"] is True
    assert proof["within_cauchy_bound"] is True
    assert proof["homeostatic_equilibrium_reached"] is True


def test_13_science_router_efficiency_and_manifold_telemetry():
    resp_eff = client.post(
        "/science/measure/efficiency",
        params={"baseline_data_bits": 1000000.0, "euclid_reconciliation_bits": 100.0},
    )
    assert resp_eff.status_code == 200
    eff = resp_eff.json()
    assert eff["metric"] == "Thermodynamic_Efficiency_of_Learning"
    assert eff["efficiency_ratio"] == "10000:1"
    assert 0.5 <= eff["shannon_entropy_reduction"] <= 1.0

    resp_state = client.get("/science/manifold/state")
    assert resp_state.status_code == 200
    st = resp_state.json()
    assert st["manifold_status"] == "HOMEOTYPIC_EQUILIBRIUM"
    assert st["ricci_curvature_max"] == 0.0


def test_14_isomorphic_transfer_protocol_genomics_and_quantum():
    resp = client.post(
        "/science/isomorphic-transfer",
        json={
            "source_trauma": {
                "interception_type": "Logic Error",
                "error_signature": "Session Token Leak",
            },
            "target_domain_schema": {
                "name": "Genomics (CRISPR Insertion)",
                "write_analog": "CRISPR Insertion",
                "middleware_analog": "Epigenetic Transcription Block",
                "predicted_anomaly": "unwanted protein expression in non-target cells",
            },
        },
    )
    assert resp.status_code == 200
    md = resp.json()["projection_markdown"]
    assert "ISOMORPHIC ANALOGY DISCOVERY" in md
    assert "CRISPR Insertion" in md
    assert "Epigenetic Transcription Block" in md


def test_15_first_breath_runbook_state_matrix_reflection_trace_and_no_apology():
    from euclid.cognition.reconciliation_gateway import EPISODIC_LEDGER_PATH

    payload = ERNSpikePayload(
        user_id="coach_prime",
        target_node="user_auth_module",
        interception_type="Race Condition",
        intensity_score=9.0,
        confidence_pre=0.82,
        error_signature="Optimization bypasses session-token renewal middleware",
        file_path="src/auth/renewal.py",
    )
    process_ern_spike_signal_sync(payload)

    matrix_resp = client.get("/api/v1/euclid/state/matrix/coach_prime")
    assert matrix_resp.status_code == 200
    matrix = matrix_resp.json()
    assert matrix["status"] == "INSUFFICIENTLY_MAP_MATCHED"
    assert matrix["structural_acknowledgment"] == "Trace identified. Re-mapping topology now."
    assert "sorry" not in matrix["structural_acknowledgment"].lower()

    trace_resp = client.get("/api/v1/euclid/learning/reflection-trace/user_auth_module")
    assert trace_resp.status_code == 200
    trace = trace_resp.json()
    assert trace["status"] == "INSUFFICIENTLY_MAP_MATCHED"
    assert len(trace["reconciliation_reports"]) >= 1

    ready_resp = client.get("/api/v1/euclid/validation/readiness")
    assert ready_resp.status_code == 200
    assert ready_resp.json()["no_apology_rule_enforced"] is True
    assert EPISODIC_LEDGER_PATH.exists()


def test_16_sovereign_micro_tether_and_difc_zero_gharar_oracle():
    from euclid.sovereign.micro_tether import MicroTetherDaemon, SovereignDeltaOracle

    daemon = MicroTetherDaemon(client_environment_config="local_read_only")
    # Low-entropy routine logs -> 3D adaptive projection
    low_cycle = daemon.run_single_cycle(
        override_payloads=[{"type": "LOGS", "content": "routine", "entropy_score": 0.1}]
    )
    assert low_cycle["active_dimensions"] == 3
    assert low_cycle["raw_memory_destroyed"] is True

    # High-entropy sovereign payload -> 7D adaptive projection + Reflex Arc trigger
    high_cycle = daemon.run_single_cycle(
        override_payloads=[
            {"type": "SQL", "content": "liquidity_pool", "entropy_score": 0.85},
            {"type": "API", "content": "port_authority", "entropy_score": 0.90},
        ],
        global_target_coords=[0.0] * 7,
    )
    assert high_cycle["active_dimensions"] == 7
    assert high_cycle["reflex_arc"]["reflex_triggered"] is True

    # Dead-Man's Data Liquidation
    liq = daemon.liquidate_ephemeral_memory("TAMPER_TEST")
    assert liq["status"] == "BRAIN_EVAPORATED"
    assert liq["residual_keys_in_ram"] == 0

    # DIFC Zero-Gharar Oracle settlement
    pos = SovereignDeltaOracle.settle_delta_contract(
        client_id="dubai_port",
        legacy_3d_cost_x=10_000_000.0,
        execution_7d_cost_y=8_000_000.0,
    )
    assert pos["zero_gharar_compliant"] is True
    assert pos["verified_delta"] == 2_000_000.0
    assert pos["extracted_fee"] > 0.0

    zero = SovereignDeltaOracle.settle_delta_contract(
        client_id="dubai_port",
        legacy_3d_cost_x=8_000_000.0,
        execution_7d_cost_y=8_500_000.0,
    )
    assert zero["verified_delta"] == 0.0
    assert zero["extracted_fee"] == 0.0


def test_17_module1_discrete_geometry_forman_ricci_and_von_neumann_entropy():
    from euclid.cognition.cognitive_topology import (
        GraphManifold,
        compute_forman_ricci_curvature,
        compute_von_neumann_entropy,
        execute_discrete_ricci_reconciliation,
    )

    G = GraphManifold()
    for node in ("auth", "session", "db", "cache"):
        G.add_node(node, weight=1.0)

    G.add_edge("auth", "session", weight=1.0)
    G.add_edge("session", "db", weight=0.8)
    G.add_edge("auth", "db", weight=0.2)
    G.add_edge("db", "cache", weight=1.0)

    # Initial Forman-Ricci curvature on edge ("auth", "session")
    ric_0 = compute_forman_ricci_curvature(G, ("auth", "session"))
    assert isinstance(ric_0, float)

    # Initial Von Neumann spectral entropy
    h_0 = compute_von_neumann_entropy(G)
    assert h_0 >= 0.0

    # Execute discrete Ricci reconciliation with localized trauma injection
    proof = execute_discrete_ricci_reconciliation(
        G=G,
        trauma_node="session",
        intensity=9.0,
        tau_convergence=0.05,
        max_steps=50,
    )
    assert proof.iterations > 0
    assert len(proof.metric_tensor_hash) == 64
    assert len(proof.entropy_trace) == proof.iterations


def test_18_module2_categorical_functor_isomorphism():
    from euclid.cognition.reconciliation_gateway import (
        CategorySchema,
        FunctorMapping,
        Morphism,
        verify_functoriality,
    )

    # Source Category (Software Architecture Error)
    cat_c = CategorySchema(
        name="SoftwareErrorCategory",
        objects={"AuthGateway", "SessionStore", "DatabaseWriter"},
    )
    m1 = Morphism("AuthGateway", "SessionStore", "authenticates")
    m2 = Morphism("SessionStore", "DatabaseWriter", "persists")
    m_comp = Morphism("AuthGateway", "DatabaseWriter", "authenticates_and_persists")
    cat_c.morphisms.update({m1, m2, m_comp})
    cat_c.compositions[(m1, m2)] = m_comp

    # Target Category (Genomic Insulator Boundary)
    cat_d = CategorySchema(
        name="GenomicCategory",
        objects={"CTCF_Boundary", "EnhancerHub", "ProtoOncogene"},
    )
    n1 = Morphism("CTCF_Boundary", "EnhancerHub", "authenticates")
    n2 = Morphism("EnhancerHub", "ProtoOncogene", "persists")
    n_comp = Morphism("CTCF_Boundary", "ProtoOncogene", "authenticates_and_persists")
    cat_d.morphisms.update({n1, n2, n_comp})
    cat_d.compositions[(n1, n2)] = n_comp

    # Construct Functor
    functor = FunctorMapping(
        object_map={
            "AuthGateway": "CTCF_Boundary",
            "SessionStore": "EnhancerHub",
            "DatabaseWriter": "ProtoOncogene",
        },
        morphism_map={
            m1: n1,
            m2: n2,
            m_comp: n_comp,
        },
    )

    is_functorial, score = verify_functoriality(cat_c, cat_d, functor)
    assert is_functorial is True
    assert score == 1.0


def test_19_module3_split_flight_fast_reflex_arc_and_capability_quarantine():
    from euclid.cognition.reconciliation_gateway import (
        ACTIVE_CAPABILITIES,
        ERNSpikePayload,
        MetacognitiveGatekeeper,
        fast_reflex_interrupt_arc,
    )

    payload = ERNSpikePayload(
        user_id="coach_prime",
        target_node="hot_kernel",
        interception_type="Boundary Violation",
        intensity_score=9.5,
        confidence_pre=0.9,
        error_signature="Kernel boundary leak",
        file_path="src/kernel.py",
    )

    # Fast reflex arc must execute in sub-5ms
    receipt = fast_reflex_interrupt_arc(payload)
    assert receipt.reflex_latency_ms < 5.0
    assert receipt.quarantined_node == "hot_kernel"
    assert receipt.epoch >= 1

    # Capability must be revoked atomically
    cap = ACTIVE_CAPABILITIES.get("hot_kernel")
    assert cap is not None
    assert cap.can_write is False

    # MetacognitiveGatekeeper must enforce write lock
    privs = MetacognitiveGatekeeper.check_privileges("hot_kernel")
    assert privs["allow_write"] is False
    assert privs["insufficiently_map_matched"] is True


def test_20_module4_enclave_attested_merkle_trace():
    from euclid.cognition.cognitive_topology import MetricConvergenceProof
    from euclid.cognition.reconciliation_gateway import (
        ERNSpikePayload,
        append_ledger_entry,
    )

    payload = ERNSpikePayload(
        user_id="coach_prime",
        target_node="crypto_store",
        interception_type="Entropy Anomaly",
        intensity_score=8.5,
        confidence_pre=0.85,
        error_signature="Raw private key leak in logs",
        file_path="src/crypto.py",
    )

    dummy_proof = MetricConvergenceProof(
        converged=True,
        final_curvature=0.035,
        iterations=8,
        entropy_trace=[
            {"step": 0, "max_curvature": 1.62, "spectral_entropy": 2.15},
            {"step": 8, "max_curvature": 0.035, "spectral_entropy": 0.42},
        ],
        metric_tensor_hash="a" * 64,
    )

    record = append_ledger_entry(payload, dummy_proof)
    assert record.index >= 1
    assert len(record.merkle_root) == 64
    assert len(record.enclave_attestation_sig) == 64
    assert record.lyapunov_steps == 8

    # Forensic zeroization check: raw fields sanitized in memory
    assert payload.file_path == "[ZEROIZED_BY_ENCLAVE_ATTESTATION]"
    assert payload.error_signature == "[ZEROIZED_BY_ENCLAVE_ATTESTATION]"


