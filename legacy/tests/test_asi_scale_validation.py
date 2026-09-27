"""Scale-validation suite for the ASI manifold elevation.

Proves the S-2 / S-3 / S-11 schools operate on genuine multidimensional
manifold objects — the 11D Poincaré-Golden ball B_phi^11 — and not on
dressed-up scalars. Every assertion exercises the shared adapter
pythagoras/asi/manifold_bridge.py against the read-only substrate
Intelligence/poincare_golden_11d.py.
"""

from __future__ import annotations

import itertools
import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Intelligence.poincare_golden_11d import compute_poincare_norm_sq
from pythagoras.asi import manifold_bridge as mb
from pythagoras.asi.causal_reasoning import CausalModel, CausalReasoningEngine
from pythagoras.asi.information_integration import InformationIntegrationMeasurer
from pythagoras.asi.predictive_processing import PredictiveProcessingEngine


class TestManifoldBridgeGeometry(unittest.TestCase):
    """The golden -> standard isometry and curvature -1 operators."""

    def test_standardize_is_exact_isometry(self):
        rng = np.random.default_rng(3)
        for _ in range(5):
            x = mb.as_ball_vector(rng.normal(0.0, 0.4, 11))
            y = mb.standardize(x)
            self.assertAlmostEqual(
                float(np.dot(y, y)),
                compute_poincare_norm_sq(x),
                delta=1e-15,
            )

    def test_exp_log_roundtrip(self):
        rng = np.random.default_rng(11)
        x = mb.as_ball_vector(rng.normal(0.0, 0.3, 11))
        y = mb.standardize(x)
        v = rng.normal(0.0, 0.05, 11)
        z = mb.exp_map(y, v)
        self.assertLess(float(np.dot(z, z)), 1.0)
        self.assertLess(float(np.max(np.abs(mb.log_map(y, z) - v))), 1e-12)

    def test_lift_project_roundtrip_under_1e_minus_14(self):
        rng = np.random.default_rng(5)
        for _ in range(6):
            x = mb.as_ball_vector(rng.normal(0.0, 0.35, 11))
            u = mb.unfold_ball_vector(x)
            x2 = mb.fold_ambient_vector(u)
            self.assertLess(float(np.max(np.abs(x2 - x))), 1e-14)
            u2 = mb.unfold_ball_vector(x2)
            self.assertLess(float(np.max(np.abs(u2 - u))), 1e-14)

    def test_geodesic_descent_monotone_and_in_ball(self):
        target = np.full(11, 0.02)

        def objective(x):
            return 0.5 * float(np.sum((x - target) ** 2))

        def grad(x):
            return x - target

        xs, info = mb.geodesic_descent(
            np.zeros(11), objective, grad, step_size=0.5, tol=1e-12, max_steps=300
        )
        hist = info["free_energy_history"]
        self.assertTrue(
            all(b <= a + 1e-15 for a, b in zip(hist, hist[1:])),
            "free energy increased during geodesic descent",
        )
        self.assertLess(hist[-1], hist[0])
        self.assertLess(hist[-1], 1e-8)
        self.assertLess(compute_poincare_norm_sq(xs), 1.0)


class TestManifoldBridgeProjections(unittest.TestCase):
    """state_to_graph / state_to_covariance / state_to_prior_layers."""

    def test_graph_is_dag_derived_from_state(self):
        rng = np.random.default_rng(13)
        x = mb.as_ball_vector(rng.normal(0.0, 0.4, 11))
        adj = mb.state_to_graph(x)
        self.assertEqual(adj.shape, (11, 11))
        order = mb.topological_sort(adj)
        self.assertEqual(len(order), 11)
        # strictly upper-triangular orientation => acyclic by construction
        self.assertTrue(np.all(np.tril(adj) == 0.0))

    def test_covariance_psd_and_deterministic(self):
        x = mb.as_ball_vector(np.linspace(-0.2, 0.2, 11))
        c1 = mb.state_to_covariance(x)
        c2 = mb.state_to_covariance(x)
        self.assertTrue(np.allclose(c1, c2))
        self.assertTrue(np.all(np.linalg.eigvalsh(c1) > 0.0))

    def test_prior_layers_stay_in_ball(self):
        x = mb.as_ball_vector(np.linspace(-0.3, 0.3, 11))
        layers = mb.state_to_prior_layers(x, 4)
        self.assertEqual(len(layers), 4)
        for layer in layers:
            self.assertLess(compute_poincare_norm_sq(layer), 1.0)

    def test_scalar_projection_bounds(self):
        x = mb.as_ball_vector(np.linspace(-0.3, 0.3, 11))
        s = mb.scalar_projection(x)
        self.assertGreaterEqual(s, 0.0)
        self.assertLess(s, 1.0)


class TestInformationMeasures(unittest.TestCase):
    """Genuine bipartite MIP on covariance (Gaussian) and density (QRE) routes."""

    def _correlated_cov(self, n, seed=0):
        rng = np.random.default_rng(seed)
        a = rng.normal(0.0, 1.0, (n, n))
        return a @ a.T + 0.05 * np.eye(n)

    def test_gaussian_mip_converges_n8_12_16(self):
        for n in (8, 12, 16):
            cov = self._correlated_cov(n, seed=n)
            r = mb.minimum_information_partition(cov)
            self.assertEqual(r["method"], "gaussian_relative_entropy")
            self.assertIsNotNone(r["partition"])
            self.assertGreater(r["phi"], 0.0)
            self.assertTrue(np.isfinite(r["phi"]))

    def test_gaussian_phi_zero_for_product_states(self):
        cov = self._correlated_cov(8, seed=1)
        product = np.diag(np.diag(cov))
        r = mb.minimum_information_partition(product)
        self.assertAlmostEqual(r["phi"], 0.0, delta=1e-12)

    def test_quantum_mip_bell_vs_product(self):
        bell = np.zeros(4, dtype=np.complex128)
        bell[0] = bell[3] = 1.0 / math.sqrt(2.0)
        rho_bell = np.outer(bell, bell.conj())
        r = mb.minimum_information_partition(rho_bell, site_dims=[2, 2])
        self.assertEqual(r["method"], "quantum_relative_entropy")
        self.assertAlmostEqual(r["phi"], 2.0 * math.log(2.0), delta=1e-12)

        product = np.diag([1.0, 0.0, 0.0, 0.0]).astype(np.complex128)
        rp = mb.minimum_information_partition(product, site_dims=[2, 2])
        self.assertAlmostEqual(rp["phi"], 0.0, delta=1e-12)

    def test_quantum_mip_ghz_3site(self):
        ghz = np.zeros(8, dtype=np.complex128)
        ghz[0] = ghz[7] = 1.0 / math.sqrt(2.0)
        rho = np.outer(ghz, ghz.conj())
        r = mb.minimum_information_partition(rho, site_dims=[2, 2, 2])
        self.assertGreater(r["phi"], math.log(2.0) - 1e-12)


class TestS3ManifoldElevation(unittest.TestCase):
    """S-3 acceptance: MIP over manifold/covariance/density inputs."""

    def setUp(self):
        self.measurer = InformationIntegrationMeasurer({})

    def test_mip_converges_on_n8_12_16(self):
        for n in (8, 12, 16):
            rng = np.random.default_rng(n)
            a = rng.normal(0.0, 1.0, (n, n))
            cov = a @ a.T + 0.05 * np.eye(n)
            r = self.measurer.measure_phi_covariance(cov)
            self.assertGreater(r.phi, 0.0)
            self.assertTrue(np.isfinite(r.phi))
            self.assertEqual(r.partitions_evaluated, 2 ** (n - 1) - 1)
            self.assertEqual(r.phi_scalar, r.to_scalar())

    def test_manifold_state_phi_and_dual_mode(self):
        rng = np.random.default_rng(4)
        x = mb.as_ball_vector(rng.normal(0.0, 0.3, 11))
        r = self.measurer.measure_phi_manifold(x)
        self.assertEqual(r.method, "gaussian_relative_entropy")
        self.assertEqual(self.measurer.phi_scalar, r.phi)
        self.assertIsInstance(r.to_scalar(), float)

    def test_density_route_entangled_vs_product(self):
        bell = np.zeros(4, dtype=np.complex128)
        bell[0] = bell[3] = 1.0 / math.sqrt(2.0)
        r = self.measurer.measure_phi_density(np.outer(bell, bell.conj()), [2, 2])
        self.assertEqual(r.method, "quantum_relative_entropy")
        self.assertAlmostEqual(r.phi, 2.0 * math.log(2.0), delta=1e-12)
        product = np.diag([1.0, 0.0, 0.0, 0.0]).astype(np.complex128)
        rp = self.measurer.measure_phi_density(product, [2, 2])
        self.assertAlmostEqual(rp.phi, 0.0, delta=1e-12)

    def test_scalar_path_unchanged(self):
        subsystems = {
            "parity": lambda xs: [x % 2 for x in xs],
            "mod3": lambda xs: [x % 3 for x in xs],
            "mod5": lambda xs: [x % 5 for x in xs],
        }
        measurer = InformationIntegrationMeasurer(subsystems)
        report = measurer.measure_phi(list(range(20)))
        self.assertIn("integrated_information_phi", report)
        mip = measurer.find_minimum_information_partition(list(range(20)))
        self.assertIsNotNone(mip["partition"])


class TestS2ManifoldElevation(unittest.TestCase):
    """S-2 acceptance: arbitrary DAGs, matrix severing, do-composition."""

    @staticmethod
    def _dag_model():
        adj = np.zeros((11, 11))
        adj[0, 2] = 1.0
        adj[1, 2] = 0.5
        adj[2, 3] = 0.7
        adj[3, 4] = 0.4
        adj[5, 6] = 0.9
        adj[6, 7] = 0.3
        return CausalModel.from_adjacency(adj)

    def test_adjacency_matrix_and_severing(self):
        eng = CausalReasoningEngine(self._dag_model())
        adj = eng.adjacency_matrix
        self.assertEqual(adj.shape, (11, 11))
        severed = eng.severed_adjacency(["x2"])
        self.assertTrue(np.all(severed[:, 2] == 0.0))
        self.assertGreater(eng.adjacency_matrix[0, 2], 0.0)

    def test_do_result_invariant_under_topological_resorting(self):
        edges = {"x": ["y"], "y": ["z"], "z": []}
        fns = {
            "x": lambda pv: 0.0,
            "y": lambda pv: 2.0 * pv.get("x", 0.0),
            "z": lambda pv: pv.get("y", 0.0) + 1.0,
        }
        reference = CausalReasoningEngine(CausalModel(list("xyz"), edges, fns)).intervene(
            {"y": 10.0}, evidence={"x": 3.0}
        )
        for perm in itertools.permutations("xyz"):
            eng = CausalReasoningEngine(CausalModel(list(perm), edges, fns))
            self.assertEqual(eng.intervene({"y": 10.0}, evidence={"x": 3.0}), reference)
            self.assertEqual(eng.intervene_matrix({"y": 10.0}, evidence={"x": 3.0}), reference)

    def test_matrix_path_matches_scalar_path(self):
        eng = CausalReasoningEngine(
            CausalModel(
                list("xyz"),
                {"x": ["y"], "y": ["z"], "z": []},
                {
                    "x": lambda pv: 0.0,
                    "y": lambda pv: 2.0 * pv.get("x", 0.0),
                    "z": lambda pv: pv.get("y", 0.0) + 1.0,
                },
            )
        )
        self.assertEqual(
            eng.intervene({"y": 10.0}, evidence={"x": 3.0}),
            eng.intervene_matrix({"y": 10.0}, evidence={"x": 3.0}),
        )

    def test_multi_intervention_matches_composition(self):
        eng = CausalReasoningEngine(self._dag_model())
        state = mb.as_ball_vector(np.linspace(-0.2, 0.2, 11))
        multi = eng.intervene_on_state(state, {0: 0.4, 2: -0.6, 5: 0.9})
        r1 = eng.intervene_on_state(state, {0: 0.4})
        r2 = eng.intervene_on_state(r1.state, {2: -0.6}, prior=r1)
        r3 = eng.intervene_on_state(r2.state, {5: 0.9}, prior=r2)
        for k in multi.values:
            self.assertAlmostEqual(r3.values[k], multi.values[k], places=14)
        self.assertLess(compute_poincare_norm_sq(r3.state), 1.0)
        self.assertIsInstance(r3.to_scalar(), float)

    def test_from_manifold_state_builds_11var_scm(self):
        rng = np.random.default_rng(9)
        state = mb.as_ball_vector(rng.normal(0.0, 0.4, 11))
        eng = CausalReasoningEngine.from_manifold_state(state)
        self.assertEqual(len(eng.model.variables), 11)
        r = eng.intervene_on_state(state, {0: 0.3})
        self.assertAlmostEqual(r.values["x0"], 0.3)


class TestS11ManifoldElevation(unittest.TestCase):
    """S-11 acceptance: geodesic descent over hierarchical 11-D errors."""

    def test_free_energy_monotone_until_convergence(self):
        eng = PredictiveProcessingEngine()
        obs = mb.as_ball_vector(np.linspace(-0.15, 0.25, 11))
        r = eng.perceive_manifold(obs, depth=3, tol=1e-10)
        hist = r.free_energy_history
        self.assertTrue(
            all(b <= a + 1e-15 for a, b in zip(hist, hist[1:])),
            "free energy increased during geodesic descent",
        )
        self.assertTrue(r.converged)
        self.assertLess(hist[-1], hist[0])

    def test_final_state_inside_poincare_ball(self):
        eng = PredictiveProcessingEngine()
        obs = mb.as_ball_vector(np.linspace(-0.15, 0.25, 11))
        r = eng.perceive_manifold(obs, depth=4)
        for layer in r.layers:
            self.assertLess(compute_poincare_norm_sq(layer), 1.0)
        self.assertLess(compute_poincare_norm_sq(r.belief_state), 1.0)
        self.assertLess(compute_poincare_norm_sq(r.predicted_state), 1.0)

    def test_lift_project_roundtrip_under_1e_minus_14(self):
        rng = np.random.default_rng(21)
        for _ in range(5):
            x = mb.as_ball_vector(rng.normal(0.0, 0.35, 11))
            u = mb.unfold_ball_vector(x)
            x2 = mb.fold_ambient_vector(u)
            self.assertLess(float(np.max(np.abs(x2 - x))), 1e-14)

    def test_dual_mode_scalar_contract(self):
        eng = PredictiveProcessingEngine()
        obs = mb.as_ball_vector(np.linspace(-0.1, 0.1, 11))
        r = eng.perceive_manifold(obs, depth=3)
        self.assertIsInstance(r.to_scalar(), float)
        self.assertIsInstance(r.predicted_phi, float)
        b = eng.perceive(0.9, 0.1)
        self.assertGreater(b.precision, 0.0)


if __name__ == "__main__":
    unittest.main()
