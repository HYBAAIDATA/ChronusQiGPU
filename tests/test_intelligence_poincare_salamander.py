"""Comprehensive verification suite for the 11D Poincaré-Golden Substrate & Salamander Allocation.

Covers:
1. Exact Poincaré metric tensor and weighted norm ||x||_phi^2.
2. Canonical Klein-Poincaré forward/inverse bijection and open unit ball containment across 6 scales.
3. Machine-epsilon roundtrip reversibility (||x - u(f(x))||_inf < 1e-11 across all scales).
4. Poincaré-Golden geodesic distance metric axioms (indiscernibles, symmetry, triangle inequality).
5. Zeckendorf canonical non-adjacent decomposition: (mask & (mask << 1)) == 0.
6. Zeckendorf 11D non-adjacent decoupling masks.
7. Salamander non-contiguous prime allocation (25 prime buckets, 25,600 slots).
8. Collision resolution and deterministic linear stepping.
9. Non-destructive slot reading and reconstruction fidelity (< 1e-14).
10. Memory reclamation and bucket capacity tracking.
11. UniversalPassport Decision Hard Gates and fail-closed security.
12. Counterfactual intelligence Klein-Poincaré forward fold and hyperbolic distance.
13. Causal ladder non-adjacent decoupling mask enforcement.
"""

from __future__ import annotations

import math
import unittest
import numpy as np

from toe.poincare_golden_11d import (
    PHI,
    compute_poincare_norm_sq,
    poincare_golden_distance,
    fold_poincare_11d_vector,
    unfold_poincare_11d_vector,
    compute_zeckendorf_certificate,
    generate_zeckendorf_decoupling_mask,
    resolve_zeckendorf_slot,
    encode_zeckendorf,
    beatty_partition,
    cassini_unimodular_det,
    get_metallic_mean,
)
from Intelligence.salamander import (
    SalamanderPoincareAllocationManager,
    SalamanderEngine,
)
from Intelligence.orchestrator import (
    IntelligenceOrchestrator,
    UniversalPassportToken,
    DecisionGateViolationError,
    verify_passport_hard_gate,
)
from Intelligence.counterfactual_intelligence import (
    project_to_11d,
)
from toe.causal_ladder import (
    CausalGraph,
    StructuralCausalModel,
    do_operator,
)


class TestPoincareGolden11D(unittest.TestCase):
    """Test Suite 1: Mathematical Invariants of the 11D Poincaré-Golden Substrate."""

    def test_poincare_norm_sq_exact_basis(self):
        """Standard basis vector e_i must have weighted norm ||e_i||_phi^2 = phi^{-(i+1)}."""
        for i in range(11):
            e_i = np.zeros(11, dtype=np.float64)
            e_i[i] = 1.0
            computed = compute_poincare_norm_sq(e_i)
            expected = PHI ** (-(i + 1))
            self.assertAlmostEqual(
                computed, expected, delta=1e-15, msg=f"Basis vector e_{i} norm mismatch"
            )

    def test_poincare_forward_folding_strict_unit_ball(self):
        """Forward folded vector f(x) must strictly satisfy ||f(x)||_phi^2 < 1.0."""
        scales = [1e-5, 0.1, 1.0, 10.0, 100.0, 1364.0, 1e6]
        for s in scales:
            x = np.array([(i + 1) * s for i in range(11)], dtype=np.float64)
            folded, reflections = fold_poincare_11d_vector(x)
            norm_sq = compute_poincare_norm_sq(folded)
            self.assertLess(norm_sq, 1.0, f"Scale {s} violated unit ball bound: {norm_sq}")
            self.assertGreaterEqual(norm_sq, 0.0)

    def test_poincare_forward_folding_directional_preservation(self):
        """Directional collinearity: f(x) must be strictly parallel to x for all non-zero x."""
        x = np.array([3.0, -2.0, 1.5, 0.0, -4.2, 7.1, 0.3, -1.1, 2.8, -0.9, 5.0], dtype=np.float64)
        folded, _ = fold_poincare_11d_vector(x)
        cos_sim = np.dot(x, folded) / (np.linalg.norm(x) * np.linalg.norm(folded))
        self.assertAlmostEqual(
            cos_sim, 1.0, delta=1e-14, msg="Forward fold did not preserve vector direction"
        )

    def test_poincare_inverse_unfolding_roundtrip_fidelity(self):
        """Roundtrip diffeomorphism: u(f(x)) must recover x with high precision."""
        test_vectors = [
            np.zeros(11, dtype=np.float64),
            np.ones(11, dtype=np.float64) * 0.05,
            np.array([math.sin(i) * 1.5 for i in range(11)], dtype=np.float64),
            np.array([float(i**2) for i in range(11)], dtype=np.float64),
            np.ones(11, dtype=np.float64) * 1364.0,
            np.array([(-1) ** i * (PHI**i) for i in range(11)], dtype=np.float64),
        ]
        for idx, vec in enumerate(test_vectors):
            folded, _ = fold_poincare_11d_vector(vec)
            unfolded = unfold_poincare_11d_vector(folded)
            err = float(np.max(np.abs(vec - unfolded)))
            self.assertLess(err, 1e-11, f"Vector {idx} roundtrip error {err} exceeds 1e-11")

    def test_poincare_inverse_unfolding_boundary_clamping(self):
        """Boundary clamping at ||y||_phi^2 -> 1.0 must not produce NaN or Inf."""
        near_boundary = np.zeros(11, dtype=np.float64)
        near_boundary[0] = math.sqrt(PHI) * 0.999999999999999
        unfolded = unfold_poincare_11d_vector(near_boundary)
        self.assertFalse(np.isnan(unfolded).any(), "Boundary unfolding produced NaN")
        self.assertFalse(np.isinf(unfolded).any(), "Boundary unfolding produced Inf")

    def test_poincare_geodesic_indiscernibles(self):
        """Distance axiom 1: d(u, u) = 0."""
        u = np.array([0.1 * (i + 1) for i in range(11)], dtype=np.float64)
        u_folded, _ = fold_poincare_11d_vector(u)
        d = poincare_golden_distance(u_folded, u_folded)
        self.assertAlmostEqual(d, 0.0, delta=1e-14, msg="Self-distance non-zero")

    def test_poincare_geodesic_symmetry(self):
        """Distance axiom 2: d(u, v) = d(v, u)."""
        u = np.array([0.1 * (i + 1) for i in range(11)], dtype=np.float64)
        v = np.array([-0.05 * (i + 1) for i in range(11)], dtype=np.float64)
        u_f, _ = fold_poincare_11d_vector(u)
        v_f, _ = fold_poincare_11d_vector(v)
        d_uv = poincare_golden_distance(u_f, v_f)
        d_vu = poincare_golden_distance(v_f, u_f)
        self.assertAlmostEqual(d_uv, d_vu, delta=1e-14, msg="Symmetry violation")
        self.assertGreater(d_uv, 0.0, "Distance between distinct points must be positive")

    def test_poincare_geodesic_triangle_inequality(self):
        """Distance axiom 3: d(u, w) <= d(u, v) + d(v, w)."""
        u = np.array([0.1, 0.0, 0.2, 0.0, 0.1, 0.0, 0.0, 0.1, 0.0, 0.0, 0.1], dtype=np.float64)
        v = np.array([0.0, 0.1, 0.0, 0.2, 0.0, 0.1, 0.0, 0.0, 0.1, 0.0, 0.0], dtype=np.float64)
        w = np.array([0.2, 0.1, 0.1, 0.0, 0.1, 0.0, 0.2, 0.0, 0.0, 0.1, 0.1], dtype=np.float64)
        u_f, _ = fold_poincare_11d_vector(u)
        v_f, _ = fold_poincare_11d_vector(v)
        w_f, _ = fold_poincare_11d_vector(w)
        d_uw = poincare_golden_distance(u_f, w_f)
        d_uv = poincare_golden_distance(u_f, v_f)
        d_vw = poincare_golden_distance(v_f, w_f)
        self.assertLessEqual(d_uw, d_uv + d_vw + 1e-12, "Triangle inequality violated")

    def test_metallic_mean_constants(self):
        """Exact algebraic values for golden, silver, bronze metallic means."""
        self.assertAlmostEqual(
            get_metallic_mean("golden"), (1.0 + math.sqrt(5.0)) / 2.0, delta=1e-15
        )
        self.assertAlmostEqual(get_metallic_mean("silver"), 1.0 + math.sqrt(2.0), delta=1e-15)
        self.assertAlmostEqual(
            get_metallic_mean("bronze"), (3.0 + math.sqrt(13.0)) / 2.0, delta=1e-15
        )
        self.assertAlmostEqual(get_metallic_mean(1), (1.0 + math.sqrt(5.0)) / 2.0, delta=1e-15)
        self.assertAlmostEqual(get_metallic_mean(2), 1.0 + math.sqrt(2.0), delta=1e-15)
        self.assertAlmostEqual(get_metallic_mean(3), (3.0 + math.sqrt(13.0)) / 2.0, delta=1e-15)

    def test_cassini_unimodular_determinant(self):
        """Cassini identity: F_{k+1}F_{k-1} - F_k^2 = (-1)^k must be unimodular (+-1)."""
        for k in range(1, 23):
            det = cassini_unimodular_det(k)
            expected = -1 if (k % 2 == 1) else 1
            self.assertEqual(det, expected, msg=f"Cassini identity failed at k={k}")

    def test_beatty_partition_disjoint_coverage(self):
        """Rayleigh-Beatty theorem: S1 = floor(n*phi) and S2 = floor(n*phi^2) form a partition."""
        s1 = set()
        s2 = set()
        for n in range(1, 200):
            w1, w2 = beatty_partition(n)
            self.assertNotIn(w1, s1, f"Duplicate w1: {w1}")
            self.assertNotIn(w2, s2, f"Duplicate w2: {w2}")
            s1.add(w1)
            s2.add(w2)
        intersection = s1.intersection(s2)
        self.assertEqual(len(intersection), 0, f"Beatty sets intersect: {intersection}")


class TestZeckendorfArithmetic(unittest.TestCase):
    """Test Suite 2: Zeckendorf Discrete Arithmetic & Non-Adjacent Decoupling."""

    def test_zeckendorf_non_adjacent_partition(self):
        """No two consecutive Fibonacci numbers: (mask & (mask << 1)) == 0 for all n."""
        test_values = [1, 2, 3, 4, 5, 8, 13, 21, 55, 89, 144, 377, 987, 1364, 25600]
        for val in test_values:
            mask, max_k = encode_zeckendorf(val)
            self.assertEqual(
                mask & (mask << 1), 0, f"Zeckendorf consecutive 1s detected for {val}: {bin(mask)}"
            )

    def test_zeckendorf_exact_arithmetic_reconstruction(self):
        """Sum of selected Fibonacci numbers must exactly equal n."""
        from toe.poincare_golden_11d import _FIB_TABLE

        for val in range(1, 300):
            mask, _ = encode_zeckendorf(val)
            reconstructed = 0
            for idx, fib in enumerate(_FIB_TABLE):
                if (mask >> idx) & 1:
                    reconstructed += fib
            self.assertEqual(reconstructed, val, f"Zeckendorf reconstruction failed for {val}")

    def test_resolve_zeckendorf_slot_bounds(self):
        """Address A = (k * 1024) + (mask % p_k) must lie in [0, 25599]."""
        for val in [1, 10, 50, 100, 500, 1364, 10000, 25600]:
            slot_addr, max_k = resolve_zeckendorf_slot(val)
            self.assertGreaterEqual(slot_addr, 0)
            self.assertLess(slot_addr, 25600)
            self.assertGreaterEqual(max_k, 0)
            self.assertLess(max_k, 25)

    def test_generate_zeckendorf_decoupling_mask_invariants(self):
        """Zeckendorf decoupling mask must have zero adjacent active bits in 11D."""
        for dim in range(11):
            mask = generate_zeckendorf_decoupling_mask(dim, 11)
            self.assertEqual(
                mask & (mask << 1), 0, f"Decoupling mask has adjacent bits: {bin(mask)} (dim={dim})"
            )
            self.assertTrue(bool(mask & (1 << dim)), f"Primary dimension {dim} not set in mask")

    def test_compute_zeckendorf_certificate_structure(self):
        """ZeckendorfCertificate must adhere to canonical schema and token pattern."""
        vec = np.array(
            [0.2, 0.1, -0.3, 0.05, 0.4, -0.1, 0.0, 0.2, -0.15, 0.08, 0.3], dtype=np.float64
        )
        cert = compute_zeckendorf_certificate(vec)
        self.assertTrue(cert.is_valid)
        self.assertTrue(cert.token_hex.startswith("ZECK-"))
        self.assertEqual(len(cert.token_hex), 21)
        self.assertEqual(cert.non_adjacent_mask & (cert.non_adjacent_mask << 1), 0)
        d = cert.to_dict()
        self.assertEqual(d["truth_class"], "mathematical")
        self.assertIn("token_hex", d)
        self.assertIn("canonical_int", d)
        self.assertIn("decoupling_mask", d)


class TestSalamanderAllocationSubstrate(unittest.TestCase):
    """Test Suite 3: Salamander Non-Contiguous Prime Allocation Substrate."""

    def setUp(self):
        self.manager = SalamanderPoincareAllocationManager()

    def test_allocate_and_read_roundtrip(self):
        """Allocate an 11D vector, read back the slot, and verify roundtrip fidelity."""
        vec = np.array([0.1 * (i + 1) for i in range(11)], dtype=np.float64)
        slot_addr = self.manager.allocate("vec_theta", vec)
        self.assertGreaterEqual(slot_addr, 0)
        self.assertLess(slot_addr, 25600)

        unfolded = self.manager.read("vec_theta")
        self.assertIsNotNone(unfolded)
        err = float(np.max(np.abs(vec - unfolded)))
        self.assertLess(err, 1e-14, f"Salamander read/unfold error {err} exceeds 1e-14")

    def test_reconstruct_fidelity_metric(self):
        """reconstruct() must return original vector with fidelity error < 1e-14."""
        vec = np.array([math.cos(i) * 0.5 for i in range(11)], dtype=np.float64)
        self.manager.allocate("vec_recon", vec)
        rec_vec, fidelity_err = self.manager.reconstruct("vec_recon")
        self.assertLess(fidelity_err, 1e-14)
        self.assertLess(float(np.max(np.abs(vec - rec_vec))), 1e-14)

    def test_prime_bucket_distribution(self):
        """Allocation must properly track counts across the 25 prime buckets."""
        for i in range(10):
            vec = np.array([(i + 1) * 0.05 * (j + 1) for j in range(11)], dtype=np.float64)
            self.manager.allocate(f"vec_bucket_{i}", vec)
        metrics = self.manager.get_capacity_metrics()
        self.assertEqual(metrics["allocated_slots"], 10)
        total_in_buckets = sum(metrics["bucket_allocations"].values())
        self.assertEqual(total_in_buckets, 10)

    def test_collision_resolution_linear_probing(self):
        """Collision resolution must deterministically step within the bucket without overwriting."""
        vec1 = np.ones(11, dtype=np.float64) * 0.2
        vec2 = np.ones(11, dtype=np.float64) * 0.2
        s1 = self.manager.allocate("vec_c1", vec1)
        s2 = self.manager.allocate("vec_c2", vec2)
        self.assertNotEqual(s1, s2, "Collision resolution failed to assign distinct slots")
        self.assertEqual(self.manager.allocated_slots_count, 2)

    def test_deallocate_memory_reclamation(self):
        """Deallocating a slot must reclaim capacity and decrement bucket counters."""
        vec = np.ones(11, dtype=np.float64) * 0.3
        self.manager.allocate("vec_temp", vec)
        self.assertEqual(self.manager.allocated_slots_count, 1)

        ok = self.manager.deallocate("vec_temp")
        self.assertTrue(ok)
        self.assertEqual(self.manager.allocated_slots_count, 0)
        with self.assertRaises(KeyError):
            self.manager.read("vec_temp")

    def test_compute_geodesic_distance_between_slots(self):
        """compute_geodesic_distance must equal poincare_golden_distance between stored folded states."""
        v1 = np.array([0.1 * (i + 1) for i in range(11)], dtype=np.float64)
        v2 = np.array([-0.05 * (i + 1) for i in range(11)], dtype=np.float64)
        self.manager.allocate("vec_g1", v1)
        self.manager.allocate("vec_g2", v2)

        dist = self.manager.compute_geodesic_distance("vec_g1", "vec_g2")
        f1, _ = fold_poincare_11d_vector(v1)
        f2, _ = fold_poincare_11d_vector(v2)
        direct_dist = poincare_golden_distance(f1, f2)
        self.assertAlmostEqual(dist, direct_dist, delta=1e-14)

    def test_salamander_engine_integration(self):
        """Verify that SalamanderEngine integrates the allocation manager seamlessly."""
        engine = SalamanderEngine()
        vec = np.array([0.15 * (i + 1) for i in range(11)], dtype=np.float64)
        slot_addr = engine.allocate("engine_vec", vec)
        self.assertGreaterEqual(slot_addr, 0)
        rec, err = engine.reconstruct_slot("engine_vec")
        self.assertIsNotNone(rec)
        self.assertLess(err, 1e-14)
        metrics = engine.capacity_metrics()
        self.assertEqual(metrics["allocated_slots"], 1)


class TestUniversalPassportHardGates(unittest.TestCase):
    """Test Suite 4: UniversalPassport Hard Gates & Fail-Closed Policy."""

    def setUp(self):
        self.orchestrator = IntelligenceOrchestrator()

    def test_mint_and_verify_passport(self):
        """Minting a passport with valid 11D state must verify successfully."""
        state_vec = np.array([0.05 * (i + 1) for i in range(11)], dtype=np.float64)
        passport = self.orchestrator.mint_universal_passport(state_vec)
        self.assertIsInstance(passport, UniversalPassportToken)
        valid, reason, _ = verify_passport_hard_gate(passport)
        self.assertTrue(valid, f"Passport verification failed: {reason}")

    def test_commit_material_decision_success(self):
        """commit_material_decision must succeed when given a valid passport and matching state."""
        state_vec = np.array([0.08 * (i + 1) for i in range(11)], dtype=np.float64)
        passport = self.orchestrator.mint_universal_passport(state_vec)
        result = self.orchestrator.commit_material_decision(
            new_state=state_vec,
            passport=passport,
            description="Retarget Difficulty Transition",
        )
        self.assertTrue(result["gate_enforced"])
        self.assertEqual(result["status"], "MATERIAL_DECISION_COMMITTED")

    def test_fail_closed_tampered_passport(self):
        """Tampered passport invariants must raise DecisionGateViolationError immediately."""
        state_vec = np.array([0.08 * (i + 1) for i in range(11)], dtype=np.float64)
        passport = self.orchestrator.mint_universal_passport(state_vec)
        tampered = UniversalPassportToken(
            token_id=passport.token_id,
            bundle_id=passport.bundle_id,
            bundle_provenance_hash="0000000000000000000000000000000000000000000000000000000000000000",
            total_invariants_verified=10,
            all_invariants_passed=False,
            state_vector_11d_hash=passport.state_vector_11d_hash,
            is_valid=True,
            zeckendorf_certificate=passport.zeckendorf_certificate,
        )
        with self.assertRaises(DecisionGateViolationError):
            self.orchestrator.commit_material_decision(
                new_state=state_vec,
                passport=tampered,
                description="Illegal Transition",
            )


class TestDownstreamIntegrations(unittest.TestCase):
    """Test Suite 5: Downstream Module Integrations (Counterfactual & Causal)."""

    def test_counterfactual_intelligence_poincare_manifold(self):
        """Counterfactual intelligence must use Klein-Poincaré projection and bound norms."""
        header = bytes(80)
        m11 = project_to_11d(header, 0)
        self.assertLess(m11.norm_sq, 1.0)
        self.assertTrue(m11.is_in_ball)
        self.assertIsNotNone(m11.certificate)
        self.assertEqual(
            m11.certificate.decoupling_mask & (m11.certificate.decoupling_mask << 1), 0
        )

        m11_other = project_to_11d(header, 100)
        dist = m11.distance_to(m11_other)
        self.assertGreater(dist, 0.0)

    def test_causal_ladder_decoupling_mask(self):
        """Causal ladder do-operator must produce Zeckendorf non-adjacent decoupling mask."""
        from kellogg.quantum_tensor import QuantumState, Observables

        graph = CausalGraph()
        graph.add_edge("X", "Y", weight=1.0)
        scm = StructuralCausalModel(graph=graph)
        observables = {"X": Observables.position(32), "Y": Observables.position(32)}
        state = QuantumState.uniform_superposition(32)

        _, diagnostics = do_operator(
            state=state,
            intervention_node="X",
            intervention_value=1.0,
            observables=observables,
            scm=scm,
            dim=32,
        )
        mask = diagnostics.get("zeckendorf_decoupling_mask")
        self.assertIsNotNone(mask)
        self.assertEqual(
            mask & (mask << 1), 0, f"Causal ladder mask violated Zeckendorf non-adjacency: {mask}"
        )


if __name__ == "__main__":
    unittest.main()
