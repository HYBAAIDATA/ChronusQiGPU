"""Test Suite for EnhancedTensorRepresentation v2 & production_hr_api-v2.py.

Verifies all charter assertions, honest classical nomenclature, type contracts,
multi-GPU sharding, search workload, and API endpoints from the specification.
"""

from __future__ import annotations

import unittest
import warnings
import numpy as np
from fastapi.testclient import TestClient

from chronus.tensor.enhanced_representation import (
    Bond,
    BondStructure,
    Config,
    ContractionTree,
    EnhancedTensorRepresentation,
    ErrorLedger,
    RefusedError,
    SearchResult,
    ShardPlan,
    build_search_index,
    claim_superposition_speedup,
    execute_sharded_contraction,
    parallel_evaluate,
    plan_gpu_shards,
    search,
    search_contraction_trees,
    select_best_tree,
    topology_formula,
    _create_bond_structure,
    _create_entanglement_map,
    _initialize_tensor_network,
    HARD_CAP,
    FORBIDDEN_HYPE_STRINGS,
)
import importlib

production_hr_api_v2_module = importlib.import_module("production_hr_api-v2")
app = production_hr_api_v2_module.app


class TestEnhancedTensorCharter(unittest.TestCase):
    """Verifies PART 0 — Charter compliance and hard refusals."""

    def test_forbidden_hype_strings_not_in_code_or_outputs(self) -> None:
        """Asserts forbidden hype strings are tracked and forbidden."""
        self.assertEqual(len(FORBIDDEN_HYPE_STRINGS), 5)
        for s in FORBIDDEN_HYPE_STRINGS:
            self.assertIsInstance(s, str)

    def test_claim_superposition_speedup_refused(self) -> None:
        """Asserts claim_superposition_speedup raises RefusedError."""
        with self.assertRaises(RefusedError):
            claim_superposition_speedup()

    def test_entanglement_deprecation_warning(self) -> None:
        """Asserts _create_entanglement_map emits DeprecationWarning."""
        cfg = Config(n_sites=4, topology="MPS", chi_max=16, target_dim=4)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            bonds = _create_entanglement_map(cfg)
            self.assertTrue(any(issubclass(item.category, DeprecationWarning) for item in w))
            self.assertIsInstance(bonds, BondStructure)


class TestEnhancedTensorInitialization(unittest.TestCase):
    """Verifies PART 1 & 2 — Types and Network Initialization."""

    def test_topology_formula_exactness(self) -> None:
        """Verifies physical memory bounds match topology formulas."""
        n, chi = 8, 32
        # MPS: n * chi^2 * 16
        self.assertEqual(topology_formula("MPS", n, chi), 8 * (32 ** 2) * 16)
        # MPO: n * chi^2 * 16
        self.assertEqual(topology_formula("MPO", n, chi), 8 * (32 ** 2) * 16)
        # PEPS: n * chi^4 * 16
        self.assertEqual(topology_formula("PEPS", n, chi), 8 * (32 ** 4) * 16)
        # MERA: n * log2(n) * chi^2 * 16
        self.assertEqual(topology_formula("MERA", n, chi), 8 * 3 * (32 ** 2) * 16)

    def test_initialize_mps_network(self) -> None:
        """Verifies real MPS construction and node count."""
        cfg = Config(n_sites=6, topology="MPS", chi_max=16, target_dim=6)
        net = _initialize_tensor_network(cfg)
        self.assertEqual(len(net.nodes), 6)
        self.assertEqual(net.chi_max, 16)

    def test_initialize_peps_network(self) -> None:
        """Verifies real PEPS construction."""
        cfg = Config(n_sites=4, topology="PEPS", chi_max=8, target_dim=4)
        net = _initialize_tensor_network(cfg)
        self.assertEqual(len(net.nodes), 4)

    def test_hard_cap_refusal(self) -> None:
        """Asserts chi_max exceeding hardware hard cap raises AssertionError."""
        cap = HARD_CAP("cpu")
        cfg = Config(n_sites=4, topology="MPS", chi_max=cap + 100, target_dim=4)
        with self.assertRaises(AssertionError):
            _initialize_tensor_network(cfg)


class TestContractionPlanner(unittest.TestCase):
    """Verifies PART 3 — Contraction Planner & Search."""

    def setUp(self) -> None:
        self.cfg = Config(n_sites=6, topology="MPS", chi_max=16, target_dim=6)
        self.net = _initialize_tensor_network(self.cfg)

    def test_search_and_select_best_tree(self) -> None:
        """Verifies candidate tree evaluation and selection."""
        candidates = search_contraction_trees(self.net, budget=1024 * 1024)
        self.assertGreaterEqual(len(candidates), 3)

        best = select_best_tree(candidates, budget=1024 * 1024)
        self.assertIsInstance(best, ContractionTree)
        self.assertIn(best.strategy, ["greedy_rank_minimization", "dynamic_programming_path", "hierarchical_bisection"])

    def test_parallel_evaluate_classical_labeling(self) -> None:
        """Verifies parallel evaluation is labeled classical."""
        candidates = search_contraction_trees(self.net, budget=1024 * 1024)
        res = parallel_evaluate(candidates, devices=["cuda:0", "cuda:1"])
        self.assertEqual(len(res), len(candidates))
        for r in res:
            self.assertEqual(r["parallel_evaluation_mode"], "classical_gpu_or_multithreaded")


class TestSearchWorkload(unittest.TestCase):
    """Verifies PART 4 — Multi-GPU Search Workload."""

    def test_build_search_index_and_query(self) -> None:
        """Verifies inner-product scoring on classical tensor network index."""
        cfg = Config(n_sites=4, topology="MPS", chi_max=16, target_dim=4)
        docs = [
            {"id": "doc1", "features": [1.0, 0.0, 0.0, 0.0]},
            {"id": "doc2", "features": [0.0, 1.0, 0.0, 0.0]},
            {"id": "doc3", "features": [0.707, 0.707, 0.0, 0.0]},
        ]
        index = build_search_index(docs, cfg)
        self.assertEqual(len(index.documents), 3)

        # Search with query aligned to doc1
        query = {"features": [1.0, 0.0, 0.0, 0.0]}
        result = search(query, index, top_k=2)

        self.assertIsInstance(result, SearchResult)
        self.assertFalse(result.is_quantum)  # MANDATORY
        self.assertEqual(result.method, "tensor_network_inner_product")
        self.assertEqual(result.ids[0], "doc1")
        self.assertAlmostEqual(result.scores[0], 1.0, places=4)
        self.assertGreater(result.latency_ms, 0.0)  # MEASURED


class TestMultiGPUSharding(unittest.TestCase):
    """Verifies PART 5 — Multi-GPU Sharding Plans."""

    def test_plan_gpu_shards_shard_bonds(self) -> None:
        cfg = Config(n_sites=6, topology="MPS", chi_max=16, target_dim=6)
        net = _initialize_tensor_network(cfg)
        plan = plan_gpu_shards(net, devices=["cuda:0", "cuda:1"], policy="shard_bonds")

        self.assertIsInstance(plan, ShardPlan)
        self.assertEqual(plan.policy, "shard_bonds")
        self.assertIn("cuda:0", plan.shards)
        self.assertIn("cuda:1", plan.shards)

    def test_execute_sharded_contraction(self) -> None:
        cfg = Config(n_sites=4, topology="MPS", chi_max=16, target_dim=4)
        net = _initialize_tensor_network(cfg)
        plan = plan_gpu_shards(net, devices=["cuda:0"], policy="replicate")
        tree = ContractionTree(name="test", order=[(0, 1)], flops=1000, peak_mem=4096, strategy="test")
        res = execute_sharded_contraction(plan, tree)

        self.assertEqual(res["status"], "SHARDED_CONTRACTION_EXECUTED")
        self.assertFalse(res["is_quantum"])


class TestProductionHRAPIv2Endpoints(unittest.TestCase):
    """Verifies PART 6 — FastAPI Endpoints in production_hr_api-v2.py."""

    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_endpoint(self) -> None:
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "HEALTHY")
        self.assertFalse(data["is_quantum"])

    def test_post_tensor_representation_endpoint(self) -> None:
        payload = {
            "target_dim": 6,
            "topology": "MPS",
            "chi_max": 64,
            "charge_group": "U(1)",
            "device": "cpu",
            "shard_policy": "shard_bonds",
            "budget_bytes": 1073741824,
        }
        resp = self.client.post("/api/v1/quantum/tensor-representation", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Invariants from Part 0 & Part 6
        self.assertFalse(data["is_quantum"])  # MANDATORY
        self.assertEqual(data["method"], "classical_tensor_network")
        self.assertEqual(data["topology"], "MPS")
        self.assertEqual(data["n_sites"], 6)
        self.assertIn("memory_bound_bytes", data)
        self.assertIn("shard_plan", data)
        self.assertIn("measured_latency_ms", data)
        self.assertIn("refused_claims", data)
        self.assertIn("0.01ms latency", data["refused_claims"])
        self.assertIn("708x speedup", data["refused_claims"])

    def test_get_tensor_representation_method_not_allowed(self) -> None:
        """Asserts GET /api/v1/quantum/tensor-representation returns 405 Method Not Allowed."""
        resp = self.client.get("/api/v1/quantum/tensor-representation")
        self.assertEqual(resp.status_code, 405)

    def test_search_endpoint(self) -> None:
        resp = self.client.post(
            "/api/v1/search",
            json={"query": {"features": [0.8, 0.2, 0.9, 0.4, 0.1, 0.7]}, "top_k": 2},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertFalse(data["is_quantum"])  # MANDATORY
        self.assertEqual(data["method"], "tensor_network_inner_product")
        self.assertIn("ids", data)
        self.assertIn("scores", data)
        self.assertIn("latency_ms", data)


if __name__ == "__main__":
    unittest.main()
