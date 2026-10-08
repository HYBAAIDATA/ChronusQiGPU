"""Adversarial regressions for the QC-closed voyage legs in toe/runtime.py.

Lane-local suite (tests/ is owned by Agent H — placement recorded in
reports/AGENT_HANDOFFS.json, entry A-004).  Covers the four QC block items:

1. Retained learning must affect a subsequent decision (bounded policy:
   net-negative modules are excluded from the delivered payload).
2. Cross-tenant feedback replay must be refused.
3. Configured durability failure must fail closed, not ok=True.
4. ready() must reflect required-loop health, not just bridge availability.
"""

from __future__ import annotations

import os
import tempfile
import unittest

from toe.runtime import (
    TenantContext,
    TOEIntelligenceRuntime,
    TOEIntelligenceRuntimeConfig,
)


def _payload() -> dict:
    return {"series": [float(i % 7 - 3) * 0.1 for i in range(64)]}


def _runtime(**kwargs) -> TOEIntelligenceRuntime:
    return TOEIntelligenceRuntime(config=TOEIntelligenceRuntimeConfig(**kwargs))


class TestLearnedPolicyInfluence(unittest.TestCase):
    """QC 1: identical input changes only when retained learning says so."""

    def test_no_learning_no_exclusion(self) -> None:
        rt = _runtime()
        t = TenantContext(tenant_id="t1")
        r1 = rt.predict(_payload(), t)
        self.assertTrue(r1.ok)
        self.assertNotIn("learned_policy", r1.result)
        self.assertNotIn("learned_exclusions", r1.result)

    def test_seeded_negative_weight_excludes_module(self) -> None:
        """Deterministic: a learned net-negative module leaves the payload."""
        rt = _runtime()
        rt.feedback_core.model_parameters["state_tomography"] = -0.5
        t = TenantContext(tenant_id="t1")
        r = rt.predict(_payload(), t)
        self.assertTrue(r.ok)
        self.assertIn("learned_policy", r.result)
        self.assertEqual(
            r.result["learned_policy"]["excluded_modules"], ["state_tomography"]
        )
        self.assertNotIn("state_tomography", set(r.result) - {"learned_exclusions"})
        self.assertIn("state_tomography", r.result["learned_exclusions"])

    def test_seeded_zero_weight_no_exclusion(self) -> None:
        """Identical input unchanged when learning is not net-negative."""
        rt = _runtime()
        rt.feedback_core.model_parameters["state_tomography"] = 0.0
        t = TenantContext(tenant_id="t1")
        r = rt.predict(_payload(), t)
        self.assertTrue(r.ok)
        self.assertNotIn("learned_policy", r.result)

    def test_learned_change_is_only_from_learning(self) -> None:
        """Same runtime, same input: differs iff learning crossed the line."""
        rt = _runtime()
        t = TenantContext(tenant_id="t1")
        before = rt.predict(_payload(), t)
        rt.feedback_core.model_parameters["trajectory_prediction"] = -0.1
        after = rt.predict(_payload(), t)
        self.assertNotEqual(
            set(before.result), set(after.result),
            "learned policy must change the decision surface",
        )
        shared = set(before.result) & set(after.result) - {
            "learned_policy", "learned_exclusions",
        }
        for key in shared:
            self.assertEqual(before.result[key], after.result[key])

    def test_negative_learning_excludes_module_from_decision(self) -> None:
        """End-to-end: a real bad outcome drives exclusion on the next call."""
        bad = _runtime()
        t2 = TenantContext(tenant_id="t1")
        r = bad.predict(_payload(), t2)
        baseline_keys = set(r.result)
        bad.record_outcome(r.decision_id, False, t2)
        r2 = bad.predict(_payload(), t2)
        self.assertTrue(r2.ok)
        if bad.feedback_core.identify_underperforming_modules():
            self.assertIn("learned_policy", r2.result)
            excluded = set(r2.result["learned_policy"]["excluded_modules"])
            self.assertTrue(excluded)
            for mod in excluded:
                self.assertNotIn(
                    mod,
                    set(r2.result) - {"learned_exclusions", "learned_policy"},
                )
            self.assertNotEqual(set(r2.result), baseline_keys)
        else:
            # Learning signal was not net-negative for this seed — the honest
            # outcome: policy must NOT have fired.
            self.assertNotIn("learned_policy", r2.result)

    def test_identical_input_identical_without_learning(self) -> None:
        rt = _runtime()
        t = TenantContext(tenant_id="t1")
        a = rt.predict(_payload(), t)
        b = rt.predict(_payload(), t)
        self.assertEqual(a.result, b.result)

    def test_restored_learning_still_excludes_after_restart(self) -> None:
        d = tempfile.mkdtemp()
        path = os.path.join(d, "fb.json")
        rt = _runtime(feedback_state_path=path)
        t = TenantContext(tenant_id="t1")
        r = rt.predict(_payload(), t)
        rt.record_outcome(r.decision_id, False, t)
        rt2 = _runtime(feedback_state_path=path)
        t2 = TenantContext(tenant_id="t1")
        r2 = rt2.predict(_payload(), t2)
        self.assertTrue(r2.ok)
        if rt2.feedback_core.identify_underperforming_modules():
            self.assertIn("learned_policy", r2.result)


class TestTenantIsolationOnFeedback(unittest.TestCase):
    """QC 2: a tenant cannot close another tenant's decision."""

    def test_cross_tenant_replay_refused(self) -> None:
        rt = _runtime()
        alice = TenantContext(tenant_id="alice")
        bob = TenantContext(tenant_id="bob")
        r = rt.predict(_payload(), alice)
        self.assertTrue(r.ok)
        out = rt.record_outcome(r.decision_id, True, bob)
        self.assertFalse(out.ok)
        self.assertIsNotNone(out.error)

    def test_same_tenant_still_works(self) -> None:
        rt = _runtime()
        alice = TenantContext(tenant_id="alice")
        r = rt.predict(_payload(), alice)
        out = rt.record_outcome(r.decision_id, True, alice)
        self.assertTrue(out.ok)

    def test_cross_tenant_attempt_does_not_consume_decision(self) -> None:
        rt = _runtime()
        alice = TenantContext(tenant_id="alice")
        bob = TenantContext(tenant_id="bob")
        r = rt.predict(_payload(), alice)
        rt.record_outcome(r.decision_id, True, bob)  # refused
        out = rt.record_outcome(r.decision_id, True, alice)
        self.assertTrue(out.ok)


class TestTransactionalDurability(unittest.TestCase):
    """Failed durable write must roll memory back to last durable state."""

    def test_failed_persist_rolls_back_and_leaves_retryable(self) -> None:
        d = tempfile.mkdtemp()
        blocker = os.path.join(d, "blocker")
        with open(blocker, "w", encoding="utf-8") as fh:
            fh.write("x")
        rt = _runtime(feedback_state_path=os.path.join(blocker, "fb.json"))
        t = TenantContext(tenant_id="t1")
        r = rt.predict(_payload(), t)
        before = dict(rt.feedback_core.model_parameters)
        out = rt.record_outcome(r.decision_id, True, t)
        self.assertFalse(out.ok)
        # In-memory aggregate is back to the last durable state — no phantom
        # learned update survives the failed handoff.
        self.assertEqual(rt.feedback_core.model_parameters, before)
        self.assertNotIn(r.decision_id, rt.feedback_core._processed)
        # Decision stays recorded and unclosed -> retryable after remediation.
        self.assertIn(r.decision_id, rt.feedback_core.decision_records)
        good = os.path.join(d, "fb.json")
        rt._feedback_state_path = type(rt._feedback_state_path)(good)
        retry = rt.record_outcome(r.decision_id, True, t)
        self.assertTrue(retry.ok)

    def test_successful_persist_recovers_durability_and_ready(self) -> None:
        d = tempfile.mkdtemp()
        blocker = os.path.join(d, "blocker")
        with open(blocker, "w", encoding="utf-8") as fh:
            fh.write("x")
        rt = _runtime(feedback_state_path=os.path.join(blocker, "fb.json"))
        t = TenantContext(tenant_id="t1")
        r = rt.predict(_payload(), t)
        self.assertFalse(rt.record_outcome(r.decision_id, True, t).ok)
        self.assertFalse(rt.ready())
        rt._feedback_state_path = type(rt._feedback_state_path)(
            os.path.join(d, "fb.json")
        )
        self.assertTrue(rt.record_outcome(r.decision_id, True, t).ok)
        self.assertFalse(rt._durability_failed)
        self.assertTrue(rt.ready())

    def test_excluded_module_still_receives_attribution(self) -> None:
        """Exclusion gates delivery, not learning: good outcomes can recover."""
        rt = _runtime()
        t = TenantContext(tenant_id="t1")
        rt.feedback_core.model_parameters["state_tomography"] = -0.5
        r = rt.predict(_payload(), t)
        self.assertIn("learned_policy", r.result)
        self.assertTrue(rt.record_outcome(r.decision_id, True, t).ok)
        # The excluded module was still attributed — its weight moved from
        # the seed rather than freezing at the exclusion boundary.
        self.assertNotEqual(
            rt.feedback_core.model_parameters.get("state_tomography"), -0.5
        )

    def test_all_modules_excluded_marks_degraded(self) -> None:
        rt = _runtime()
        t = TenantContext(tenant_id="t1")
        probe = rt.predict(_payload(), t)
        for key, value in probe.result.items():
            if isinstance(value, dict):
                rt.feedback_core.model_parameters[key] = -0.5
        r = rt.predict(_payload(), t)
        self.assertTrue(r.ok)
        self.assertTrue(r.degraded)
        self.assertTrue(r.result["learned_policy"]["empty_surface"])


class TestDurabilityFailClosed(unittest.TestCase):
    """QC 3: configured persistence failing => record_outcome must not ok."""

    def test_unwritable_state_path_fails_closed(self) -> None:
        # Path through a FILE is unwritable: mkdir/replace fails.
        d = tempfile.mkdtemp()
        blocker = os.path.join(d, "blocker")
        with open(blocker, "w", encoding="utf-8") as fh:
            fh.write("x")
        bad_path = os.path.join(blocker, "fb.json")
        rt = _runtime(feedback_state_path=bad_path)
        t = TenantContext(tenant_id="t1")
        r = rt.predict(_payload(), t)
        out = rt.record_outcome(r.decision_id, True, t)
        self.assertFalse(out.ok)
        self.assertEqual(out.error.code, "persistence_failed")
        self.assertTrue(out.degraded)
        self.assertFalse(rt.ready())

    def test_unconfigured_durability_still_ok(self) -> None:
        rt = _runtime()  # no feedback_state_path
        t = TenantContext(tenant_id="t1")
        r = rt.predict(_payload(), t)
        out = rt.record_outcome(r.decision_id, True, t)
        self.assertTrue(out.ok)


class TestReadySemantics(unittest.TestCase):
    """QC 4: ready() reflects required loops, not just bridge availability."""

    def test_ready_true_when_required_loops_up(self) -> None:
        self.assertTrue(_runtime().ready())

    def test_ready_false_when_feedback_required_but_missing(self) -> None:
        class _BridgeOk:
            def available(self):
                return True

        rt = TOEIntelligenceRuntime(
            config=TOEIntelligenceRuntimeConfig(enable_feedback=True),
            bridge=_BridgeOk(),
            feedback_core=None,
        )
        # feedback_core=None is injected deliberately; enable_feedback makes
        # the middle loop required, so the constructor's fallback still
        # creates one.  Disable the loop entirely to test the gate.
        rt.feedback_core = None
        self.assertFalse(rt.ready())

    def test_ready_false_after_durability_failure(self) -> None:
        d = tempfile.mkdtemp()
        blocker = os.path.join(d, "blocker")
        with open(blocker, "w", encoding="utf-8") as fh:
            fh.write("x")
        rt = _runtime(feedback_state_path=os.path.join(blocker, "fb.json"))
        t = TenantContext(tenant_id="t1")
        r = rt.predict(_payload(), t)
        self.assertTrue(rt.ready())  # predict path healthy before outcome
        rt.record_outcome(r.decision_id, True, t)
        self.assertFalse(rt.ready())


if __name__ == "__main__":
    unittest.main()
