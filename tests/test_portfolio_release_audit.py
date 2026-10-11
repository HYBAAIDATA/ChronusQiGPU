"""Portfolio release audit — evidence-derived state ladder tests.

The audit must derive publication state only from executed evidence: local
verdicts qualify, registry presence + green same-sha smoke receipts verify,
and an immutable PyPI release without executed evidence is an incident, never
a quiet success.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packaging"))
import portfolio_release_audit as audit

SHA = "a" * 40
OTHER = "b" * 40


def _versioned(versions):
    return {"releases": {v: [] for v in versions}}


def _fetcher(registry):
    def fetch(url):
        for index, base in audit.INDEXES.items():
            if url.startswith(base):
                name = url.rstrip("/").split("/")[-2]
                versions = registry.get(index, {}).get(name)
                return None if versions is None else _versioned(versions)
        return None
    return fetch


def _receipt(product, registry, sha=SHA, python="3.12", status="PASS",
             checks=None):
    return {"schema": "hyba.registry-execution.v1", "product": product,
            "registry": registry, "python": python, "source_commit": sha,
            "status": status,
            "checks": checks or {"registry_install": True},
            "_file": f"r/{product}-{registry}-{python}.json"}


class SpecifierTests(unittest.TestCase):
    def test_exact(self):
        self.assertTrue(audit.satisfies("1.0.0", "==1.0.0"))
        self.assertFalse(audit.satisfies("1.0.1", "==1.0.0"))

    def test_range(self):
        self.assertTrue(audit.satisfies("1.0.0", ">=1.0,<2"))
        self.assertTrue(audit.satisfies("1.9.9", ">=1.0,<2"))
        self.assertFalse(audit.satisfies("2.0.0", ">=1.0,<2"))
        self.assertFalse(audit.satisfies("0.9", ">=1.0,<2"))

    def test_malformed_refused(self):
        self.assertFalse(audit.satisfies("1.0.0", "banana"))


class WorkflowContractTests(unittest.TestCase):
    def test_missing_oidc_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            wf = Path(td) / "wf.yml"
            wf.write_text("on:\n  workflow_dispatch:\nsteps: []\n")
            row = audit.workflow_contract(wf, {})
            self.assertFalse(row["ok"])
            self.assertIn("OIDC permission", row["missing"])

    def test_shared_workflow_requires_per_product_verdicts(self):
        with tempfile.TemporaryDirectory() as td:
            wf = Path(td) / "wf.yml"
            wf.write_text(
                "workflow_dispatch publish id-token: write "
                "gh-action-pypi-publish environment: testpypi pypi "
                "theseus-release-verdict\n")
            row = audit.workflow_contract(
                wf, {"workflow_strings": ["theseus-release-verdict",
                                          "ovid-release-verdict"]})
            self.assertFalse(row["ok"])
            self.assertIn("per-product verdict artifact ovid-release-verdict",
                          row["missing"])


class LocalVerdictTests(unittest.TestCase):
    def test_status_and_bool_verdicts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            saved, audit.REPO = audit.REPO, root
            try:
                v = root / "packaging/x/dist/artifact-verdict.json"
                v.parent.mkdir(parents=True)
                v.write_text(json.dumps({"product": "hyba-x", "version": "1.0.0",
                                         "source_commit": SHA, "status": "PASS"}))
                row = audit.local_verdict(v, {"sha_field": "source_commit",
                                              "verdict_status": "PASS"}, "hyba-x")
                self.assertTrue(row["passed"])
                v.write_text(json.dumps({"product": "hyba-x", "version": "1.0.0",
                                         "source_commit": SHA, "status": "FAIL"}))
                row = audit.local_verdict(v, {"sha_field": "source_commit",
                                              "verdict_status": "PASS"}, "hyba-x")
                self.assertFalse(row["passed"])
                self.assertEqual(row["checks_failed"], ["status"])
            finally:
                audit.REPO = saved


class StateLadderTests(unittest.TestCase):
    """audit_product against a synthetic product in a temp repo."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.saved = audit.REPO
        audit.REPO = self.root
        (self.root / ".github/workflows").mkdir(parents=True)
        (self.root / ".github/workflows/x.yml").write_text(
            "workflow_dispatch publish id-token: write "
            "gh-action-pypi-publish environment: testpypi environment: pypi\n")
        (self.root / "packaging/x/dist").mkdir(parents=True)
        self.product = {
            "order": 9, "workflow": ".github/workflows/x.yml",
            "verdict": "packaging/x/dist/v.json",
            "verdict_status": "PASS", "sha_field": "source_commit",
            "deps": {}, "smoke_pythons": ["3.12"],
        }

    def tearDown(self):
        audit.REPO = self.saved
        self.td.cleanup()

    def _verdict(self, sha=SHA, status="PASS", name="hyba-x"):
        (self.root / "packaging/x/dist/v.json").write_text(json.dumps(
            {"product": name, "version": "1.0.0", "source_commit": sha,
             "status": status}))

    def _run(self, registry=None, receipts=(), sha=SHA):
        return audit.audit_product(
            "hyba-x", self.product, sha=sha,
            fetcher=_fetcher(registry or {}), receipts=list(receipts),
            offline=False)

    def test_blocked_without_verdict(self):
        self.assertEqual(self._run()["state"], "BLOCKED")

    def test_blocked_on_failed_local_gate(self):
        self._verdict(status="FAIL")
        row = self._run()
        self.assertEqual(row["state"], "BLOCKED")
        self.assertTrue(any("local gate" in b for b in row["blockers"]))

    def test_stale_verdict_rejected_for_frozen_rc(self):
        self._verdict(sha=OTHER)
        row = self._run()
        self.assertEqual(row["state"], "BLOCKED")
        self.assertTrue(row["stale_evidence"])

    def test_qualified_when_local_green(self):
        self._verdict()
        self.assertEqual(self._run()["state"], "QUALIFIED")

    def test_testpypi_requires_executed_smoke_matrix(self):
        self._verdict()
        registry = {"testpypi": {"hyba-x": ["1.0.0"]}}
        self.assertEqual(self._run(registry)["state"], "QUALIFIED")
        row = self._run(registry, [_receipt("hyba-x", "testpypi")])
        self.assertEqual(row["state"], "TESTPYPI_VERIFIED")

    def test_wrong_sha_receipt_not_counted(self):
        self._verdict()
        registry = {"testpypi": {"hyba-x": ["1.0.0"]}}
        row = self._run(registry, [_receipt("hyba-x", "testpypi", sha=OTHER)])
        self.assertEqual(row["state"], "QUALIFIED")
        self.assertTrue(row["stale_evidence"])

    def test_pypi_and_release_complete(self):
        self._verdict()
        registry = {"testpypi": {"hyba-x": ["1.0.0"]},
                    "pypi": {"hyba-x": ["1.0.0"]}}
        receipts = [_receipt("hyba-x", "testpypi"),
                    _receipt("hyba-x", "pypi")]
        row = self._run(registry, receipts)
        self.assertEqual(row["state"], "PYPI_VERIFIED")
        publication = {"product": "hyba-x", "published": True,
                       "testpypi_verified": True, "registry": "publication",
                       "_file": "r/final.json"}
        row = self._run(registry, receipts + [publication])
        self.assertEqual(row["state"], "RELEASE_COMPLETE")

    def test_pypi_publish_without_smoke_is_incident_not_success(self):
        self._verdict()
        registry = {"testpypi": {"hyba-x": ["1.0.0"]},
                    "pypi": {"hyba-x": ["1.0.0"]}}
        row = self._run(registry, [_receipt("hyba-x", "testpypi")])
        self.assertEqual(row["state"], "TESTPYPI_VERIFIED")
        self.assertEqual(row["incident"]["type"],
                         "published_without_executed_pypi_evidence")

    def test_pypi_smoke_failure_is_incident(self):
        self._verdict()
        registry = {"testpypi": {"hyba-x": ["1.0.0"]},
                    "pypi": {"hyba-x": ["1.0.0"]}}
        row = self._run(registry, [_receipt("hyba-x", "testpypi"),
                                   _receipt("hyba-x", "pypi", status="FAIL")])
        self.assertEqual(row["state"], "TESTPYPI_VERIFIED")
        self.assertEqual(row["incident"]["type"], "pypi_smoke_failure")

    def test_dependency_must_resolve_on_same_registry(self):
        self.product["deps"] = {"hyba-dep": "==1.0.0"}
        self._verdict()
        registry = {"testpypi": {"hyba-x": ["1.0.0"]}}
        row = self._run(registry, [_receipt("hyba-x", "testpypi")])
        # Dependency absent on testpypi: published state is an incident and the
        # product cannot advance past TESTPYPI without it.
        self.assertEqual(row["incident"]["type"],
                         "published_before_dependency_prerequisites")
        self.assertTrue(any("hyba-dep" in b for b in row["blockers"]))

    def test_identity_mismatch_blocked(self):
        self._verdict(name="hyba-other")
        self.assertEqual(self._run()["state"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
