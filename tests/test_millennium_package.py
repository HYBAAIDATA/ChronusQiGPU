"""Package contract for ``millennium`` — the consolidated Clay problem surface.

These tests pin two invariants:

1.  **Presence** — every Millennium implementation file (Yang-Mills,
    Poincare, BSD, Hodge, Riemann, Navier-Stokes, P-vs-NP surfaces) must be
    inside the ``millennium/`` package.  If a file is dropped or moved, the
    suite's own ``asset_inventory()`` and the manifest below both fail.
2.  **Honesty** — no probe may claim a Clay problem ESTABLISHED.  The
    ``assert_no_established()`` invariant must hold on a quick sweep.
"""

import importlib
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_PKG = _ROOT / "millennium"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import millennium  # noqa: E402

# Every file that belongs to the consolidated Millennium package.
_PACKAGE_FILES = (
    "__init__.py",
    "__main__.py",
    "millennium_suite.py",
    "mathematical_discovery.py",
    "grover_exact_scale.py",
    "quantum_algorithms.py",
    "nobel_fields_intelligence.py",
    "yang_mills_data.py",
    "poincare_cassini_search.py",
    "poincare_golden_11d.py",
    "hyba_poincare_yangmills.py",
    "hyba_golden_mass_gap.py",
    "exact_gap.py",
    "millennium_reasoning_service.py",
    "sl5_millennium_bridge.py",
    "clay_checklist.py",
    "hodge_bridge.ts",
    "rtl/yang_mills_gap_monitor.sv",
    "docs/OPEN_SCIENTIFIC_PROBLEMS_LEDGER.md",
)

_EXPECTED_PROBLEMS = {
    "riemann",
    "p_vs_np",
    "yang_mills",
    "navier_stokes",
    "bsd",
    "hodge",
    "poincare",
}


class MillenniumPackageSurfaceTests(unittest.TestCase):
    def test_millennium_is_a_package_not_a_module(self) -> None:
        self.assertTrue(hasattr(millennium, "__path__"))
        self.assertEqual(Path(millennium.__file__).name, "__init__.py")

    def test_public_surface_resolves(self) -> None:
        for name in millennium.__all__:
            self.assertTrue(hasattr(millennium, name), f"millennium.__all__ missing {name}")

    def test_all_package_files_present(self) -> None:
        missing = [name for name in _PACKAGE_FILES if not (_PKG / name).is_file()]
        self.assertEqual(missing, [], f"missing package files: {missing}")

    def test_seven_clay_problems_declared(self) -> None:
        ids = {p.id for p in millennium.MILLENNIUM_PROBLEMS}
        self.assertEqual(ids, _EXPECTED_PROBLEMS)

    def test_asset_inventory_all_present(self) -> None:
        inventory = millennium.MillenniumSuite(scale="quick").asset_inventory()
        missing = [row["asset"] for row in inventory if not row["file_present"]]
        self.assertEqual(missing, [], f"millennium assets missing on disk: {missing}")


class MillenniumHonestyTests(unittest.TestCase):
    """A quick sweep must complete with zero proof claims."""

    def test_quick_run_makes_no_established_claims(self) -> None:
        suite = millennium.MillenniumSuite(scale="quick")
        report = suite.run()
        self.assertTrue(suite.assert_no_established(report))
        self.assertEqual(report["established_count"], 0)
        self.assertEqual(report["problems"], len(_EXPECTED_PROBLEMS))
        for row in report["summary"]:
            self.assertFalse(row["proof_claim"], row["problem_id"])
            self.assertIn(row["evidence_class"], millennium.EVIDENCE_CLASSES)


class MillenniumNoMockTests(unittest.TestCase):
    """The package must contain real shipped implementations only — no toy,
    dummy, or phantom-engine heuristics."""

    def test_reasoning_service_imports_real_backends(self) -> None:
        service = importlib.import_module("millennium.millennium_reasoning_service")
        # The service must be wired to the real probe suite, not to engine
        # classes that do not exist in this repository.
        self.assertIs(service.MillenniumSuite, millennium.MillenniumSuite)
        source = Path(service.__file__).read_text(encoding="utf-8")
        self.assertNotIn("embedded_control", source)
        self.assertNotIn("PvsNPEngine", source)
        self.assertNotIn("CurveRankHeuristic", source)

    def test_reasoning_service_runs_real_probe(self) -> None:
        import asyncio

        service = importlib.import_module("millennium.millennium_reasoning_service")
        result = asyncio.run(service.analyze_topology({"dimension": 4, "scale": "quick"}))
        self.assertEqual(result["problem_id"], "hodge")
        self.assertFalse(result["proof_claim"])

    def test_nobel_fields_delegates_to_real_probes(self) -> None:
        nf = importlib.import_module("millennium.nobel_fields_intelligence")
        intel = nf.NobelFieldsIntelligence()

        # BSD: real Legendre-sum a_p values — Hasse must hold exactly.
        bsd = intel.explore_bsd_conjecture({"a": -1, "b": 0, "prime_limit": 200})
        self.assertEqual(bsd["hasse_violations"], 0)
        self.assertGreater(bsd["primes_used"], 10)
        self.assertNotIn("operational_rank", bsd)

        # Yang-Mills: the reported gap is the true smallest eigenvalue.
        ym = intel.explore_yang_mills({"lattice_size": 2})
        self.assertGreater(ym["smallest_eigenvalue"], 0.0)
        self.assertLess(ym["hermiticity_residual"], 1e-9)
        self.assertNotIn("stability_score", ym)

        # Riemann: observed prime count equals an independent sieve count.
        rh = intel.explore_riemann_hypothesis({"start": 2, "end": 100})
        self.assertEqual(rh["observed_primes"], 25)
        self.assertNotIn("critical_line_alignment", rh)

        # P vs NP: measured DPLL nodes, not a phase-residual classifier.
        pnp = intel.explore_p_vs_np({"size": 8})
        self.assertIn("measured_median_dpll_nodes", pnp)
        self.assertNotIn("phase_residual", pnp)

        # Every exploration must carry an honest scope, never a proof claim.
        for row in intel.exploration_history:
            self.assertFalse(row["proof_claim"])
            self.assertIn(row["evidence_class"], millennium.EVIDENCE_CLASSES)


class MillenniumPackagingTests(unittest.TestCase):
    """``millennium`` must be in the built distribution, not just the checkout."""

    def test_pyproject_declares_millennium_package(self) -> None:
        import tomllib

        meta = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        packages = meta["tool"]["setuptools"]["packages"]
        self.assertIn("millennium", packages)
        package_dir = meta["tool"]["setuptools"]["package-dir"]
        self.assertEqual(package_dir["millennium"], "millennium")


if __name__ == "__main__":
    sys.path.insert(0, str(_ROOT))
    unittest.main()
