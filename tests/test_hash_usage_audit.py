"""Standalone, offline tests for the advisory audit; standard library only."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "hash_usage_audit.py"
SPEC = importlib.util.spec_from_file_location("hash_usage_audit", SCRIPT)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class HashUsageAuditTests(unittest.TestCase):
    def test_bucket_candidates(self):
        for expression in ("hash_value % 1024", "h%num_buckets", "digest % bucket_count"):
            with self.subTest(expression=expression):
                self.assertEqual(
                    AUDIT.scan_text("x.py", expression)[0]["category"], "bucketing-review"
                )

    def test_ordinary_modulo_not_reported(self):
        self.assertEqual(AUDIT.scan_text("x.py", "minute % 60"), [])

    def test_sha_is_advisory_not_a_mac_diagnosis(self):
        self.assertEqual(
            AUDIT.scan_text("x.py", "hashlib.sha256(header)")[0]["category"],
            "sha256-context-review",
        )

    def test_hmac_and_constant_time_context(self):
        for expression in ("hmac.new(key, msg)", "compare_digest(a, b)"):
            self.assertEqual(AUDIT.scan_text("x.py", expression)[0]["category"], "hmac-context")

    def test_source_values_are_not_emitted(self):
        report = AUDIT.scan_text("x.py", 'hashlib.sha256(b"sensitive-example")')
        self.assertNotIn("sensitive-example", json.dumps(report))
        self.assertEqual(set(report[0]), {"path", "line", "category"})

    def test_line_numbers(self):
        self.assertEqual(AUDIT.scan_text("x.py", "pass\nh % 8")[0]["line"], 2)

    def test_tracked_only_and_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", directory], check=True)
            (root / "a.py").write_text("h % 8\n", encoding="utf-8")
            (root / "untracked.py").write_text("h % 8\n", encoding="utf-8")
            (root / "binary.py").write_bytes(b"\0h % 8")
            (root / "link.py").symlink_to(root / "a.py")
            subprocess.run(["git", "-C", directory, "add", "a.py", "binary.py", "link.py"], check=True)
            output = root / "report.json"
            subprocess.run(
                [sys.executable, str(SCRIPT), "--root", directory, "--output", str(output)],
                check=True,
                capture_output=True,
            )
            report = json.loads(output.read_text())
            self.assertEqual(report["files_scanned"], 1)
            self.assertEqual([entry["path"] for entry in report["findings"]], ["a.py"])
            self.assertTrue(report["advisory_only"])

    def test_missing_repository_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(subprocess.CalledProcessError):
                AUDIT.audit(directory)


if __name__ == "__main__":
    unittest.main()
