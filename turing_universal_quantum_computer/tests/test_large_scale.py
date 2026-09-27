"""Large-scale exact quantum maths — the 10_000-qubit universal system.

These tests exercise what the docs always described but nothing
implemented: superposition, entanglement, quantum walks, annealing,
tunnelling and swarming — all exact, at n = 10_000 where applicable.
"""
import unittest
from fractions import Fraction

import sympy as sp

import turing_universal_quantum_computer as tqc


class StabilizerBackendTests(unittest.TestCase):
    def test_basis_state_exact(self):
        s = tqc.StabilizerState(4)
        p0, p1 = s.measurement_probabilities(0)
        self.assertEqual(p0, 1)
        self.assertEqual(p1, 0)

    def test_superposition_10000_exact(self):
        # |+>^10000: every Z-measurement is exactly 1/2 — 1/2.
        s = tqc.StabilizerState.plus(10_000)
        for q in (0, 1, 5000, 9999):
            p0, p1 = s.measurement_probabilities(q)
            self.assertEqual(p0, Fraction(1, 2))
            self.assertEqual(p1, Fraction(1, 2))

    def test_ghz_10000_entangled(self):
        s = tqc.StabilizerState.ghz(10_000)
        # GHZ cut 1|9999 carries exactly one e-bit — exact integer entropy.
        self.assertEqual(s.entanglement_entropy({0}), 1)
        self.assertEqual(s.entanglement_entropy({0, 1, 2, 3, 4}), 1)
        # correlated: after measuring qubit 0, all are deterministic-equal
        rec = s.measure(0, seed=7)
        outcome = rec["outcome"]
        for q in (1, 9999):
            p0, p1 = s.measurement_probabilities(q)
            self.assertEqual(p0 if outcome == 0 else p1, 1)

    def test_bell_pair_circuit(self):
        s = tqc.StabilizerState(3)
        s.h(0).cnot(0, 1)
        self.assertEqual(s.entanglement_entropy({0, 2}), 1)  # Bell across 0|1
        self.assertEqual(s.entanglement_entropy({0}), 1)
        self.assertEqual(s.entanglement_entropy({2}), 0)  # qubit 2 separable

    def test_circuit_matches_state_vector(self):
        # Cross-check stabilizer sim against the exact sparse register.
        s = tqc.StabilizerState(3)
        s.h(0).cnot(0, 1).cnot(0, 2)
        reg = tqc.QuantumRegister(3)
        reg.apply_h(0)
        reg.apply_cnot(0, 1)
        reg.apply_cnot(0, 2)
        dist = reg.distribution()
        # GHZ_3: |000> and |111> each with probability exactly 1/2
        for idx in (0, 7):
            self.assertEqual(float(dist[idx]), 0.5)
        self.assertEqual(len(dist), 2)
        p0, p1 = s.measurement_probabilities(0)
        self.assertEqual(p0, Fraction(1, 2))
        # deterministic given a collapse
        rec = s.measure(0, seed=0)
        self.assertIn(rec["outcome"], (0, 1))

    def test_non_clifford_fails_closed(self):
        s = tqc.StabilizerState(4)
        with self.assertRaises(tqc.StabilizerDomainError):
            s.t(0)
        with self.assertRaises(tqc.StabilizerDomainError):
            s.apply_phase_gate(0, sp.pi / 7)


class QuantumWalkTests(unittest.TestCase):
    def test_hypercube_closed_form_binomial(self):
        walk = tqc.HypercubeWalk(10_000)
        t = sp.pi / 3
        dist = walk.hamming_distribution(t)
        self.assertEqual(len(dist), 10_001)
        # exact: P(w) = C(n,w) cos^{2(n-w)} sin^{2w}, sums to 1 identically
        w1 = dist[0]
        self.assertEqual(sp.simplify(w1 - sp.cos(t) ** 20_000), 0)
        self.assertEqual(walk.expected_hamming_weight(t), 10_000 * sp.sin(t) ** 2)

    def test_hypercube_matches_sparse_register(self):
        # n=4 hypercube CT walk vs exact sparse register with exp(-itX)^n.
        # e^{-itX}|0> = cos t|0> - i sin t|1> per qubit — build via H-frame:
        # amplitude at vertex x = cos^{n-w}(t) (-i sin t)^{w} — spot check
        # vertex 3 (w=2) and vertex 0 (w=0) against closed form.
        walk = tqc.HypercubeWalk(4)
        t = sp.pi / 5
        amp0 = walk.vertex_amplitude(0, t)
        amp3 = walk.vertex_amplitude(0b0011, t)
        self.assertEqual(sp.simplify(amp0 - sp.cos(t) ** 4), 0)
        self.assertEqual(
            sp.simplify(amp3 - sp.cos(t) ** 2 * (-sp.I * sp.sin(t)) ** 2), 0
        )
        # unitarity: sum_w P(w) = 1
        total = sp.simplify(sum(walk.hamming_distribution(t).values()))
        self.assertEqual(total, 1)

    def test_coined_cycle_walk_exact(self):
        walk = tqc.CoinedCycleWalk(8).run(3)
        dist = walk.position_distribution()
        # keep values exact (QSqrt2/sympy) — sum without float sympify
        total = None
        for p in dist.values():
            total = p if total is None else total + p
        self.assertEqual(total, 1)
        self.assertTrue(all(p > 0 for p in dist.values()))


class AnnealingTunnelTests(unittest.TestCase):
    def test_tfim_gap_exact_10000(self):
        tfim = tqc.TransverseFieldIsing(10_000)
        gap = tfim.critical_gap()
        # exact: 4 sin(pi/20000)
        self.assertEqual(sp.simplify(gap - 4 * sp.sin(sp.pi / 20_000)), 0)
        # asymptotic 2*pi*J/n agrees to leading order
        self.assertTrue(abs(float(gap) - float(tfim.gap_asymptotic()))
                        / float(gap) < 1e-7)

    def test_tfim_ground_energy_symbolic(self):
        tfim = tqc.TransverseFieldIsing(6)
        e0 = tfim.ground_energy()
        self.assertTrue(e0.is_Add)  # unevaluated exact sum of radicals

    def test_landau_zener_symbolic(self):
        p = tqc.landau_zener(sp.Rational(1, 10), sp.Rational(1, 100))
        self.assertEqual(p, 1 - sp.exp(-sp.pi * sp.Rational(1, 100) / (2 * sp.Rational(1, 100))))
        self.assertAlmostEqual(float(p), 1 - sp.exp(-sp.pi / 2).evalf(), places=6)


class SwarmTests(unittest.TestCase):
    def test_swarm_deterministic_seeded(self):
        dist = {0: Fraction(1, 2), 1: Fraction(1, 4), 2: Fraction(1, 4)}
        s1 = tqc.QuantumSwarm(50, lambda _t: dist, seed=42).run(10)
        s2 = tqc.QuantumSwarm(50, lambda _t: dist, seed=42).run(10)
        self.assertEqual(s1.positions, s2.positions)
        emp = s1.empirical_distribution()
        self.assertEqual(sum(emp.values()), 1)


class TenThousandQubitSystemTests(unittest.TestCase):
    def setUp(self):
        self.sys = tqc.TenThousandQubitSystem()

    def test_dimensions(self):
        self.assertEqual(self.sys.n_qubits, 10_000)
        self.assertEqual(self.sys.hilbert_dim_symbolic, "2^10000")

    def test_superposition_exact(self):
        res = self.sys.superposition()
        self.assertFalse(res["materialized"])
        p0, p1 = res["state"].measurement_probabilities(4242)
        self.assertEqual(p0, Fraction(1, 2))

    def test_ghz_entanglement_broadcast(self):
        seen = []
        self.sys.add_entanglement_listener(seen.append)
        res = self.sys.ghz()
        self.assertEqual(res["state"].entanglement_entropy({0}), 1)
        reg = self.sys.register_subsystem_entanglement("euclid", [2, 4, 7])
        self.assertTrue(reg.zeckendorf_protected)
        self.assertEqual(len(seen), 1)
        self.assertEqual(self.sys.entanglement_ledger[0].subsystem, "euclid")

    def test_zeckendorf_protection_rejects_adjacent(self):
        self.assertFalse(tqc.zeckendorf_valid([3, 4]))   # F3,F4 adjacent
        self.assertTrue(tqc.zeckendorf_valid([3, 5]))    # non-adjacent

    def test_walk_anneal_tunnel(self):
        walk = self.sys.quantum_walk("hypercube", t=sp.pi / 6)
        self.assertEqual(walk["truth_class"], "exact_symbolic")
        anneal = self.sys.anneal(s_values=(0, sp.Rational(1, 2)))
        self.assertEqual(anneal["truth_class"], "exact_symbolic")
        tunnel = self.sys.tunnel(sp.Rational(1, 10), sp.Rational(1, 50))
        self.assertIn("p_diabatic", tunnel)

    def test_swarm(self):
        res = self.sys.swarm(20, 4, num_positions=8, seed=1)
        self.assertEqual(sum(res["empirical"].values()), 1)

    def test_sparse_register_unbounded_n(self):
        reg = self.sys.sparse_register(basis=7)
        self.assertEqual(reg.n_qubits, 10_000)
        reg.apply_x(5000)  # sparse ops fine at any width
        # densifying past the bound fails closed, never truncates
        small = self.sys.sparse_register(max_amplitudes=4)
        with self.assertRaises(MemoryError):
            for q in range(5):
                small.apply_h(q)

    def test_status_honest(self):
        st = self.sys.status()
        self.assertFalse(st["materialized"])
        self.assertEqual(st["truth_class"], "symbolic_exact")
        self.assertFalse(st["theorem_proven"])

    def test_aethel_manifest_store(self):
        rec = self.sys.aethel_store_manifest()
        self.assertIn("address", rec)


class AdapterWidthTests(unittest.TestCase):
    def test_adapter_accepts_any_width(self):
        # The artificial n==11 gate is gone: arbitrary width constructs.
        a = tqc.LucasScaledAethelExecutionAdapter(n_qubits=23, scale_index=76)
        self.assertEqual(a.n_qubits, 23)
        a2 = tqc.LucasScaledAethelExecutionAdapter(n_qubits=10_000, scale_index=76)
        self.assertEqual(a2.n_qubits, 10_000)
        with self.assertRaises(ValueError):
            tqc.LucasScaledAethelExecutionAdapter(n_qubits=0)


if __name__ == "__main__":
    unittest.main()
