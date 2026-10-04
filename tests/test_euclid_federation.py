"""Tests for the EUCLID federation layer."""
import unittest

from euclid.federation import (
    Audit,
    FederationCoherence,
    FederationEmergence,
    FederationEmergenceProposal,
    FederationNode,
    FederationRegistry,
    FederationState,
    FederatedEuclid,
    Governance,
    IntentHarmoniser,
    ManifoldSynthesiser,
    NodeHealth,
    WorldCluster,
    EuclidFederationOrchestrator,
)
from euclid.creative_substrate import (
    CreativeManifold,
    CreatorDirective,
    EuclidCreativeKernel,
    IntentVector,
    ManifoldEdge,
    ManifoldNode,
    SemanticGeometryLayer,
)


class TestFederationCore(unittest.TestCase):
    def setUp(self):
        FederationRegistry.clear()
        Audit.clear()
        WorldCluster.reset()

    def test_node_health(self):
        h = NodeHealth(True, {"warning": True})
        self.assertFalse(h.is_red())
        self.assertTrue(h.is_yellow())
        h2 = NodeHealth(False)
        self.assertTrue(h2.is_red())
        self.assertFalse(h2.is_yellow())

    def test_federation_state(self):
        state = FederationState()
        state.record("a", NodeHealth(True))
        state.record("b", NodeHealth(False))
        self.assertTrue(state.any_red())
        self.assertFalse(state.any_yellow())

    def test_federation_registry(self):
        node = FederationNode("n1", None)
        FederationRegistry.register(node)
        self.assertEqual(FederationRegistry.get("n1"), node)
        self.assertEqual(len(FederationRegistry.all_nodes()), 1)
        with self.assertRaises(Exception):
            FederationRegistry.register(node)


class TestIntentHarmoniser(unittest.TestCase):
    def _make_intent(self, creator, themes):
        return EuclidCreativeKernel().intent_layer.interpret([
            CreatorDirective(creator, f"intent by {creator}", 1.0, {"themes": themes})
        ])

    def test_combine_single(self):
        intent = self._make_intent("a", ("x",))
        result = IntentHarmoniser.combine([intent])
        self.assertIsNotNone(result)
        self.assertEqual(result.creators, ("a",))

    def test_combine_multiple(self):
        i1 = self._make_intent("a", ("x", "y"))
        i2 = self._make_intent("b", ("y", "z"))
        result = IntentHarmoniser.combine([i1, i2])
        self.assertIsNotNone(result)
        self.assertIn("x", result.themes)
        self.assertIn("y", result.themes)
        self.assertIn("z", result.themes)
        self.assertEqual(set(result.creators), {"a", "b"})


class TestManifoldSynthesiser(unittest.TestCase):
    def _make_manifold(self, creator, themes):
        kernel = EuclidCreativeKernel()
        intent = kernel.intent_layer.interpret([
            CreatorDirective(creator, f"manifold by {creator}", 1.0, {"themes": themes})
        ])
        return kernel.geometry_layer.construct(intent)

    def test_merge_single(self):
        m = self._make_manifold("a", ("x",))
        result = ManifoldSynthesiser.merge([m])
        self.assertEqual(result.content_hash, m.content_hash)

    def test_merge_multiple(self):
        m1 = self._make_manifold("a", ("x", "y"))
        m2 = self._make_manifold("b", ("y", "z"))
        result = ManifoldSynthesiser.merge([m1, m2])
        self.assertIsNotNone(result)
        labels = {n.label for n in result.nodes}
        self.assertTrue(labels & {"x", "y", "z"})


class TestGovernance(unittest.TestCase):
    def test_forbids_motif(self):
        self.assertTrue(Governance.forbids_motif("autonomy_shard"))
        self.assertFalse(Governance.forbids_motif("harmony"))

    def test_veto_records(self):
        Audit.clear()
        Governance.veto("test_reason")
        self.assertEqual(len(Audit.records), 1)
        self.assertEqual(Audit.records[0]["veto"], "test_reason")


class TestFederationOrchestrator(unittest.TestCase):
    def setUp(self):
        FederationRegistry.clear()
        Audit.clear()
        WorldCluster.reset()

    def test_orchestrator_startup(self):
        n1 = FederatedEuclid("node-1", EuclidCreativeKernel())
        n2 = FederatedEuclid("node-2", EuclidCreativeKernel())
        gov = Governance()
        orch = EuclidFederationOrchestrator([n1.node, n2.node], gov)
        state = orch.startup()
        self.assertFalse(state.any_red())
        self.assertIn("node-1", state.node_states)
        self.assertIn("node-2", state.node_states)

    def test_run_single_cycle(self):
        n1 = FederatedEuclid("node-1", EuclidCreativeKernel())
        n2 = FederatedEuclid("node-2", EuclidCreativeKernel())
        gov = Governance()
        orch = EuclidFederationOrchestrator([n1.node, n2.node], gov)
        orch.startup()
        result = orch.run_single_cycle()
        self.assertEqual(result["cycles_completed"], 2)
        self.assertEqual(result["node_count"], 2)
