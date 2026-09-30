"""Retarget-window telemetry truth-boundary tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mla1517.mining.retarget_telemetry import DIFF1_WORK, RetargetWindowTracker


def _snapshot(
    *,
    height: int,
    session: str = "s1",
    difficulty: float | None = 4.0,
    submitted: int = 0,
    accepted: int = 0,
    rejected: int = 0,
    unknown: int = 0,
    stale: int = 0,
    fingerprint: str = "job-a",
    rtt: float | None = None,
) -> dict:
    return {
        "session_id": session,
        "primary": {"pool_id": "pool-a"},
        "job": {
            "block_height": height,
            "fingerprint": fingerprint,
            "difficulty": difficulty,
        },
        "counters": {
            "submitted": submitted,
            "accepted": accepted,
            "rejected": rejected,
            "unknown": unknown,
        },
        "outcomes": {"stale_dropped": stale},
        "submission": {
            "rtt_ms": {"last": rtt},
        },
    }


class RetargetTelemetryTests(unittest.TestCase):
    def test_epoch_position_and_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "retarget.json"
            tracker = RetargetWindowTracker(path)
            with patch("mla1517.mining.retarget_telemetry.time.time", return_value=100.0):
                status = tracker.observe(_snapshot(height=4035, fingerprint="job-4035"))
            self.assertEqual(status["epoch"], 2)
            self.assertEqual(status["position"], 3)
            self.assertEqual(status["next_retarget_height"], 6048)
            self.assertEqual(status["blocks_until_next_retarget"], 2013)
            self.assertTrue(path.exists())
            persisted = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["schema"], "pythia.retarget_windows/1")

    def test_effective_hashrate_requires_complete_difficulty_evidence(self) -> None:
        tracker = RetargetWindowTracker(None)
        with patch("mla1517.mining.retarget_telemetry.time.time", return_value=100.0):
            tracker.observe(_snapshot(height=900_001, submitted=0, accepted=0))
        with patch("mla1517.mining.retarget_telemetry.time.time", return_value=110.0):
            status = tracker.observe(
                _snapshot(height=900_001, submitted=1, accepted=1, difficulty=4.0, rtt=2.5)
            )
        self.assertAlmostEqual(status["effective_stratum_hashrate_hs"], 4.0 * DIFF1_WORK / 10.0)
        self.assertTrue(status["effective_hashrate_complete"])
        self.assertEqual(status["accepted_ratio"], 1.0)
        self.assertEqual(status["submit_rtt_last_ms"], 2.5)

    def test_stale_candidates_are_persisted_in_candidate_ratios(self) -> None:
        tracker = RetargetWindowTracker(None)
        tracker.observe(_snapshot(height=900_001))
        status = tracker.observe(
            _snapshot(
                height=900_001,
                submitted=3,
                accepted=2,
                rejected=1,
                stale=1,
                fingerprint="job-b",
            )
        )
        self.assertEqual(status["candidate_total"], 4)
        self.assertEqual(status["stale"], 1)
        self.assertEqual(status["accepted_ratio"], 0.5)
        self.assertEqual(status["rejected_ratio"], 0.25)
        self.assertEqual(status["stale_ratio"], 0.25)

    def test_unknown_difficulty_keeps_effective_hashrate_unavailable(self) -> None:
        tracker = RetargetWindowTracker(None)
        with patch("mla1517.mining.retarget_telemetry.time.time", return_value=100.0):
            tracker.observe(_snapshot(height=900_001, difficulty=None))
        with patch("mla1517.mining.retarget_telemetry.time.time", return_value=110.0):
            status = tracker.observe(
                _snapshot(
                    height=900_001,
                    difficulty=None,
                    submitted=1,
                    accepted=1,
                    fingerprint="job-c",
                )
            )
        self.assertIsNone(status["effective_stratum_hashrate_hs"])
        self.assertFalse(status["effective_hashrate_complete"])
        self.assertEqual(status["accepted_without_difficulty"], 1)

    def test_session_counter_reset_does_not_create_negative_work(self) -> None:
        tracker = RetargetWindowTracker(None)
        tracker.observe(_snapshot(height=900_001, session="old", submitted=4, accepted=3))
        status = tracker.observe(
            _snapshot(height=900_001, session="new", submitted=1, accepted=1, fingerprint="job-d")
        )
        self.assertEqual(status["submitted"], 5)
        self.assertEqual(status["accepted"], 4)

    def test_missing_height_is_not_inferred(self) -> None:
        tracker = RetargetWindowTracker(None)
        snapshot = _snapshot(height=900_001)
        snapshot["job"]["block_height"] = None
        self.assertIsNone(tracker.observe(snapshot))


if __name__ == "__main__":
    unittest.main()
