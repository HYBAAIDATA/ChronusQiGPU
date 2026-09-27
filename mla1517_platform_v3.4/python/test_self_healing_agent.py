from __future__ import annotations

import unittest

from mla1517.mining.self_healing_agent import (
    NonBlockingRecoveryQueue,
    RecoveryBackpressure,
    RecoveryCommand,
    SelfHealingAgent,
)
from mla1517.mining.toe_context import TOEContextBuilder, TOEContextUnavailable


def make_context(job_id: str = "job-1"):
    return (
        TOEContextBuilder()
        .with_job({"job_id": job_id, "prevhash": "00" * 32})
        .with_hardware_state(b"h" * 64)
        .with_coordinates(lane_id=1, node_id=2, sequence=1, watermark=1)
        .with_telemetry({"source": "observed-test-feed"})
        .build()
    )


def telemetry(**updates):
    result = {
        "kernel_latency_ms": 10.0,
        "kernel_latency_bound_ms": 100.0,
        "temperature_c": 55.0,
        "thermal_limit_c": 85.0,
        "stratum_state": "READY",
        "hardware_status": "READY",
        "new_job_observed": False,
    }
    result.update(updates)
    return result


class SelfHealingAgentTests(unittest.TestCase):
    def test_new_job_severs_and_flushes_before_dispatch(self):
        plan = SelfHealingAgent().observe(
            context=make_context(),
            telemetry=telemetry(new_job_observed=True, stratum_state="NEW_JOB"),
            observed_at_ns=100,
            current_job_id="job-1",
        )
        self.assertEqual(
            [action.command for action in plan.actions],
            [RecoveryCommand.SEVER_LANE, RecoveryCommand.FLUSH_LANE],
        )
        self.assertTrue(plan.non_blocking)

    def test_hang_risk_isolates_flushes_and_restarts_lane(self):
        plan = SelfHealingAgent().observe(
            context=make_context(),
            telemetry=telemetry(kernel_latency_ms=250.0, hardware_status="HANG_RISK"),
            observed_at_ns=101,
        )
        self.assertEqual(
            [action.command for action in plan.actions],
            [
                RecoveryCommand.SEVER_LANE,
                RecoveryCommand.FLUSH_LANE,
                RecoveryCommand.RESTART_LANE,
            ],
        )

    def test_cassini_failure_quarantines_and_recovers_cursor(self):
        plan = SelfHealingAgent().observe(
            context=make_context(),
            telemetry=telemetry(),
            observed_at_ns=102,
            record_id="record-1",
            cassini_error="seal mismatch",
        )
        self.assertEqual(
            [action.command for action in plan.actions],
            [
                RecoveryCommand.QUARANTINE_RECORD,
                RecoveryCommand.FLUSH_PERSISTENCE_RING,
                RecoveryCommand.RESET_CURSOR,
            ],
        )
        self.assertFalse(plan.actions[1].parameters["drop_records"])

    def test_backpressure_is_explicit_and_non_dropping(self):
        plan = SelfHealingAgent().observe(
            context=make_context(),
            telemetry=telemetry(),
            observed_at_ns=103,
            queue_backpressure=True,
        )
        self.assertEqual(plan.actions[0].command, RecoveryCommand.APPLY_BACKPRESSURE)
        self.assertFalse(plan.actions[0].parameters["drop_records"])
        self.assertEqual(plan.actions[-1].command, RecoveryCommand.RESET_CURSOR)

    def test_normal_observation_holds_and_missing_record_fails_closed(self):
        agent = SelfHealingAgent()
        plan = agent.observe(context=make_context(), telemetry=telemetry(), observed_at_ns=104)
        self.assertEqual(plan.actions[0].command, RecoveryCommand.HOLD)
        with self.assertRaises(TOEContextUnavailable):
            agent.observe(
                context=make_context(),
                telemetry=telemetry(),
                observed_at_ns=105,
                cassini_error="seal mismatch",
            )

    def test_recovery_queue_never_waits_or_drops(self):
        queue = NonBlockingRecoveryQueue(max_pending=1)
        agent = SelfHealingAgent()
        plan = agent.observe(context=make_context(), telemetry=telemetry(), observed_at_ns=106)
        queue.submit(plan)
        with self.assertRaises(RecoveryBackpressure):
            queue.submit(plan)
        self.assertIs(queue.receive(), plan)


if __name__ == "__main__":
    unittest.main()
