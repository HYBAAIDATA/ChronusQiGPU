"""Fail-closed tests for Turing structural-research claim promotion.

These tests do not prove the research claims. They enforce the opposite: a
research claim may not silently become a production claim just because prose or
an implementation name exists.
"""

from __future__ import annotations

import json
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "docs" / "turing_structural_research_gates.json"
SPEC = REPO_ROOT / "docs" / "TURING_STRUCTURAL_RESEARCH_GATES.md"


class StructuralResearchGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.spec_text = SPEC.read_text(encoding="utf-8")
        cls.gates = {gate["claim_id"]: gate for gate in cls.manifest["gates"]}

    def test_schema_and_normative_document_are_pinned(self):
        self.assertEqual(
            self.manifest["schema"], "turing.structural_research_gates.v1"
        )
        self.assertEqual(
            self.manifest["normative_document"],
            "docs/TURING_STRUCTURAL_RESEARCH_GATES.md",
        )
        self.assertEqual(self.manifest["status"], "RESEARCH_GATED")

    def test_all_four_required_research_programmes_exist(self):
        self.assertEqual(
            set(self.gates),
            {
                "turing.fold_gap.v1",
                "turing.orbit_collapse.stabilizer_frontier.v1",
                "turing.pisot_transform.v1",
                "turing.dimension_11.v1",
            },
        )

    def test_no_research_gate_is_pre_promoted(self):
        self.assertFalse(self.manifest["theorem_proven"])
        self.assertFalse(self.manifest["measured_qpu"])
        self.assertFalse(self.manifest["production_claim_allowed"])
        for gate in self.gates.values():
            with self.subTest(claim_id=gate["claim_id"]):
                self.assertFalse(gate["theorem_proven"])
                self.assertFalse(gate["measured_qpu"])
                self.assertFalse(gate["production_claim_allowed"])
                self.assertIn(
                    gate["status"],
                    {
                        "SPECIFIED",
                        "IMPLEMENTED_UNVERIFIED",
                        "FALSIFIED",
                        "BENCHMARKED",
                        "PROVEN",
                        "EVIDENCED",
                        "UNAVAILABLE",
                    },
                )

    def test_future_production_promotion_requires_evidence(self):
        for gate in self.gates.values():
            if not gate["production_claim_allowed"]:
                continue
            with self.subTest(claim_id=gate["claim_id"]):
                self.assertEqual(gate["status"], "EVIDENCED")
                self.assertTrue(gate["implementation_ref"])
                self.assertTrue(gate["benchmark_artifacts"] or gate["proof_artifacts"])
                self.assertNotIn("UNAVAILABLE", str(gate["supported_domain"]))

    def test_theorem_flag_requires_a_proof_artifact(self):
        for gate in self.gates.values():
            if gate["theorem_proven"]:
                with self.subTest(claim_id=gate["claim_id"]):
                    self.assertTrue(gate["proof_artifacts"])

    def test_fold_gap_is_measured_code_length_not_measured_kolmogorov_complexity(self):
        gate = self.gates["turing.fold_gap.v1"]
        self.assertEqual(
            gate["formula"], "FoldGap_bits(x;B,F) = L_B(x) - L_F(x)"
        )
        required = set(gate["required_receipt_fields"])
        self.assertTrue(
            {
                "baseline_bits",
                "folded_bits",
                "model_cost_bits",
                "decoder_cost_policy",
                "lossless_reconstruction",
                "reconstructed_digest",
            }.issubset(required)
        )
        self.assertIn("ensemble quantity", gate["shannon_boundary"])
        self.assertIn("not directly measurable", " ".join(gate["limitations"]))

    def test_stabilizer_extension_claim_is_still_false(self):
        gate = self.gates["turing.orbit_collapse.stabilizer_frontier.v1"]
        self.assertFalse(gate["strictly_exceeds_stabilizer"])
        self.assertFalse(gate["orbit_collapse_theorem_proven"])
        evidence = " ".join(gate["required_evidence"])
        self.assertIn("non-stabilizer", evidence)
        self.assertIn("Stim", evidence)
        self.assertIn("dense-reference", evidence)

    def test_pisot_transform_does_not_supersede_qft_by_declaration(self):
        gate = self.gates["turing.pisot_transform.v1"]
        self.assertFalse(gate["supersedes_qft"])
        self.assertFalse(gate["fourier_retired"])
        self.assertIn("Matched QFT".lower(), gate["benchmark_spec"].lower())

    def test_eleven_is_a_coordinate_dimension_not_a_physics_claim(self):
        gate = self.gates["turing.dimension_11.v1"]
        self.assertEqual(gate["why_eleven"], "UNPROVEN_SELECTION")
        self.assertIn("eleven coordinates", gate["current_definition"])
        distinct = " ".join(gate["distinct_from"])
        self.assertIn("VIRTUAL_QUANTUM_QUBITS = 11", distinct)
        self.assertIn("M-theory", distinct)
        self.assertIn("spacetime", distinct)

    def test_scientific_corrections_are_pinned(self):
        corrections = self.manifest["corrections"]
        self.assertIn("SU(2)_3", corrections["fibonacci_anyons"])
        self.assertFalse(corrections["phi_is_smallest_pisot"])
        self.assertEqual(corrections["phi_classification"], "quadratic Pisot unit")

    def test_spec_explicitly_preserves_shannon_and_fourier_boundaries(self):
        self.assertIn("Shannon entropy is not wrong", self.spec_text)
        self.assertIn("QFT/Fourier methods remain canonical", self.spec_text)
        self.assertIn("strictly exceeds the stabilizer class", self.spec_text)
        self.assertIn("why eleven?", self.spec_text.lower())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
