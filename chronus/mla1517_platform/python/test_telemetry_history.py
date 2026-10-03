"""Durable telemetry history: bounded append, rotation and tail reads (§7)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from chronus.mla1517.mining.telemetry_history import TelemetryHistory, tail_history


class TelemetryHistoryTests(unittest.TestCase):
    def _history(self, root: Path, **kwargs) -> TelemetryHistory:
        return TelemetryHistory(root / "telemetry_history.jsonl", **kwargs)

    def test_appends_stratum_events_verbatim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            history = self._history(Path(tmp))
            history.append({"seq": 1, "at": 1000.0, "kind": "job", "job_id": "abc"})
            history.append(
                {"seq": 2, "at": 1001.0, "kind": "share", "result": "ACCEPTED", "total": 1}
            )
            records = tail_history(Path(tmp) / "telemetry_history.jsonl", 10)
        self.assertEqual([r["kind"] for r in records], ["job", "share"])
        self.assertEqual(records[0]["data"]["job_id"], "abc")
        self.assertEqual(records[1]["data"]["result"], "ACCEPTED")

    def test_metrics_are_rate_bounded_and_kind_filtered(self) -> None:
        ticks = iter([float(t) for t in range(100)])

        def clock() -> float:
            return next(ticks)

        with tempfile.TemporaryDirectory() as tmp:
            history = self._history(Path(tmp), min_interval_s={"hashrate": 5.0}, clock=clock)
            for _ in range(10):
                history.record_metrics({"hashrate_hs": 1.0, "backend": "cpu"})
            path = Path(tmp) / "telemetry_history.jsonl"
            all_records = tail_history(path, 100)
            only_jobs = tail_history(path, 100, kinds={"job"})
        # t=0 and t=5 pass the 5s bound; the rest are dropped.
        self.assertEqual(len(all_records), 2)
        self.assertTrue(all(r["kind"] == "hashrate" for r in all_records))
        self.assertEqual(only_jobs, [])

    def test_tail_reads_newest_records_and_missing_file_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "telemetry_history.jsonl"
            history = self._history(Path(tmp))
            for index in range(30):
                history.append({"seq": index + 1, "at": 1000.0 + index, "kind": "state"})
            tail = tail_history(path, 5)
            missing = tail_history(Path(tmp) / "absent.jsonl", 5)
        self.assertEqual([r["data"]["seq"] for r in tail], [26, 27, 28, 29, 30])
        self.assertEqual(missing, [])

    def test_rotation_keeps_the_newest_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "telemetry_history.jsonl"
            history = self._history(Path(tmp), max_bytes=200)
            for index in range(20):
                history.append({"seq": index + 1, "at": 1.0, "kind": "job", "job_id": f"j{index}"})
            self.assertTrue(path.exists())
            self.assertTrue(path.with_name("telemetry_history.jsonl.1").exists())
            tail = tail_history(path, 100)
            parsed = [json.loads(line) for line in path.read_text().splitlines() if line]
        self.assertEqual([r["data"]["job_id"] for r in tail], [r["data"]["job_id"] for r in parsed])


if __name__ == "__main__":
    unittest.main()
