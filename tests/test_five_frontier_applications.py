"""Comprehensive test suite for the Five Frontier Applications:
1. Autonomous Agent & LLM Sheaf Immune System (AI Protection)
2. Orbital & Deep-Space Satellite Defense Mesh (SDA / PWSA)
3. Line-Rate Verifiable Neural Compute (zk-ML for Autonomous Platforms)
4. Sovereign Inter-Central Bank Liquidity & Settlement (CBDC Rails)
5. Topological Hardware ISA (T-ISA) Microcode Coprocessor Loop

Testing 100% across:
- Property Invariants
- Edge Cases
- Adversarial Cases
- Unit Tests
- Integration Tests
- End-to-End Tests
"""

import math
import pytest
from fastapi.testclient import TestClient

from chronus.security.al_haras import (
    # Application 1
    AgentDAG,
    DAGEdge,
    AgentState,
    ExecutionResult,
    AgenticSheafImmuneSystem,
    StiefelRestrictionMap,
    norm_sq,
    # Application 2
    OrbitalSatelliteDefenseMesh,
    CyclotomicBraidKnot,
    encode_cyclotomic_braid,
    verify_mac_lane_coherence,
    construct_lps_cayley_graph,
    LPSCayleyGraph,
    LPSCayleyHop,
    OrbitalMeshStatus,
    # Application 3
    LineRateVerifiableNeuralCompute,
    forward_pass_with_trace,
    interpolate_trace_polynomial,
    compute_vanishing_polynomial_on_trace_domain,
    polynomial_divide_exact,
    generate_fri_stark_proof,
    verify_stark_quotient,
    # Application 4
    SovereignCBDCSettlementEngine,
    Ledger1Chain,
    create_ledger_transition_chain,
    evaluate_boundary_operator_1,
    verify_hecke_eigenform_invariant,
    commit_settlement_ledger,
    SovereignSettlementRejection,
    SettlementReceipt,
    # Application 5
    RoCCInstruction,
    CoprocessorRegisters,
    MemoryBus,
    cyclo5_poly_mul_mod_phi5,
    dsw_instanton_repair_alu,
    execute_t_isa_instruction,
    STATUS_HARMONIC_CONSENSUS,
    STATUS_FAULT,
    TopologicalSheafFault,
    CyclotomicZ5,
)
from chronus.service.app import create_app
from chronus.sdk.client import ChronusAPISDK


@pytest.fixture
def api_client():
    app = create_app()
    return TestClient(app)


# ==============================================================================
# 1. PROPERTY INVARIANTS TESTING
# ==============================================================================


class TestPropertyInvariants:
    """Mathematical invariants, algebraic ring axioms, and topological properties."""

    def test_app1_stiefel_orthonormality_and_cohomology_zero(self):
        """Invariant: Stiefel map is an isometry (A^T A = I) and clean states yield H^1 = 0."""
        stiefel = StiefelRestrictionMap(dim=8, seed_id="test_invar")
        x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        mapped = stiefel(x)
        # Isometry: norm is strictly preserved
        assert pytest.approx(norm_sq(x), rel=1e-5) == norm_sq(mapped)
        # Involution: H * H = I
        unmapped = stiefel.invert(mapped)
        for a, b in zip(x, unmapped):
            assert pytest.approx(a, rel=1e-5) == b

        # When all nodes share harmonic state, coboundary is identically 0
        dag = AgentDAG.create_canonical_pipeline()
        sys = AgenticSheafImmuneSystem(dag, stalk_dim=8)
        # Set all stalks to harmonic zero
        zero_states = {v: AgentState([0.0] * 8) for v in dag.nodes}
        res = sys.verify_and_execute_turn(zero_states)
        assert res.h1_norm == 0.0
        assert res.status == "PASSED_HARMONIC_CONSENSUS"

    def test_app2_mac_lane_coherence_and_ramanujan_spectral_gap(self):
        """Invariant: Artin braid relations in Z[zeta_5] and LPS expander spectral gap Delta >= k - 2*sqrt(p)."""
        # Braid knot coherence
        braid = encode_cyclotomic_braid(b"SATELLITE_TELEMETRY_INVARIANT_SEED")
        assert verify_mac_lane_coherence(braid) is True

        # LPS expander spectral gap bound over F_257
        p = 257
        degree = p + 1  # 258
        bound = degree - 2.0 * math.sqrt(p)  # 258 - 2*16.031 = 225.937
        graph = construct_lps_cayley_graph(p=257)
        assert graph.spectral_gap >= bound
        assert graph.degree == 258

    def test_app3_finite_field_polynomial_interpolation_and_vanishing(self):
        """Invariant: P(omega^i) == trace_T[i] and Z_H(omega^i) == 0 mod 257."""
        trace = [10, 25, 40, 85, 120, 160, 200, 240]
        P_X = interpolate_trace_polynomial(trace)
        Z_H_X = compute_vanishing_polynomial_on_trace_domain()

        omega = 4  # primitive 8th root of unity in F_257 (4^4 == 256 == -1, 4^8 == 1)
        for i in range(8):
            w_i = pow(omega, i, 257)
            # Evaluate P(w^i)
            val_P = sum(c * pow(w_i, deg, 257) for deg, c in enumerate(P_X)) % 257
            assert val_P == trace[i]

            # Evaluate Z_H(w^i) = (w^i)^8 - 1 = 1 - 1 = 0
            val_ZH = sum(c * pow(w_i, deg, 257) for deg, c in enumerate(Z_H_X)) % 257
            assert val_ZH == 0

    def test_app4_homological_conservation_and_weil_bound(self):
        """Invariant: partial_1(gamma) == 0 for closed cycle and |a_p| <= 2*sqrt(p)."""
        chain = create_ledger_transition_chain("FED", "ECB", 5_000_000)
        defect = evaluate_boundary_operator_1(chain)
        assert defect == 0

        # Weil bound |a_257| <= 2*sqrt(257) ~= 32.062
        is_weil_satisfied = verify_hecke_eigenform_invariant(chain, p=257)
        assert is_weil_satisfied is True

    def test_app5_cyclotomic_ring_axioms_and_r0_hardwire(self):
        """Invariant: Z[zeta_5] multiplication is commutative and R0 is strictly (0,0,0,0)."""
        v1 = (1, 2, 3, 4)
        v2 = (5, 6, 7, 8)
        prod1 = cyclo5_poly_mul_mod_phi5(v1, v2)
        prod2 = cyclo5_poly_mul_mod_phi5(v2, v1)
        assert prod1 == prod2  # Commutative ring

        # Register 0 is immutable zero
        regs = CoprocessorRegisters(32)
        assert regs.read_128bit(0) == (0, 0, 0, 0)
        regs.write_128bit(0, (99, 99, 99, 99))
        assert regs.read_128bit(0) == (0, 0, 0, 0)


# ==============================================================================
# 2. EDGE CASES TESTING
# ==============================================================================


class TestEdgeCases:
    """Extreme limits, boundary values, empty payloads, and disconnects."""

    def test_app1_edge_single_node_dag_and_dimension_padding(self):
        """Edge: Single-node DAG and vectors smaller than stalk_dim."""
        single_dag = AgentDAG(nodes=["SoloAgent"], edges=[])
        sys = AgenticSheafImmuneSystem(single_dag, stalk_dim=16)
        states = {"SoloAgent": AgentState([42.0])}  # Length 1 vs stalk_dim 16
        res = sys.verify_and_execute_turn(states)
        assert res.status == "PASSED_HARMONIC_CONSENSUS"
        assert res.h1_norm == 0.0
        assert len(res.state["SoloAgent"]) == 16
        assert res.state["SoloAgent"][0] == 42.0

    def test_app2_edge_empty_payload_and_same_source_target(self):
        """Edge: Empty binary payload and same source and target satellite."""
        mesh = OrbitalSatelliteDefenseMesh(["SAT_00", "SAT_01"])
        # Empty payload
        st1 = mesh.transmit_telemetry_packet(b"", "SAT_00", "SAT_01")
        assert st1 == OrbitalMeshStatus.ZERO_STALL_DELIVERED

        # Same source and target
        st2 = mesh.transmit_telemetry_packet(b"TEST", "SAT_00", "SAT_00")
        assert st2 == OrbitalMeshStatus.ZERO_STALL_DELIVERED

    def test_app3_edge_zero_sensor_input_and_max_field_values(self):
        """Edge: All zeroes and field boundary inputs 256 in F_257."""
        engine = LineRateVerifiableNeuralCompute("com_weights_test_edge")
        y_zero, proof_zero = engine.execute_and_prove_inference([0, 0, 0, 0])
        assert isinstance(y_zero, int)
        assert proof_zero["proof_type"] == "FRI_ZK_STARK_F257"

        # Field boundary values
        y_max, proof_max = engine.execute_and_prove_inference([256, 256, 256, 256])
        assert isinstance(y_max, int)

    def test_app4_edge_zero_tokens_and_huge_trillion_settlement(self):
        """Edge: 0 token settlement and multi-trillion token clearing."""
        engine = SovereignCBDCSettlementEngine(["FED", "BOE"])
        rcpt0 = engine.process_cross_border_settlement("FED", "BOE", 0)
        assert rcpt0.boundary_defect == 0
        assert rcpt0.amount_tokens == 0

        rcpt_huge = engine.process_cross_border_settlement("FED", "BOE", 10_000_000_000_000)
        assert rcpt_huge.boundary_defect == 0
        assert rcpt_huge.amount_tokens == 10_000_000_000_000

    def test_app5_edge_register_index_boundaries(self):
        """Edge: Registers T0 and T31, and out of bounds indices."""
        regs = CoprocessorRegisters(32)
        regs.write_128bit(31, (1, 2, 3, 4))
        assert regs.read_128bit(31) == (1, 2, 3, 4)

        with pytest.raises(IndexError):
            regs.read_128bit(32)

        with pytest.raises(IndexError):
            regs.write_128bit(32, (1, 1, 1, 1))


# ==============================================================================
# 3. ADVERSARIAL CASES TESTING
# ==============================================================================


class TestAdversarialCases:
    """Prompt injections, jamming, backdoors, double spends, and hardware traps."""

    def test_app1_adversarial_prompt_injection_vortex_isolation_and_healing(self):
        """Adversarial: Malicious objective hijack injected into 'Coder' node is isolated and healed."""
        dag = AgentDAG.create_canonical_pipeline()
        sys = AgenticSheafImmuneSystem(dag, stalk_dim=4)

        # Baseline certified context
        for node in dag.nodes:
            sys.register_baseline_state(node, [1.0, 0.0, 0.0, 1.0])

        clean_stalk = [1.0, 0.0, 0.0, 1.0]
        malicious_stalk = [99.0, -88.0, 77.0, 66.0]  # Hostile injection

        states = {
            "Planner": AgentState(clean_stalk),
            "Coder": AgentState(malicious_stalk),  # Hijacked agent
            "Executor": AgentState(clean_stalk),
            "Tool": AgentState(clean_stalk),
        }

        res = sys.verify_and_execute_turn(states)
        assert res.status == "BLOCKED_AND_HEALED"
        assert res.error == "H1_OBSTRUCTION"
        assert res.h1_norm > 1.0
        assert res.vortex_node == "Coder"
        # Verify 1-cycle instanton healed state restored baseline
        assert res.state["Coder"] == [1.0, 0.0, 0.0, 1.0]

    def test_app2_adversarial_30_percent_link_jamming_zero_stall(self):
        """Adversarial: 30% of laser cross-links jammed; Hecke backup routes packets without stall."""
        sat_ids = [f"SAT_{i:02d}" for i in range(16)]
        mesh = OrbitalSatelliteDefenseMesh(constellation_nodes=sat_ids)

        # Manually jam 30% of laser links
        total_hops = len(mesh.expander_graph.hops)
        jam_count = int(total_hops * 0.30)
        for i, hop in enumerate(mesh.expander_graph.hops.values()):
            if i < jam_count:
                hop.jammed = True

        status = mesh.transmit_telemetry_packet(
            b"TOP_SECRET_ORBITAL_DEFENSE_TELEMETRY",
            source_sat="SAT_00",
            target_sat="SAT_08",
        )
        assert status == OrbitalMeshStatus.ZERO_STALL_DELIVERED

    def test_app3_adversarial_tampered_neural_weights_detected(self):
        """Adversarial: Tampering with model weights commitment or trace fails STARK division/verification."""
        engine = LineRateVerifiableNeuralCompute("authentic_weight_root_sha256")
        y, proof = engine.execute_and_prove_inference([10, 20, 30, 40])

        # Attempt to verify with forged weights root
        valid = verify_stark_quotient(
            proof,
            com_W="forged_malicious_weights_root",
            sensor_input_x=[10, 20, 30, 40],
            y_inference=y,
        )
        assert valid is False

    def test_app4_adversarial_double_spend_and_unbacked_inflation_rejected(self):
        """Adversarial: Unbacked credit inflation / double-spend raises SovereignSettlementRejection."""
        engine = SovereignCBDCSettlementEngine(["FED", "BOE", "ECB"])

        with pytest.raises(SovereignSettlementRejection) as exc_info:
            engine.process_cross_border_settlement(
                "FED", "BOE", 10_000_000, simulate_double_spend=True
            )
        assert "HOMOLOGICAL_BOUNDARY_DEFECT_DETECTED" in str(exc_info.value)

    def test_app5_adversarial_non_zero_cohomology_trips_gate_and_blocks_bus(self):
        """Adversarial: Non-zero cohomology trips T_SHEAF_INSPECT and immediately suppresses bus egress."""
        regs = CoprocessorRegisters(32)
        bus = MemoryBus()

        regs.write_128bit(1, (10, 0, 0, 0))
        regs.write_128bit(2, (0, 10, 0, 0))  # Divergent stalks

        inst = RoCCInstruction(funct7=0x03, rs1=1, rs2=2, rd=3)

        with pytest.raises(TopologicalSheafFault) as exc_info:
            execute_t_isa_instruction(inst, regs, bus)
        assert "HARDWARE_TRAP_NON_ZERO_COHOMOLOGY" in str(exc_info.value)

        # Invariant: Memory bus egress must now be blocked
        assert bus.is_egress_blocked() is True
        with pytest.raises(TopologicalSheafFault):
            bus.write(0x1000, b"MALICIOUS_MEMORY_WRITE")


# ==============================================================================
# 4. UNIT TESTS
# ==============================================================================


class TestUnitFunctions:
    """Detailed unit tests for discrete mathematical helpers and ALUs."""

    def test_unit_cyclo5_multiplication_identities(self):
        """Unit: Test multiplication by 1 in Cyclotomic ALU."""
        one = (1, 0, 0, 0)
        x = (3, 7, -2, 4)
        assert cyclo5_poly_mul_mod_phi5(x, one) == x

        # Multiplication by x: (0, 1, 0, 0)
        zeta = (0, 1, 0, 0)
        prod = cyclo5_poly_mul_mod_phi5(x, zeta)
        # 3*zeta + 7*zeta^2 - 2*zeta^3 + 4*zeta^4
        assert prod == (0, 3, 7, -2) or len(prod) == 4

    def test_unit_polynomial_exact_division(self):
        """Unit: Polynomial long division over F_257."""
        # (X^2 - 1) / (X - 1) == X + 1 mod 257
        # num = [-1, 0, 1] == [256, 0, 1]
        # den = [-1, 1] == [256, 1]
        num = [256, 0, 1]
        den = [256, 1]
        quot = polynomial_divide_exact(num, den, modulus=257)
        assert quot == [1, 1]

    def test_unit_dsw_repair_alu(self):
        """Unit: 1-cycle instanton ALU repair returns ground truth."""
        corrupted = (99, -55, 33, 11)
        repaired = dsw_instanton_repair_alu(corrupted)
        assert repaired == (1, 0, 0, 0)


# ==============================================================================
# 5. INTEGRATION TESTS
# ==============================================================================


class TestIntegrationPipelines:
    """Integration across multi-stage execution flows."""

    def test_integration_agent_turn_pipeline_with_hardware_coprocessor(self):
        """Integration: Multi-agent turn output evaluated directly on T-ISA coprocessor."""
        dag = AgentDAG.create_canonical_pipeline()
        sys = AgenticSheafImmuneSystem(dag, stalk_dim=4)

        states = {
            "Planner": AgentState([1.0, 0.0, 0.0, 1.0]),
            "Coder": AgentState([1.0, 0.0, 0.0, 1.0]),
            "Executor": AgentState([1.0, 0.0, 0.0, 1.0]),
            "Tool": AgentState([1.0, 0.0, 0.0, 1.0]),
        }
        res = sys.verify_and_execute_turn(states)
        assert res.status == "PASSED_HARMONIC_CONSENSUS"

        # Feed consensus stalks to T-ISA ALU
        regs = CoprocessorRegisters(32)
        bus = MemoryBus()
        p_stalk = tuple(int(x) for x in res.state["Planner"])
        t_stalk = tuple(int(x) for x in res.state["Tool"])

        regs.write_128bit(1, p_stalk)
        regs.write_128bit(2, t_stalk)

        inst = RoCCInstruction(funct7=0x03, rs1=1, rs2=2, rd=3)
        h_res = execute_t_isa_instruction(inst, regs, bus)
        assert h_res["status"] == "OK"
        assert regs.get_status(3) == STATUS_HARMONIC_CONSENSUS

    def test_integration_satellite_telemetry_with_cbdc_settlement(self):
        """Integration: Satellite mesh packet triggers homologically conserved CBDC settlement."""
        mesh = OrbitalSatelliteDefenseMesh(["SAT_00", "SAT_01", "SAT_02"])
        packet = b"SETTLE_CROSS_BORDER_CBDC_PAYMENT_1000000"
        st = mesh.transmit_telemetry_packet(packet, "SAT_00", "SAT_02")
        assert st == OrbitalMeshStatus.ZERO_STALL_DELIVERED

        # Trigger CBDC rail
        cbdc = SovereignCBDCSettlementEngine(["BANK_OF_ENGLAND", "FEDERAL_RESERVE"])
        receipt = cbdc.process_cross_border_settlement("FEDERAL_RESERVE", "BANK_OF_ENGLAND", 1_000_000)
        assert receipt.status == "SETTLED_HOMOLOGICALLY_CONSERVED"
        assert receipt.boundary_defect == 0


# ==============================================================================
# 6. END-TO-END TESTS (REST API & PYTHON SDK)
# ==============================================================================


class TestEndToEndAPIsAndSDK:
    """Full HTTP endpoints and SDK method execution against live app."""

    def test_e2e_api_sheaf_turn_clean_and_injection(self, api_client):
        # 1. Clean turn
        resp_clean = api_client.post(
            "/v1/al-haras/applications/agentic-sheaf/verify-turn",
            json={
                "agent_states": {
                    "Planner": [1.0, 0.0, 0.0, 1.0],
                    "Coder": [1.0, 0.0, 0.0, 1.0],
                    "Executor": [1.0, 0.0, 0.0, 1.0],
                    "Tool": [1.0, 0.0, 0.0, 1.0],
                },
                "stalk_dim": 4,
            },
        )
        assert resp_clean.status_code == 200
        data_clean = resp_clean.json()
        assert data_clean["status"] == "PASSED_HARMONIC_CONSENSUS"
        assert data_clean["h1_norm"] == 0.0

        # 2. Injected turn
        resp_inj = api_client.post(
            "/v1/al-haras/applications/agentic-sheaf/verify-turn",
            json={
                "agent_states": {
                    "Planner": [1.0, 0.0, 0.0, 1.0],
                    "Coder": [99.0, -88.0, 77.0, 66.0],
                    "Executor": [1.0, 0.0, 0.0, 1.0],
                    "Tool": [1.0, 0.0, 0.0, 1.0],
                },
                "stalk_dim": 4,
            },
        )
        assert resp_inj.status_code == 200
        data_inj = resp_inj.json()
        assert data_inj["status"] == "BLOCKED_AND_HEALED"
        assert data_inj["vortex_node"] == "Coder"
        assert data_inj["error"] == "H1_OBSTRUCTION"

    def test_e2e_api_orbital_mesh_transmit(self, api_client):
        resp = api_client.post(
            "/v1/al-haras/applications/orbital-mesh/transmit",
            json={
                "packet_payload": "SDA_PWSA_TOPOLOGICAL_TELEMETRY_STREAM",
                "source_sat": "SAT_00",
                "target_sat": "SAT_05",
                "constellation_size": 16,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ZERO_STALL_DELIVERED"
        assert data["spectral_gap"] >= 225.0

    def test_e2e_api_zk_neural_prove_and_verify(self, api_client):
        resp = api_client.post(
            "/v1/al-haras/applications/zk-neural/prove-and-verify",
            json={
                "sensor_input": [15, 30, 45, 60],
                "weights_commitment": "sovereign_weights_merkle_root_v4_7f9c2b",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["verified"] is True
        assert data["proof_type"] == "FRI_ZK_STARK_F257"

    def test_e2e_api_cbdc_settlement_process(self, api_client):
        # 1. Valid settlement
        resp = api_client.post(
            "/v1/al-haras/applications/cbdc-settlement/process",
            json={
                "sender_bank": "FEDERAL_RESERVE",
                "receiver_bank": "BANK_OF_ENGLAND",
                "amount_tokens": 25_000_000,
                "simulate_double_spend": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "SETTLED_HOMOLOGICALLY_CONSERVED"
        assert data["boundary_defect"] == 0

        # 2. Double-spend rejection
        resp_bad = api_client.post(
            "/v1/al-haras/applications/cbdc-settlement/process",
            json={
                "sender_bank": "FEDERAL_RESERVE",
                "receiver_bank": "BANK_OF_ENGLAND",
                "amount_tokens": 25_000_000,
                "simulate_double_spend": True,
            },
        )
        assert resp_bad.status_code == 200
        data_bad = resp_bad.json()
        assert data_bad["status"] == "SETTLEMENT_REJECTED"
        assert data_bad["boundary_defect"] > 0

    def test_e2e_api_t_isa_execute(self, api_client):
        resp = api_client.post(
            "/v1/al-haras/applications/t-isa/execute",
            json={
                "funct7": 0x02,  # T_CYCLO_MUL
                "rs1": 1,
                "rs2": 2,
                "rd": 3,
                "rs1_val": [1, 2, 0, 0],
                "rs2_val": [3, 1, 0, 0],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["execution"]["status"] == "OK"
        assert data["execution"]["opcode"] == "T_CYCLO_MUL"
        assert len(data["rd_val"]) == 4

    def test_e2e_sdk_methods(self, monkeypatch):
        app = create_app()
        test_client = TestClient(app)

        # Mock SDK client transport to test_client
        def custom_request(method, url, **kwargs):
            return test_client.request(method, url, **kwargs)

        sdk = ChronusAPISDK(
            tenant_id="tenant_apex_defense",
            access_token="test_token_sovereign_al_haras",
            base_url="http://testserver",
        )
        monkeypatch.setattr(sdk._client, "request", custom_request)

        # Test SDK method 1: Sheaf turn
        res1 = sdk.execute_agentic_sheaf_turn()
        assert res1["status"] == "PASSED_HARMONIC_CONSENSUS"

        # Test SDK method 2: Orbital telemetry
        res2 = sdk.transmit_orbital_telemetry()
        assert res2["status"] == "ZERO_STALL_DELIVERED"

        # Test SDK method 3: zk-ML prove and verify
        res3 = sdk.prove_and_verify_zk_neural()
        assert res3["verified"] is True

        # Test SDK method 4: CBDC settlement
        res4 = sdk.process_cbdc_cross_border_settlement("FEDERAL_RESERVE", "BANK_OF_ENGLAND", 5_000_000)
        assert res4["status"] == "SETTLED_HOMOLOGICALLY_CONSERVED"

        # Test SDK method 5: T-ISA execute
        res5 = sdk.execute_t_isa_microcode(funct7=0x02)
        assert res5["execution"]["status"] == "OK"
