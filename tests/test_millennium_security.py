"""
================================================================================
  TEST SUITE: AL HARAS CLASSES WITH LEGACY "MILLENNIUM" NAMES
================================================================================
  What is verified (exact arithmetic throughout):
    1. Ollivier-Ricci curvature and threshold edge removal (RicciCurvatureDeCloaker)
    2. Exact Hodge decomposition of a trace on a cycle graph (HodgeCovertChannelFilter)
    3. Exact p-adic distances and ball disjointness (UltrametricMemorySandbox)
    4. In-place buffer zeroisation; reversible cat-map permutation (AnosovColdBootScrambler)
    5. Picard-Lefschetz anti-jamming: reported as not implemented
    6. T-ISA opcodes and coprocessor behaviour (hardware_t_isa)
    7. Legacy "unification" entry points: NOT_IMPLEMENTED plus exact self-checks
  Endpoint tests need fastapi and are skipped where it is not installed.
  Pure-computation tests with independent known answers are in
  tests/test_al_haras_millennium_exact.py.
================================================================================
"""

from fractions import Fraction

import pytest

from chronus.security.al_haras import (
    RicciCurvatureDeCloaker,
    HodgeCovertChannelFilter,
    UltrametricMemorySandbox,
    AnosovColdBootScrambler,
    PicardLefschetzAntiJammingFilter,
    SpectralDualityBridge,
    HarmonicCohomologyBridge,
    ParabolicFlowSingularityBridge,
    GrandMillenniumUnificationNexus,
    TISAOpcode,
    TISAInstruction,
    RISCVTopologicalCoprocessor,
    RoCCInstruction,
    CoprocessorRegisters,
    MemoryBus,
    execute_t_isa_instruction,
    RicciCurvatureNeckFault,
    encode_t_isa_instruction,
    decode_t_isa_instruction,
)


TOKEN = "al-haras-millennium-test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
MILLENNIUM = "/v1/al-haras/millennium"


@pytest.fixture
def client():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from chronus.service.app import create_app
    from chronus.service.dependencies import auth_service

    auth_service.register_tenant("al-haras-millennium-test", TOKEN)
    return TestClient(create_app())


class TestRicciCurvatureDeCloaker:
    """Exact Ollivier-Ricci curvature and threshold edge removal."""

    def test_ricci_curvature_benign_cluster(self):
        """A triangle with equal weights has curvature exactly 1/2 on every edge (alpha = 0)."""
        decloaker = RicciCurvatureDeCloaker(curvature_threshold=-0.4)
        decloaker.add_edge("NodeA", "NodeB", traffic_weight=1.0)
        decloaker.add_edge("NodeB", "NodeC", traffic_weight=1.0)
        decloaker.add_edge("NodeC", "NodeA", traffic_weight=1.0)

        curvatures = decloaker.compute_ollivier_ricci_curvatures()
        assert curvatures == {"NodeA->NodeB": Fraction(1, 2), "NodeB->NodeC": Fraction(1, 2), "NodeC->NodeA": Fraction(1, 2)}

    def test_perelman_surgery_removes_bridge_between_clusters(self):
        """The bridge between two triangles has curvature -2/3 and is the only edge removed."""
        decloaker = RicciCurvatureDeCloaker(curvature_threshold=-0.4)
        for source, target in (
            ("HQ_1", "HQ_2"), ("HQ_2", "HQ_3"), ("HQ_3", "HQ_1"),
            ("EXT_1", "EXT_2"), ("EXT_2", "EXT_3"), ("EXT_3", "EXT_1"),
        ):
            decloaker.add_edge(source, target, traffic_weight=2.0)
        decloaker.add_edge("HQ_1", "EXT_1", traffic_weight=2.0)

        res = decloaker.execute_perelman_surgery()
        assert res["status"] == "EDGES_REMOVED"
        assert res["transport_optimality_certified"] is True
        assert res["removed_edge_count"] == 1
        bridge = res["removed_edges"][0]
        assert (bridge["source"], bridge["target"]) == ("HQ_1", "EXT_1")
        assert Fraction(bridge["ollivier_ricci_curvature"]) == Fraction(-2, 3)
        assert (res["connected_components_before"], res["connected_components_after"]) == (1, 2)
        assert "surgery_status" not in res and "excised_c2_bridges" not in res

    def test_high_traffic_leaf_edge_is_flat(self):
        """A leaf edge has curvature 0 whatever its traffic; traffic alone does not make an edge negative."""
        decloaker = RicciCurvatureDeCloaker(curvature_threshold=-0.4)
        decloaker.add_edge("HQ_1", "HQ_2", traffic_weight=2.0)
        decloaker.add_edge("HQ_2", "HQ_3", traffic_weight=2.0)
        decloaker.add_edge("HQ_3", "HQ_1", traffic_weight=2.0)
        decloaker.add_edge("HQ_1", "Leaf_Node", traffic_weight=100.0)

        res = decloaker.execute_perelman_surgery()
        assert res["curvatures"]["HQ_1->Leaf_Node"] == "0"
        assert all(edge["target"] != "Leaf_Node" for edge in res["removed_edges"])


class TestHodgeCovertChannelFilter:
    """Exact Hodge decomposition of a trace on the cycle graph C_n."""

    def test_hodge_decomposition_three_components(self):
        """exact + co_exact + harmonic reconstructs the trace; co_exact is zero on C_n."""
        trace = [1.0, 5.0, 2.0, 8.0, 3.0, 7.0, 2.0, 6.0]
        exact, co_exact, harmonic = HodgeCovertChannelFilter.decompose_signal(trace)
        assert len(exact) == len(co_exact) == len(harmonic) == len(trace)
        assert harmonic == [Fraction(17, 4)] * 8
        assert co_exact == [Fraction(0)] * 8
        assert [e + h for e, h in zip(exact, harmonic)] == [Fraction(x) for x in (1, 5, 2, 8, 3, 7, 2, 6)]

    def test_side_channel_projection_is_exact_and_keeps_the_variation(self):
        """The projection is the trace minus its mean: the modulation is kept, nothing is nullified."""
        noisy_bus = [10.0, 25.0, 11.0, 28.0, 10.5, 26.0, 11.2, 27.5]
        res = HodgeCovertChannelFilter.sanitize_side_channels(noisy_bus)
        assert res["status"] == "DECOMPOSITION_VERIFIED"
        assert all(res["identities_verified"].values())
        mean = sum(Fraction(str(x)) for x in noisy_bus) / len(noisy_bus)
        assert Fraction(res["mean"]) == mean
        assert [Fraction(x) for x in res["projection"]] == [Fraction(str(x)) - mean for x in noisy_bus]
        assert Fraction(res["projection_norm_sq"]) > 0
        assert "side_channel_nullified" not in res and "covert_leakage_power_after" not in res


class TestUltrametricMemorySandbox:
    """Exact p-adic distances and disjointness of p-adic balls of integer addresses."""

    def test_p_adic_distance_properties(self):
        """d_p(x, y) = |x - y|_p exactly."""
        sandbox = UltrametricMemorySandbox(prime_p=257)
        assert sandbox.p_adic_distance(1000, 1000) == 0
        assert sandbox.p_adic_distance(0, 257) == Fraction(1, 257)
        assert sandbox.p_adic_distance(0, 1) == 1

    def test_ultrametric_strong_triangle_inequality(self):
        """|x + y|_p <= max(|x|_p, |y|_p)."""
        sandbox = UltrametricMemorySandbox(prime_p=257)
        x = 257 * 3
        y = 257 * 7
        dist_x = sandbox.p_adic_distance(0, x)
        dist_y = sandbox.p_adic_distance(0, y)
        dist_sum = sandbox.p_adic_distance(0, x + y)
        assert dist_sum <= max(dist_x, dist_y)

    def test_enclave_address_sets_are_disjoint_when_centres_differ_mod_p(self):
        """0x1000 and 0x5000 differ mod 257, so their residue classes are disjoint."""
        sandbox = UltrametricMemorySandbox(prime_p=257)
        sandbox.register_enclave("process_kernel", 0x1000)
        sandbox.register_enclave("process_userland", 0x5000)

        res = sandbox.verify_non_overlapping_isolation("process_kernel", "process_userland")
        assert res["balls_disjoint"] is True
        assert res["status"] == "ADDRESS_SETS_DISJOINT"
        assert res["ball_a"]["address_set"] == f"{0x1000 % 257} mod 257^1"
        assert "isolation_guarantee" not in res and "speculative_cross_bleed_possible" not in res

    def test_congruent_enclaves_intersect(self):
        """Centres congruent mod 257 give the same ball; the check reports the intersection."""
        sandbox = UltrametricMemorySandbox(prime_p=257)
        sandbox.register_enclave("one", 7)
        sandbox.register_enclave("two", 7 + 257)
        res = sandbox.verify_non_overlapping_isolation("one", "two")
        assert res["balls_disjoint"] is False
        assert res["status"] == "ADDRESS_SETS_INTERSECT"


class TestAnosovColdBootScrambler:
    """Zeroisation of mutable buffers; the cat map is a reversible permutation."""

    def test_arnold_cat_map_step_is_reversible(self):
        """One cat-map step over F_257 and its exact inverse."""
        x, y = 42, 99
        x_next, y_next = AnosovColdBootScrambler.iterate_arnold_map(x, y, iterations=1)
        assert (x_next, y_next) == ((2 * x + y) % 257, (x + y) % 257)
        assert AnosovColdBootScrambler.inverse_arnold_map(x_next, y_next, iterations=1) == (x, y)

    def test_emergency_ram_purge_zeroises_a_mutable_buffer(self):
        """A bytearray is overwritten with zeros in place and read back."""
        secret_key = bytearray(b"TEST_ROOT_KEY_MATERIAL_FOR_UNIT_TESTS_ONLY_0123456789abcdef!!")
        res = AnosovColdBootScrambler.emergency_ram_purge(secret_key)
        assert res["status"] == "ZEROISED_AND_VERIFIED"
        assert secret_key == bytearray(len(secret_key))
        assert res["cat_map_scramble"]["applied"] is False
        assert res["cat_map_scramble"]["period_mod_256"] == 192

    def test_emergency_ram_purge_cannot_zeroise_immutable_bytes(self):
        """A bytes object cannot be overwritten and is reported as not zeroised."""
        res = AnosovColdBootScrambler.emergency_ram_purge(b"immutable key material")
        assert res["status"] == "NOT_ZEROISED_IMMUTABLE_INPUT"
        assert res["zeroised_in_place"] is False
        assert "cold_boot_recovery_possible" not in res and "purge_latency_us" not in res


class TestPicardLefschetzAntiJammingFilter:
    """The anti-jamming filter is not implemented and says so."""

    def test_jammed_waveform_filter_reports_not_implemented(self):
        """No samples are returned and no signal-quality figure is claimed."""
        iq_samples = [(1.0, 1.0), (1.1, 0.9), (0.95, 1.05), (1.02, 0.98)]
        res = PicardLefschetzAntiJammingFilter.filter_jammed_waveform(
            signal_iq_samples=iq_samples,
            jamming_phase_intensity=3.0,
        )
        assert res["status"] == "NOT_IMPLEMENTED"
        assert res["input_samples"] == 4
        assert "snr_improvement_db" not in res and "anti_jamming_recovery_status" not in res


class TestTISANewOpcodes:
    """T_RICCI_INSPECT (sign test of c0), T_HODGE_PROJ (projection onto (c0, c1)) and
    T_ANOSOV_PURGE (invertible cat map mod 257) in the T-ISA software model."""

    def test_t_isa_instruction_encode_decode(self):
        """Tests 32-bit word encoding and decoding for the 3 new T-ISA opcodes."""
        inst_ricci = TISAInstruction(TISAOpcode.T_RICCI_INSPECT, rd=3, rs1=1, rs2=2)
        word_ricci = encode_t_isa_instruction(inst_ricci)
        dec_ricci = decode_t_isa_instruction(word_ricci)
        assert dec_ricci.opcode == TISAOpcode.T_RICCI_INSPECT
        assert dec_ricci.rd == 3
        assert dec_ricci.rs1 == 1

        inst_hodge = TISAInstruction(TISAOpcode.T_HODGE_PROJ, rd=4, rs1=2)
        word_hodge = encode_t_isa_instruction(inst_hodge)
        dec_hodge = decode_t_isa_instruction(word_hodge)
        assert dec_hodge.opcode == TISAOpcode.T_HODGE_PROJ
        assert dec_hodge.rd == 4

        inst_anosov = TISAInstruction(TISAOpcode.T_ANOSOV_PURGE, rd=5, rs1=1)
        word_anosov = encode_t_isa_instruction(inst_anosov)
        dec_anosov = decode_t_isa_instruction(word_anosov)
        assert dec_anosov.opcode == TISAOpcode.T_ANOSOV_PURGE

    def test_coprocessor_ricci_inspect(self):
        """T_RICCI_INSPECT passes when c0 >= 0 and traps, closing the egress gate, when c0 < 0."""
        coproc = RISCVTopologicalCoprocessor()
        coproc.execute_instruction(TISAInstruction(TISAOpcode.T_LOAD_CYCLO, rd=1, imm=(10, 0, 0, 0)))
        res = coproc.execute_instruction(TISAInstruction(TISAOpcode.T_RICCI_INSPECT, rd=2, rs1=1))
        assert res["status"] == "OK"
        assert res["c0"] == 10 and res["c0_nonnegative"] is True
        v = coproc.regfile.read(2)
        assert (v.c0, v.c1, v.c2, v.c3) == (1, 0, 0, 0)
        assert not coproc.bus.is_egress_blocked()

        coproc.execute_instruction(TISAInstruction(TISAOpcode.T_LOAD_CYCLO, rd=3, imm=(-5, 0, 0, 0)))
        with pytest.raises(RicciCurvatureNeckFault):
            coproc.execute_instruction(TISAInstruction(TISAOpcode.T_RICCI_INSPECT, rd=4, rs1=3))
        assert coproc.bus.is_egress_blocked()

    def test_coprocessor_hodge_proj(self):
        """T_HODGE_PROJ keeps (c0, c1) and zeroes (c2, c3), reporting what it removed."""
        coproc = RISCVTopologicalCoprocessor()
        coproc.execute_instruction(TISAInstruction(TISAOpcode.T_LOAD_CYCLO, rd=1, imm=(5, 7, 99, 120)))
        res = coproc.execute_instruction(TISAInstruction(TISAOpcode.T_HODGE_PROJ, rd=2, rs1=1))
        assert res["status"] == "OK"
        assert res["rd"] == 2
        v = coproc.regfile.read(2)
        assert v.c0 == 5
        assert v.c1 == 7
        assert v.c2 == 0
        assert v.c3 == 0
        assert res["removed_norm_sq"] == 99 * 99 + 120 * 120

    def test_coprocessor_anosov_purge(self):
        """T_ANOSOV_PURGE applies the cat map mod 257 to (c0, c1) and (c2, c3); it is invertible, not erasure."""
        coproc = RISCVTopologicalCoprocessor()
        coproc.execute_instruction(TISAInstruction(TISAOpcode.T_LOAD_CYCLO, rd=1, imm=(10, 20, 30, 40)))
        res = coproc.execute_instruction(TISAInstruction(TISAOpcode.T_ANOSOV_PURGE, rd=2, rs1=1))
        assert res["status"] == "OK"
        assert res["inverse_recovers_input"] is True
        v = coproc.regfile.read(2)
        assert v.c0 == (2 * 10 + 20) % 257
        assert v.c1 == (10 + 20) % 257
        assert (v.c2, v.c3) == ((2 * 30 + 40) % 257, (30 + 40) % 257)
        assert AnosovColdBootScrambler.iterate_arnold_map(30, 40, iterations=1) == (v.c2, v.c3)
        assert AnosovColdBootScrambler.inverse_arnold_map(v.c0, v.c1, iterations=1) == (10, 20)

    def test_rocc_instruction_level_execution(self):
        """RoCC-level execution of funct7 0x06, 0x07 and 0x08 with CoprocessorRegisters and MemoryBus."""
        regs = CoprocessorRegisters(32)
        bus = MemoryBus()

        # 0x06: T_RICCI_INSPECT
        regs.write_128bit(1, (5, 0, 0, 0))
        rocc_ricci = RoCCInstruction(funct7=0x06, rs1=1, rd=2)
        res_r = execute_t_isa_instruction(rocc_ricci, regs, bus)
        assert res_r["status"] == "OK"
        assert res_r["c0_nonnegative"] is True
        assert regs.read_128bit(2) == (1, 0, 0, 0)

        # 0x07: T_HODGE_PROJ
        regs.write_128bit(3, (4, 8, 15, 16))
        rocc_hodge = RoCCInstruction(funct7=0x07, rs1=3, rd=4)
        res_h = execute_t_isa_instruction(rocc_hodge, regs, bus)
        assert res_h["status"] == "OK"
        assert res_h["dst"] == (4, 8, 0, 0)

        # 0x08: T_ANOSOV_PURGE
        regs.write_128bit(5, (12, 14, 16, 18))
        rocc_anosov = RoCCInstruction(funct7=0x08, rs1=5, rd=6)
        res_a = execute_t_isa_instruction(rocc_anosov, regs, bus)
        assert res_a["status"] == "OK"
        assert res_a["dst"] == ((2 * 12 + 14) % 257, (12 + 14) % 257, (2 * 16 + 18) % 257, (16 + 18) % 257)
        assert res_a["inverse_recovers_input"] is True
        assert regs.read_128bit(6) == res_a["dst"]
        assert not bus.is_egress_blocked()


class TestGrandMillenniumUnification:
    """Legacy "unification" entry points: exact computations or NOT_IMPLEMENTED, never a Millennium claim."""

    def test_spectral_duality_bridge(self):
        """Pair correlation is not implemented; the Paley P(257) spectral certificate is exact."""
        spacing = SpectralDualityBridge.compute_gue_pair_correlation([1.0, 2.0, 3.0, 4.0])
        assert spacing["status"] == "NOT_IMPLEMENTED"
        assert spacing["normalised_spacings"] == ["1", "1", "1"]

        res = SpectralDualityBridge.verify_spectral_mass_gap(degree=6, prime_p=257)
        assert res["is_ramanujan"] is True
        assert res["degree_used"] == 128
        assert res["requested_degree_available"] is False
        assert "yang_mills_mass_gap_strictly_positive" not in res

    def test_harmonic_cohomology_bridge(self):
        """Exact elliptic-curve point count at 257 and an exact sheaf consistency check."""
        curve = HarmonicCohomologyBridge.compute_bsd_modular_eigenspace(p=257)
        assert curve["status"] == "COMPUTED"
        assert curve["frobenius_trace_ap"] == 257 + 1 - curve["point_count"]
        assert curve["frobenius_trace_ap"] ** 2 <= 4 * 257

        coherent = HarmonicCohomologyBridge.evaluate_p_vs_np_sheaf_obstruction([(1, 0, 0, 0), (1, 0, 0, 0), (1, 0, 0, 0)])
        assert coherent["consistent"] is True
        assert coherent["coboundary_max_edge_norm_sq"] == "0"

        frustrated = HarmonicCohomologyBridge.evaluate_p_vs_np_sheaf_obstruction([(1, 0, 0, 0), (99, 0, 0, 0)])
        assert frustrated["consistent"] is False
        assert frustrated["coboundary_max_edge_norm_sq"] == "9604"
        assert "tractability_class" not in frustrated

    def test_parabolic_flow_singularity_bridge(self):
        """There is no flow model; the method reports NOT_IMPLEMENTED."""
        res = ParabolicFlowSingularityBridge.verify_vorticity_dissipation_and_surgery(
            initial_enstrophy=150.0, viscosity_nu=0.1, timesteps=10
        )
        assert res["status"] == "NOT_IMPLEMENTED"
        assert "bkm_finite_time_blowup_prevented" not in res

    def test_grand_millennium_unification_nexus(self):
        """The requested unification is NOT_IMPLEMENTED; the exact self-checks pass."""
        res = GrandMillenniumUnificationNexus.verify_grand_millennium_unification()
        assert res["status"] == "NOT_IMPLEMENTED"
        assert res["computed_checks_passed"] is True
        assert "the_seven_problems_status" not in res and "unification_invariance_verified" not in res


class TestMillenniumEndpoints:
    """FastAPI endpoints for the legacy "millennium" routes (skipped without fastapi)."""

    @pytest.mark.parametrize(
        "path", ["ricci-surgery", "hodge-project", "ultrametric-sandbox", "anosov-purge", "picard-lefschetz-filter"]
    )
    def test_post_endpoints_require_a_tenant_token(self, client, path):
        assert client.post(f"{MILLENNIUM}/{path}", json={}).status_code == 401

    def test_ricci_surgery_endpoint(self, client):
        resp = client.post(f"{MILLENNIUM}/ricci-surgery", headers=AUTH, json={
            "edges": [
                {"source": "A", "target": "B", "traffic_weight": 1.0},
                {"source": "B", "target": "C", "traffic_weight": 1.0},
                {"source": "C", "target": "A", "traffic_weight": 1.0},
                {"source": "D", "target": "E", "traffic_weight": 1.0},
                {"source": "E", "target": "F", "traffic_weight": 1.0},
                {"source": "F", "target": "D", "traffic_weight": 1.0},
                {"source": "C", "target": "D", "traffic_weight": 1.0},
            ],
            "curvature_threshold": -0.4,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "EDGES_REMOVED"
        assert data["transport_optimality_certified"] is True
        assert data["removed_edge_count"] == 1
        assert data["removed_edges"][0]["ollivier_ricci_curvature"] == "-2/3"
        assert data["curvature_threshold"] == "-2/5"

        self_loop = client.post(f"{MILLENNIUM}/ricci-surgery", headers=AUTH, json={
            "edges": [{"source": "A", "target": "A", "traffic_weight": 1}]
        })
        assert self_loop.status_code == 422

    def test_hodge_project_endpoint(self, client):
        resp = client.post(f"{MILLENNIUM}/hodge-project", headers=AUTH, json={
            "bus_trace": [10.0, 20.0, 10.0, 30.0, 10.0, 20.0, 10.0, 30.0]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "DECOMPOSITION_VERIFIED"
        assert data["mean"] == "35/2"
        assert data["projection_norm_sq"] == "550"
        assert data["residual"] == ["35/2"] * 8

        exact = client.post(f"{MILLENNIUM}/hodge-project", headers=AUTH, json={"bus_trace": ["1/3", "2/3"]}).json()
        assert exact["mean"] == "1/2" and exact["projection"] == ["-1/6", "1/6"]

    def test_ultrametric_sandbox_endpoint(self, client):
        resp = client.post(f"{MILLENNIUM}/ultrametric-sandbox", headers=AUTH, json={
            "enclave_a": "kernel",
            "enclave_b": "user",
            "base_address_a": 4096,
            "base_address_b": 8192,
            "prime_p": 257,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ADDRESS_SETS_DISJOINT"
        assert data["balls_disjoint"] is True
        assert data["p_adic_distance"] == "1"

        congruent = client.post(f"{MILLENNIUM}/ultrametric-sandbox", headers=AUTH, json={
            "enclave_a": "one", "enclave_b": "two", "base_address_a": 7, "base_address_b": 7 + 257, "prime_p": 257,
        })
        assert congruent.json()["status"] == "ADDRESS_SETS_INTERSECT"
        same_name = client.post(f"{MILLENNIUM}/ultrametric-sandbox", headers=AUTH, json={"enclave_a": "x", "enclave_b": "x"})
        assert same_name.status_code == 422
        composite = client.post(f"{MILLENNIUM}/ultrametric-sandbox", headers=AUTH, json={"prime_p": 256})
        assert composite.status_code == 422

    def test_anosov_purge_endpoint(self, client):
        resp = client.post(f"{MILLENNIUM}/anosov-purge", headers=AUTH, json={
            "secret_hex": "414c5f48415241535f534f5645524549474e5f4b4559"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ZEROISED_AND_VERIFIED"
        assert data["input_type"] == "bytearray"
        assert data["buffer_length"] == 22
        assert data["nonzero_bytes_after"] == 0
        assert client.post(f"{MILLENNIUM}/anosov-purge", headers=AUTH, json={"secret_hex": "zz"}).status_code == 422

    def test_picard_lefschetz_endpoint_reports_not_implemented(self, client):
        resp = client.post(f"{MILLENNIUM}/picard-lefschetz-filter", headers=AUTH, json={
            "samples": [[1.0, 0.5], [0.8, -0.3]],
            "jamming_phase_intensity": 2.5,
        })
        assert resp.status_code == 501
        data = resp.json()
        assert data["status"] == "NOT_IMPLEMENTED"
        assert data["input_samples"] == 2
        assert "snr_improvement_db" not in data

    def test_millennium_unification_endpoint(self, client):
        resp = client.get(f"{MILLENNIUM}/unification")
        assert resp.status_code == 501
        data = resp.json()
        assert data["status"] == "NOT_IMPLEMENTED"
        assert data["computed_checks_passed"] is True
        assert "the_seven_problems_status" not in data
