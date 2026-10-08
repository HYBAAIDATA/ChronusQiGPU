"""Hermetic release-protocol tests, NOT product/registry qualification evidence."""
import copy
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packaging"))
import verify_registry_release as protocol

SHA = "a" * 40
RUN = "https://github.com/QuantumPhiRedux/PhiMiner/actions/runs/123"


class RegistryProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {"CI_RUN_URL": RUN})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.verdict = {
            "product": "hyba-kellogg-tensor", "version": "1.0.0", "git_sha": SHA,
            "publishable": True, "published": False, "testpypi_verified": False,
            "tests": {"git_sha": SHA, "passed": 211, "failed": 0, "errors": 0, "skipped": 0, "returncode": 0},
            "wheel": {"file": "hyba_kellogg_tensor-1.0.0-py3-none-any.whl", "sha256": "b" * 64},
            "sdist": {"file": "hyba_kellogg_tensor-1.0.0.tar.gz", "sha256": "c" * 64},
        }
        for key in ("cross_version_verified", "tests_passed", "benchmarks_completed", "wheel_built",
                    "standalone_boundary_verified", "registry_verified", "sdist_verified", "attestation_verified",
                    "certificate_verification_passed", "wheel_clean_install_verified"):
            self.verdict[key] = True
        self.paths = []
        for version in ("3.11", "3.12", "3.13", "3.14"):
            parent = self.root / version
            parent.mkdir()
            receipt = {
                "source_commit": SHA, "product": "hyba-kellogg-tensor", "version": "1.0.0", "registry": "testpypi",
                "status": "PASS", "python": version + ".0", "ci_run_url": RUN,
                "checks": {key: True for key in protocol.MANDATORY},
                "artifacts": {key: self.verdict[key] for key in ("wheel", "sdist")},
            }
            for filename, key in (("commands.log", "commands_sha256"), ("custody.json", "custody_sha256"),
                                  ("install-report.json", "install_report_sha256")):
                (parent / filename).write_text("fixture only; not executed package evidence")
                receipt[key] = protocol.file_digest(parent / filename)
            self.paths.append(parent / "receipt.json")
            self.save(self.paths[-1], receipt)

    def save(self, path, row):
        row.pop("receipt_digest", None)
        row["receipt_digest"] = protocol.digest(row)
        path.write_text(json.dumps(row))

    def validate(self, paths=None):
        return protocol.validate_receipts(self.paths if paths is None else paths, self.verdict, "testpypi", SHA)

    def mutate(self, fn):
        row = json.loads(self.paths[0].read_text())
        fn(row)
        self.save(self.paths[0], row)
        with self.assertRaises((ValueError, KeyError)):
            self.validate()

    def test_complete_protocol_fixture(self):
        self.assertEqual(len(self.validate()), 4)

    def test_package_existence_is_not_execution(self):
        self.mutate(lambda r: r.update(checks={"package_exists": True}))

    def test_missing_cli(self):
        self.mutate(lambda r: r["checks"].pop("entry_point"))

    def test_failed_smoke(self):
        self.mutate(lambda r: r["checks"].update(smoke=False))

    def test_missing_restart_replay(self):
        self.mutate(lambda r: r["checks"].pop("restart_replay"))

    def test_stale_sha(self):
        self.mutate(lambda r: r.update(source_commit="d" * 40))

    def test_wrong_registry(self):
        self.mutate(lambda r: r.update(registry="pypi"))

    def test_wrong_product(self):
        self.mutate(lambda r: r.update(product="other"))

    def test_wrong_run(self):
        self.mutate(lambda r: r.update(ci_run_url=RUN + "4"))

    def test_substituted_archive(self):
        self.mutate(lambda r: r.update(artifacts={"wheel": {"sha256": "e" * 64}}))

    def test_tampered_receipt(self):
        row = json.loads(self.paths[0].read_text())
        row["status"] = "FAIL"
        self.paths[0].write_text(json.dumps(row))
        with self.assertRaises(ValueError):
            self.validate()

    def test_missing_matrix_result(self):
        with self.assertRaises(ValueError):
            self.validate(self.paths[:3])

    def test_duplicate_matrix_result(self):
        with self.assertRaises(ValueError):
            self.validate(self.paths + self.paths[:1])

    def test_missing_executed_log(self):
        (self.paths[0].parent / "commands.log").unlink()
        with self.assertRaises(FileNotFoundError):
            self.validate()

    def test_tampered_custody(self):
        (self.paths[0].parent / "custody.json").write_text("different")
        with self.assertRaises(ValueError):
            self.validate()

    def test_duplicate_json_keys(self):
        p = self.root / "bad.json"
        p.write_text('{"status":"PASS","status":"FAIL"}')
        with self.assertRaises(ValueError):
            protocol.load(p)

    def test_candidate_identity_and_qualification(self):
        p = self.root / "verdict.json"
        p.write_text(json.dumps(self.verdict))
        self.assertEqual(protocol.qualification(p, SHA, "hyba-kellogg-tensor")["git_sha"], SHA)
        for key in ("tests_passed", "cross_version_verified", "registry_verified"):
            row = copy.deepcopy(self.verdict)
            row.pop(key)
            p.write_text(json.dumps(row))
            with self.assertRaises(ValueError):
                protocol.qualification(p, SHA, "hyba-kellogg-tensor")

    def test_zero_skips_enforced(self):
        p = self.root / "verdict.json"
        self.verdict["tests"]["skipped"] = 1
        p.write_text(json.dumps(self.verdict))
        with self.assertRaises(ValueError):
            protocol.qualification(p, SHA, "hyba-kellogg-tensor")

    def test_no_tests_is_not_pass(self):
        p = self.root / "verdict.json"
        self.verdict["tests"]["passed"] = 0
        p.write_text(json.dumps(self.verdict))
        with self.assertRaises(ValueError):
            protocol.qualification(p, SHA, "hyba-kellogg-tensor")

    def test_junit_counts_retain_skips(self):
        path = ROOT / "packaging/kellogg-tensor/run_release_gate.py"
        spec = importlib.util.spec_from_file_location("kellogg_source_gate", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        junit = self.root / "tests.xml"
        junit.write_text('<testsuites><testsuite tests="3" failures="0" errors="0" skipped="1" time="0.1"/></testsuites>')
        self.assertEqual(module._junit_counts(junit)["skipped"], 1)


if __name__ == "__main__":
    unittest.main()
