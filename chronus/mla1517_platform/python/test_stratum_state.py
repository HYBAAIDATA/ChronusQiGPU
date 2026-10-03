"""Canonical Stratum runtime evidence and job-generation tests."""

from __future__ import annotations

import unittest
from dataclasses import replace

from chronus.mla1517.mining.stratum_adapter import StratumJob, SubscriptionState
from chronus.mla1517.mining.stratum_state import StratumRuntimeState

SUBSCRIPTION = SubscriptionState("01020304", 4)
JOB = StratumJob(
    job_id="job-1",
    prevhash="00" * 32,
    coinb1="01000000",
    coinb2="ffffffff",
    merkle_branch=(),
    version="20000000",
    nbits="1d00ffff",
    ntime="65abcdef",
    clean_jobs=True,
    target=None,
)


def _authorized_state() -> StratumRuntimeState:
    state = StratumRuntimeState(
        pool_id="test-pool",
        endpoint="127.0.0.1:3333",
        worker="PY***",
    )
    state.connecting()
    state.connected()
    state.subscribing()
    state.subscription_confirmed(SUBSCRIPTION)
    state.authorizing()
    state.authorization_confirmed()
    return state


class StratumRuntimeStateTests(unittest.TestCase):
    def test_transport_is_not_authorization_or_readiness(self) -> None:
        state = StratumRuntimeState(
            pool_id="test-pool",
            endpoint="127.0.0.1:3333",
            worker="PY***",
        )
        state.connecting()
        state.connected()
        snapshot = state.snapshot()
        self.assertTrue(snapshot["connected"])
        self.assertFalse(snapshot["primary"]["authorized"])
        self.assertFalse(snapshot["ready"])

    def test_authorized_without_job_waits_for_job(self) -> None:
        state = _authorized_state()
        self.assertEqual(state.snapshot()["state"], "WAITING_JOB")
        self.assertFalse(state.ready)

    def test_job_generations_and_clean_invalidation_are_explicit(self) -> None:
        state = _authorized_state()
        state.target_updated(target=(1 << 255), source="mining.set_target", value="80" + "00" * 31)
        first = state.job_received(replace(JOB, target=state.target), SUBSCRIPTION)
        second_job = replace(JOB, coinb2="eeeeeeee", target=state.target)
        second = state.job_received(second_job, SUBSCRIPTION)
        snapshot = state.snapshot(now=second.received_at)

        self.assertEqual(first.generation_id, 1)
        self.assertEqual(second.generation_id, 2)
        self.assertNotEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(snapshot["job"]["invalidated_generation"], 1)
        self.assertEqual(snapshot["counters"]["jobs_invalidated"], 1)
        self.assertTrue(snapshot["ready"])

    def test_target_change_updates_target_generation_and_fingerprint(self) -> None:
        state = _authorized_state()
        state.target_updated(target=(1 << 255), source="mining.set_difficulty", value=1)
        first = state.job_received(replace(JOB, target=state.target), SUBSCRIPTION)
        state.target_updated(target=(1 << 254), source="mining.set_difficulty", value=2)
        updated = state.current_job

        self.assertIsNotNone(updated)
        self.assertEqual(updated.generation_id, first.generation_id)
        self.assertEqual(updated.target_generation, 2)
        self.assertNotEqual(updated.fingerprint, first.fingerprint)
        self.assertEqual(state.snapshot()["job"]["difficulty_source"], "mining.set_difficulty")

    def test_submission_results_remain_literal(self) -> None:
        state = _authorized_state()
        state.target_updated(target=(1 << 255), source="mining.set_target", value="80" + "00" * 31)
        state.job_received(replace(JOB, target=state.target), SUBSCRIPTION)

        state.submission_started("job-1")
        state.submission_finished(True)
        self.assertEqual(state.snapshot()["submission"]["state"], "ACCEPTED")

        state.submission_started("job-1")
        state.submission_finished(False)
        self.assertEqual(state.snapshot()["submission"]["state"], "REJECTED")
        self.assertEqual(state.snapshot()["counters"]["accepted"], 1)
        self.assertEqual(state.snapshot()["counters"]["rejected"], 1)

    def test_disconnect_during_submit_is_unknown(self) -> None:
        state = _authorized_state()
        state.target_updated(target=(1 << 255), source="mining.set_target", value="80" + "00" * 31)
        state.job_received(replace(JOB, target=state.target), SUBSCRIPTION)
        state.submission_started("job-1")
        state.disconnected("socket closed before response")
        snapshot = state.snapshot()

        self.assertEqual(snapshot["submission"]["state"], "OUTCOME_UNKNOWN")
        self.assertEqual(snapshot["counters"]["unknown"], 1)
        self.assertIsNone(snapshot["job"]["share_target"])
        self.assertFalse(snapshot["ready"])
        with self.assertRaisesRegex(RuntimeError, "already unresolved"):
            state.submission_started("job-1")

    def test_job_snapshot_exports_the_pool_work_fields(self) -> None:
        """§4: the job view needs the fields the pool actually delivered."""
        state = _authorized_state()
        state.target_updated(target=(1 << 255), source="mining.set_target", value="80" + "00" * 31)
        generation = state.job_received(
            replace(
                JOB,
                prevhash="ab" * 32,
                merkle_branch=("cc" * 32, "dd" * 32),
                target=state.target,
            ),
            SUBSCRIPTION,
        )
        job = state.snapshot(now=generation.received_at)["job"]

        self.assertTrue(job["active"])
        self.assertEqual(job["prevhash"], "ab" * 32)
        self.assertEqual(job["version"], "20000000")
        self.assertEqual(job["nbits"], "1d00ffff")
        self.assertEqual(job["ntime"], "65abcdef")
        self.assertEqual(job["extranonce1"], "01020304")
        self.assertEqual(job["extranonce2_size"], 4)
        self.assertEqual(job["merkle_branch"], ["cc" * 32, "dd" * 32])
        self.assertEqual(job["coinb1"], "01000000")
        self.assertEqual(job["coinb2"], "ffffffff")

    def test_job_fields_stay_null_before_any_job(self) -> None:
        """No job received means no work-detail fields — never invented."""
        snapshot = _authorized_state().snapshot()["job"]
        for key in (
            "prevhash",
            "version",
            "nbits",
            "ntime",
            "extranonce1",
            "extranonce2_size",
            "merkle_branch",
            "coinb1",
            "coinb2",
        ):
            self.assertIsNone(snapshot[key], key)


if __name__ == "__main__":
    unittest.main()
