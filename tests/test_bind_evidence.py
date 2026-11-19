"""Concurrent bind_evidence INDEX updates must retain both checksum rows."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "ci"))

import bind_evidence  # noqa: E402
import pytest

pytestmark = pytest.mark.simulated


class BindEvidenceTests(unittest.TestCase):
    def test_concurrent_binds_keep_both_index_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            evidence = tmp_root / "evidence" / "smoke"
            evidence.mkdir(parents=True)
            paths = []
            for name, body in (
                ("race-a.json", {"started": "A", "exit_code": 0, "git_commit": "aaa"}),
                ("race-b.json", {"started": "B", "exit_code": 0, "git_commit": "bbb"}),
            ):
                path = evidence / name
                path.write_text(json.dumps(body), encoding="utf-8")
                paths.append(path)

            barrier = threading.Barrier(2)
            errors: list[BaseException] = []

            def worker(path: Path) -> None:
                try:
                    barrier.wait(timeout=5)
                    bind_evidence.bind(path, exit_code=0)
                except BaseException as exc:  # noqa: BLE001
                    errors.append(exc)

            with patch.object(bind_evidence, "ROOT", tmp_root):
                threads = [threading.Thread(target=worker, args=(p,)) for p in paths]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=15)

            self.assertEqual(errors, [])
            index = (evidence / "INDEX.sha256").read_text(encoding="utf-8")
            self.assertIn("race-a.json", index)
            self.assertIn("race-b.json", index)
            for path in paths:
                self.assertTrue(Path(str(path) + ".sidecar.json").is_file())
            self.assertFalse((evidence / ".INDEX.sha256.lock").exists())


if __name__ == "__main__":
    unittest.main()
