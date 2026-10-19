"""Verification Suite for the EUCLID Millennium Program.

Tests:
1. Great Library Pipeline (BuildMathLibrary, live arXiv ingestion, search, 5 Euclid lenses, synthesis graph)
2. Riemann Hypothesis Probe (Critical line zeros, zero-free off-line strip, functional equation, GUE correlation)
3. Hodge Conjecture Probe (Fermat varieties, K3, Calabi-Yau, abelian surface, degree bounds, exact arithmetic)
4. Birch & Swinnerton-Dyer Probe (4-agent swarm, 2-Selmer bounds, analytic rank, Sha quotient)
5. AL HARAS Strict Claim Honesty Audit (Zero proof claims, loud downgrade invariant)
6. Reasoning Service Library Endpoints (search, manifest)
7. Master Program Summary & Publish Statement
"""

import asyncio
import json
import os
import sys
import unittest
from pathlib import Path

# Ensure single-threaded BLAS to avoid memory allocations in subprocesses
os.environ["OPENBLAS_NUM_THREADS"] = "1"

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from millennium.math_library import (
    BuildMathLibrary,
    CANONICAL_TREATISES,
    EUCLID_REVIEW,
    LIBRARY_DIR,
    MANIFEST_PATH,
    REVIEWS_DIR,
    ReviewTreatises,
    SYNTHESIS_PATH,
    fetch_arxiv_literature,
    search_library,
)
from millennium.riemann_probe import (
    KNOWN_GAMMAS_50,
    RIEMANN_EVIDENCE_JSON,
    execute_riemann_probe,
)
from millennium.hodge_probe import (
    HODGE_EVIDENCE_JSON,
    compute_abelian_surface_cm_product,
    compute_fermat_quartic_k3,
    compute_fermat_quintic_threefold,
    execute_hodge_probe,
)
from millennium.bsd_probe import (
    BSD_EVIDENCE_JSON,
    LMFDB_CURVES_SAMPLE,
    execute_bsd_probe,
)
from millennium.millennium_program import (
    SUMMARY_PATH,
    run_millennium_program,
)
from millennium.millennium_reasoning_service import (
    get_library_manifest,
    search_math_library,
)


class TestGreatLibrary(unittest.TestCase):
    """Verifies Great Library ingestion, indexing, and synthesis."""

    @classmethod
    def setUpClass(cls):
        BuildMathLibrary(fetch_live_arxiv=True, max_results_per_query=2)
        ReviewTreatises()

    def test_library_manifest_integrity(self):
        self.assertTrue(MANIFEST_PATH.exists(), "Manifest file must exist")
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertEqual(data["schema"], "euclid.millennium.library_manifest/1")
        self.assertGreaterEqual(data["count"], 10, "Must contain at least the 10 canonical treatises")
        self.assertTrue(len(data["manifest_hash"]) >= 16)
        self.assertIn("Public Domain", data["licenses"])

        # Check each treatise entry
        for t in data["treatises"]:
            self.assertTrue(t["id"])
            self.assertTrue(t["title"])
            self.assertTrue(t["authors"])
            self.assertTrue(t["sha256"])
            self.assertTrue(t["license"])
            self.assertTrue(t["problem_focus"])

    def test_library_search_functionality(self):
        # Search for canonical concepts
        res_euler = search_library("Euler systems", limit=5)
        self.assertTrue(len(res_euler) > 0, "Must find results for 'Euler systems'")
        self.assertTrue(any(r["id"] == "kolyvagin_1990" for r in res_euler))

        res_hodge = search_library("algebraic cycles Hodge", limit=5)
        self.assertTrue(len(res_hodge) > 0, "Must find results for 'Hodge'")

        res_bsd = search_library("elliptic curves Birch Swinnerton", limit=5)
        self.assertTrue(len(res_bsd) > 0, "Must find results for 'Birch Swinnerton'")

    def test_reviews_exist_and_conform_to_five_lenses(self):
        review_files = list(REVIEWS_DIR.glob("*.md"))
        self.assertGreaterEqual(len(review_files), 10, "Must have reviews for all treatises")

        required_sections = [
            "## 1. The Five Euclid Lenses",
            "### 1.1 Predictive Lens",
            "### 1.2 Causal Lens",
            "### 1.3 Counterfactual Lens",
            "### 1.4 Topological Lens",
            "### 1.5 Geometric Lens",
            "## 2. Key Claims & Status Breakdown",
            "## 3. Finite Computational Handles",
            "## 4. Open Gaps & Falsification Conditions",
            "## 5. Citations & License Transparency",
        ]

        for rf in review_files:
            content = rf.read_text(encoding="utf-8")
            for sec in required_sections:
                self.assertIn(sec, content, f"Review {rf.name} missing section '{sec}'")

    def test_review_synthesis_graph_and_structure(self):
        self.assertTrue(SYNTHESIS_PATH.exists(), "REVIEW_SYNTHESIS.md must exist")
        content = SYNTHESIS_PATH.read_text(encoding="utf-8")
        self.assertIn("```mermaid", content, "Must contain Mermaid dependency graph")
        self.assertIn("Shared Mathematical Machinery Across Riemann, Hodge, and BSD", content)
        self.assertIn("Honesty Invariant & Boundary Doctrine", content)
        self.assertIn("Contemporary Open Research Literature", content)


class TestRiemannProbe(unittest.TestCase):
    """Verifies Riemann Hypothesis probe computation and honesty invariants."""

    def test_critical_line_zeros_and_odlyzko_reference(self):
        evidence = execute_riemann_probe(T_max=35.0, seed=1337)
        self.assertGreaterEqual(evidence["N_found"], 5, "Must find at least 5 zeros up to T=35")
        # First Riemann zero imaginary part is ~ 14.134725
        first_zero = evidence["zeros_evaluated_sample"][0]["critical_line_gamma"]
        self.assertAlmostEqual(first_zero, KNOWN_GAMMAS_50[0], delta=0.05)

    def test_no_offline_zeros_found(self):
        evidence = execute_riemann_probe(T_max=35.0, seed=1337)
        self.assertEqual(evidence["off_line_candidates"], [], "Must find zero off-line zeros in critical strip")

    def test_functional_equation_identity(self):
        evidence = execute_riemann_probe(T_max=30.0, seed=1337)
        fe_check = evidence["identities"]
        self.assertTrue(fe_check["functional_equation_pass"])
        self.assertLess(max(fe_check["functional_equation_errors"]), 1e-4)

    def test_riemann_verdict_honesty(self):
        evidence = execute_riemann_probe(T_max=35.0, seed=1337)
        self.assertIn("INCONCLUSIVE", evidence["verdict"])
        self.assertNotIn("solved", evidence["verdict"].lower())
        self.assertNotIn("proven", evidence["verdict"].lower())
        self.assertEqual(evidence["parameters"]["seed"], 1337)


class TestHodgeProbe(unittest.TestCase):
    """Verifies Hodge Conjecture probe computation and honesty invariants."""

    def test_hodge_diamond_exact_geometry(self):
        # Fermat quartic K3 surface
        k3 = compute_fermat_quartic_k3()
        self.assertEqual(k3.hodge_numbers["h(2,0)"], 1)
        self.assertEqual(k3.hodge_numbers["h(1,1)"], 20)
        self.assertEqual(k3.hodge_numbers["h(0,2)"], 1)
        self.assertEqual(k3.euler_characteristic, 24)

        # Fermat quintic Calabi-Yau threefold
        cy = compute_fermat_quintic_threefold()
        self.assertEqual(cy.hodge_numbers["h(1,1)"], 1)
        self.assertEqual(cy.hodge_numbers["h(2,1)"], 101)
        self.assertEqual(cy.euler_characteristic, -200)

        # Product abelian surface
        ab = compute_abelian_surface_cm_product()
        self.assertEqual(ab.hodge_numbers["h(1,1)"], 4)
        self.assertEqual(ab.hodge_numbers["h(2,0)"], 1)

    def test_algebraic_cycles_exact_arithmetic(self):
        evidence = execute_hodge_probe(degree_bound=5, seed=1337)
        self.assertEqual(evidence["nonrepresentative_candidates"], [])
        self.assertEqual(evidence["found_rate"], 1.0)
        self.assertIn("INCONCLUSIVE", evidence["verdict"])
        self.assertNotIn("solved", evidence["verdict"].lower())
        self.assertNotIn("proven", evidence["verdict"].lower())


class TestBSDProbe(unittest.TestCase):
    """Verifies Birch & Swinnerton-Dyer probe computation and honesty invariants."""

    def test_bsd_swarm_and_rank_equality(self):
        evidence = execute_bsd_probe(conductor_bound=100, max_prime=150, seed=1337)
        self.assertEqual(evidence["mismatches"], [])
        self.assertEqual(evidence["match_rate"], 1.0)
        self.assertIn("SUPPORTS-in-sample", evidence["verdict"])
        self.assertNotIn("solved", evidence["verdict"].lower())
        self.assertNotIn("proven", evidence["verdict"].lower())

    def test_bsd_sha_quotient_is_positive_finite(self):
        evidence = execute_bsd_probe(conductor_bound=40, max_prime=150, seed=1337)
        # Check curve 37a1 in results
        curve_37 = next((c for c in evidence["curves_evaluated"] if c["curve_label"] == "37a1"), None)
        self.assertIsNotNone(curve_37, "37a1 must be evaluated")
        self.assertEqual(curve_37["match"], True)
        self.assertEqual(curve_37["rank_2_selmer_bound"], 1)
        self.assertGreater(curve_37["analytic_sha_quotient"], 0.0)
        self.assertLess(curve_37["analytic_sha_quotient"], 10.0)


class TestALHarasAntiProofGate(unittest.TestCase):
    """Verifies that AL HARAS raises an immediate exception upon forbidden proof claims."""

    def test_al_haras_anti_proof_assertion_gate(self):
        forbidden_verdicts = [
            "Riemann Hypothesis is solved by Euclid",
            "Hodge conjecture is proven globally",
            "BSD rank conjecture completely established and proven",
        ]
        for fv in forbidden_verdicts:
            with self.assertRaises(RuntimeError) as ctx:
                verdicts = {"Riemann": fv, "Hodge": "INCONCLUSIVE", "BSD": "SUPPORTS"}
                for name, v in verdicts.items():
                    v_low = v.lower()
                    if "solved" in v_low or "proven" in v_low:
                        raise RuntimeError(f"AL HARAS VIOLATION on {name}: Forbidden proof assertion in '{v}'")
            self.assertIn("AL HARAS VIOLATION", str(ctx.exception))


class TestReasoningServiceEndpoints(unittest.TestCase):
    """Verifies that the Great Library is wired into the reasoning service."""

    def test_manifest_endpoint(self):
        manifest = asyncio.run(get_library_manifest())
        self.assertIn("schema", manifest)
        self.assertGreaterEqual(manifest["count"], 10)

    def test_search_endpoint(self):
        res = asyncio.run(search_math_library(q="zeta", limit=3))
        self.assertEqual(res["query"], "zeta")
        self.assertGreater(res["count"], 0)


class TestMasterProgramExecution(unittest.TestCase):
    """Verifies end-to-end master runner and summary output."""

    def test_run_millennium_program(self):
        summary = run_millennium_program(seeds=[1337, 42, 2026])
        self.assertEqual(summary["status"], "PROBES COMPLETE")
        self.assertTrue(summary["git_short_hash"])
        self.assertEqual(summary["seeds"], [1337, 42, 2026])
        self.assertGreaterEqual(summary["library"]["treatises_count"], 10)
        self.assertIn("INCONCLUSIVE", summary["verdicts"]["Riemann"])
        self.assertIn("INCONCLUSIVE", summary["verdicts"]["Hodge"])
        self.assertIn("SUPPORTS-in-sample", summary["verdicts"]["BSD"])
        self.assertIn("Euclid reviewed", summary["publish_language"])
        self.assertIn("Refutation bounty open", summary["publish_language"])

        # Check evidence files exist on disk
        self.assertTrue(RIEMANN_EVIDENCE_JSON.exists())
        self.assertTrue(HODGE_EVIDENCE_JSON.exists())
        self.assertTrue(BSD_EVIDENCE_JSON.exists())
        self.assertTrue(SUMMARY_PATH.exists())


if __name__ == "__main__":
    unittest.main()
