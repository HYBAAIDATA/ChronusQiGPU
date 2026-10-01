"""New TOE expansion contract tests.

These tests cover capabilities added above the original TOE bridge smoke suite:
canonical heterogeneous payloads, 11D certificates, scale authorization,
truth-boundary rejection, and causal graph direction.
"""
import sys
import unittest

sys.path.insert(0, "/data/pythia_real")
sys.path.insert(0, "/data/pythia_real/chronus/mla1517_platform/python")

from toe.causal_ladder import CausalGraph
from toe.operator_compilers import compile_operator
from toe.bridge import TOEBridge
from toe.expansion import TOEExpansionEngine, TOEExpansionPolicy


class TOEExpansionContractTests(unittest.TestCase):
    def setUp(self):
        self.engine = TOEExpansionEngine(
            policy=TOEExpansionPolicy(scale_indices=(10, 15, 31, 76))
        )

    def test_new_heterogeneous_surfaces_collapse(self):
        surfaces = {
            "document": {"title": "incident", "body": "thermal recovery"},
            "graph": {"edges": [("source", "router"), ("router", "sink")]},
            "code": "def fold_state(x): return x",
            "binary": bytes(range(128)),
            "events": [{"t": 1, "event": "open"}, {"t": 2, "event": "close"}],
        }
        for domain, data in surfaces.items():
            result = self.engine.collapse(data, domain=domain, context_id=domain)
            self.assertTrue(result.available, domain)
            self.assertTrue(result.state_certificate["is_valid"], domain)
            self.assertTrue(result.capabilities["exact_tensor"]["exact"], domain)
            self.assertTrue(result.capabilities["exact_tensor"]["normalized_exact"], domain)
            self.assertFalse(result.proof_boundary["theorem_proven"])
            self.assertEqual(result.execution_envelope["math_scale"], 76)

    def test_schema_digest_is_canonical_but_schema_sensitive(self):
        first = self.engine.collapse({"a": 1, "b": 2})
        reordered = self.engine.collapse({"b": 2, "a": 1})
        renamed = self.engine.collapse({"c": 1, "b": 2})
        self.assertEqual(first.input_digest, reordered.input_digest)
        self.assertEqual(first.state_certificate["token"], reordered.state_certificate["token"])
        self.assertNotEqual(first.input_digest, renamed.input_digest)

    def test_typed_operator_compilers_preserve_structure(self):
        document = compile_operator("thermal drift recovery plan")
        graph = compile_operator({"edges": [("a", "b"), ("b", "c")]})
        events = compile_operator({"events": [{"event": "open"}, {"event": "close"}]})
        code = compile_operator("def f(x):\n    if x:\n        return x")
        binary = compile_operator(bytes(range(16)))
        self.assertEqual(document.operator, "lexical_diagonal_operator")
        self.assertEqual(graph.payload["adjacency"], [[0, 1, 0], [0, 0, 1], [0, 0, 0]])
        self.assertEqual(events.payload["transitions"], [("open", "close")])
        self.assertEqual(code.operator, "control_flow_token_operator")
        self.assertEqual(code.payload["control_flow_tokens"], ["def", "if", "return"])
        self.assertEqual(binary.operator, "byte_fold_mod_256")
        self.assertEqual(binary.payload["byte_length"], 16)

    def test_scale_budget_is_fail_closed(self):
        engine = TOEExpansionEngine(
            policy=TOEExpansionPolicy(
                scale_indices=(10, 1000),
                scale_families=("golden",),
                max_physical_bytes=300,
            )
        )
        result = engine.collapse({"series": [1, 2, 3]}, domain="budget")
        self.assertFalse(result.available)
        self.assertEqual([item["accepted"] for item in result.scale_program], [True, False])
        self.assertEqual(result.scale_program[-1]["reason"], "output_budget_exceeded")

    def test_full_pisot_scale_program_and_receipt(self):
        result = self.engine.collapse(
            {"series": [1, 1, 2, 3, 5, 8, 13, 21]},
            domain="recurrence",
            context_id="full-family",
        )
        self.assertTrue(result.available)
        self.assertEqual(
            {item["point"]["family"] for item in result.scale_program},
            {"golden", "silver", "plastic", "supergolden", "tribonacci"},
        )
        self.assertEqual(len(result.scale_program), 20)
        self.assertEqual(len(result.receipt_digest), 64)
        self.assertEqual(result.operator["kind"], "time_series")
        self.assertEqual(result.capability_matrix["physical_acceleration"]["status"], "hardware_gated")

    def test_nonfinite_input_is_not_silently_zeroed(self):
        result = TOEBridge().predict({"x": float("nan")})
        self.assertFalse(result["available"])
        self.assertFalse(result["state_tomography"]["available"])
        self.assertIn("non-finite", result["state_tomography"]["diagnostics"]["error"])

    def test_exact_tensor_rejects_undeclared_continuous_evolution(self):
        result = TOEBridge().exact_tensor({"x": 1}, quarter_turns=0.5)
        self.assertFalse(result["available"])
        self.assertFalse(result["theorem_proven"])
        self.assertIn("integer", result["diagnostics"]["error"])

    def test_causal_edge_direction_and_transitive_queries(self):
        graph = CausalGraph()
        graph.add_edge("A", "B")
        graph.add_edge("B", "C")
        self.assertEqual(graph.parents["B"], ["A"])
        self.assertEqual(graph.children["A"], ["B"])
        self.assertEqual(graph.ancestors("C"), {"A", "B"})
        self.assertEqual(graph.descendants("A"), {"B", "C"})
        self.assertEqual(graph.topological_order(), ["A", "B", "C"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
