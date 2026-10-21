"""Focused bridge regressions. DiskPort is a test double, not OVID qualification.

Installed acceptance separately exercises the actual shared CompositionRoot port.
"""

import copy
from dataclasses import FrozenInstanceError
from pathlib import Path
import secrets
from types import SimpleNamespace
import tempfile
import threading
import time
import unittest

from al_haras.audit import AuditIntegrityError, HashChainAudit
from euclid.capabilities.empirical_state_bridge import (
    EmpiricalStateBridge,
    EmpiricalStateController,
    StateCommitUncertain,
    StateTransitionRequest,
)


class DiskPort:
    def __init__(self, path, audit):
        self.path, self.audit = path, audit
        self.fail_after_write = False

    def latest(self, kind):
        files = sorted(self.path.glob("*.json")) if self.path.exists() else []
        return SimpleNamespace(binding_id=files[-1].stem) if files else None

    def put(self, kind, payload, **kwargs):
        if self.audit.records[-1]["event"]["phase"] != "ADMITTED":
            raise RuntimeError("effect without durable admission")
        self.path.mkdir(exist_ok=True)
        name = f"{len(list(self.path.glob('*.json'))):08d}"
        (self.path / (name + ".json")).write_bytes(payload)
        if self.fail_after_write:
            raise OSError("test publication failure")
        return SimpleNamespace(binding_id=name)

    def read(self, binding_id):
        return (self.path / (binding_id + ".json")).read_bytes()


class EmpiricalHardening(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.token = secrets.token_urlsafe(32)
        self.audit = HashChainAudit(self.root / "audit/events.jsonl")
        self.port = DiskPort(self.root / "state", self.audit)
        self.bridge = self.make_bridge()

    def make_bridge(self, **changes):
        args = dict(
            authorizer=lambda req: req.caller_id == "operator"
            and secrets.compare_digest(req.operator_token, self.token),
            audit=self.audit,
            data_port=self.port,
        )
        args.update(changes)
        return EmpiricalStateBridge(**args)

    def request(self, **changes):
        args = dict(
            capability_id=self.bridge.APPROVED_CAPABILITY_ID,
            caller_id="operator",
            transition_type="UPDATE_RELIABILITY",
            state_payload={"domain": "atomic", "weight": 0.7},
            deadline_epoch=time.time() + 60,
            max_budget=1,
            operator_token=self.token,
        )
        args.update(changes)
        return StateTransitionRequest(**args)

    def test_no_configured_authority_fails_closed(self):
        self.assertFalse(EmpiricalStateBridge().dispatch(self.request())[0])

    def test_arbitrary_long_token_and_wrong_caller_refused(self):
        for changes in (
            {"operator_token": "x" * 100},
            {"caller_id": "other"},
            {"operator_token": ""},
        ):
            self.assertFalse(self.bridge.dispatch(self.request(**changes))[0])
        self.assertEqual(self.bridge.controller.state["version"], 1)
        self.assertEqual(self.audit.records, ())

    def test_authorizer_exception_refuses(self):
        def unavailable(req):
            raise OSError("test authority unavailable")

        self.assertFalse(self.make_bridge(authorizer=unavailable).dispatch(self.request())[0])

    def test_in_memory_audit_is_not_durable_authority(self):
        bridge = self.make_bridge(audit=HashChainAudit())
        self.assertEqual(bridge.dispatch(self.request())[2], "GOVERNANCE_UNAVAILABLE")

    def test_custody_is_required(self):
        bridge = self.make_bridge(data_port=None)
        self.assertEqual(bridge.dispatch(self.request())[2], "GOVERNANCE_UNAVAILABLE")

    def test_authorizer_observation_cannot_substitute_payload(self):
        def observe(req):
            req.state_payload["weight"] = 0.1
            return True

        bridge = self.make_bridge(authorizer=observe)
        bridge.dispatch(self.request())
        self.assertEqual(bridge.controller.state["reliability_weights"]["atomic"], 0.7)

    def test_commit_has_durable_admission_and_completion(self):
        ok, receipt, _ = self.bridge.dispatch(self.request())
        self.assertTrue(ok)
        self.assertEqual(
            [r["event"]["phase"] for r in self.audit.records], ["ADMITTED", "COMMITTED"]
        )
        self.assertEqual(self.bridge.audit_log, [receipt])
        self.assertNotIn(self.token, self.audit.path.read_text())
        with self.assertRaises(FrozenInstanceError):
            receipt.status = "changed"

    def test_audit_failure_before_execution_prevents_mutation(self):
        before = copy.deepcopy(self.bridge.controller.state)

        def unavailable(event):
            raise OSError("test admission disk failure")

        self.audit.append = unavailable
        with self.assertRaises(OSError):
            self.bridge.dispatch(self.request())
        self.assertEqual(self.bridge.controller.state, before)
        self.assertFalse(self.port.path.exists())

    def test_full_state_restored_after_partial_execution_failure(self):
        class PartialFailure(EmpiricalStateController):
            def apply(inner, req):
                inner.state["reliability_weights"]["atomic"] = 0.2
                inner.state["version"] = 999
                raise RuntimeError("test failure after partial mutation")

        bridge = self.make_bridge(controller=PartialFailure())
        before = copy.deepcopy(bridge.controller.state)
        self.assertEqual(bridge.dispatch(self.request())[2], "EXECUTION_FAILED_ROLLED_BACK")
        self.assertEqual(bridge.controller.state, before)
        self.assertEqual(
            [r["event"]["phase"] for r in self.audit.records], ["ADMITTED", "ROLLED_BACK"]
        )

    def test_reopen_restores_operational_state_and_durable_receipts(self):
        self.bridge.dispatch(self.request())
        reopened = self.make_bridge(audit=HashChainAudit(self.audit.path))
        self.assertEqual(reopened.controller.state, self.bridge.controller.state)
        self.assertEqual(reopened.audit_log, self.bridge.audit_log)
        detached = reopened.audit_log
        detached.clear()
        self.assertEqual(len(reopened.audit_log), 1)

    def test_uncertain_completion_never_reports_success_or_allows_retry(self):
        append = self.audit.append

        def failure(event):
            if event["phase"] == "COMMITTED":
                raise OSError("test completion disk failure")
            return append(event)

        self.audit.append = failure
        with self.assertRaises(StateCommitUncertain):
            self.bridge.dispatch(self.request())
        with self.assertRaises(StateCommitUncertain):
            self.bridge.dispatch(self.request())
        self.assertEqual(self.bridge.audit_log, [])
        with self.assertRaises(StateCommitUncertain):
            self.make_bridge(audit=HashChainAudit(self.audit.path))

    def test_store_publish_then_raise_is_uncertain_not_false_rollback(self):
        self.port.fail_after_write = True
        with self.assertRaises(StateCommitUncertain):
            self.bridge.dispatch(self.request())
        with self.assertRaises(StateCommitUncertain):
            self.make_bridge()

    def test_stale_writer_refused(self):
        stale = self.make_bridge()
        self.bridge.dispatch(self.request())
        with self.assertRaises(StateCommitUncertain):
            stale.dispatch(self.request())

    def test_invalid_numeric_weights_never_persist(self):
        for weight in (True, "0.5", float("nan"), float("inf"), -0.1, 1.1):
            with self.subTest(weight=weight):
                req = self.request(state_payload={"domain": "atomic", "weight": weight})
                self.assertFalse(self.bridge.dispatch(req)[0])
        self.assertEqual(self.bridge.controller.state["version"], 1)
        self.assertFalse(self.port.path.exists())

    def test_invalid_budget_deadline_and_capability(self):
        for changes in (
            {"max_budget": 0},
            {"max_budget": True},
            {"max_budget": "10"},
            {"deadline_epoch": time.time() - 1},
            {"deadline_epoch": float("nan")},
            {"deadline_epoch": True},
            {"capability_id": "unapproved"},
        ):
            self.assertFalse(self.bridge.dispatch(self.request(**changes))[0])
        self.assertEqual(self.audit.records, ())

    def test_no_prior_memories_or_identity_in_state_schema(self):
        with self.assertRaises(ValueError):
            EmpiricalStateController(
                {"version": 1, "reliability_weights": {}, "identity": "past-self"}
            )

    def test_custody_cannot_be_adopted_by_another_owner(self):
        self.bridge.dispatch(self.request())
        with self.assertRaises(ValueError):
            self.make_bridge(owner_id="another-owner")

    def test_deadline_expires_during_custody_without_false_success(self):
        original = self.port.put

        def delayed(*args, **kwargs):
            binding = original(*args, **kwargs)
            time.sleep(0.03)
            return binding

        self.port.put = delayed
        with self.assertRaises(StateCommitUncertain):
            self.bridge.dispatch(self.request(deadline_epoch=time.time() + 0.02))

    def test_corrupt_audit_refuses_reopen(self):
        self.bridge.dispatch(self.request())
        text = self.audit.path.read_text().replace('"COMMITTED"', '"CORRUPTED"')
        self.audit.path.write_text(text)
        with self.assertRaises(AuditIntegrityError):
            HashChainAudit(self.audit.path)

    def test_concurrent_calls_are_serialized(self):
        outcomes = []

        def dispatch():
            outcomes.append(self.bridge.dispatch(self.request())[0])

        workers = [threading.Thread(target=dispatch) for _ in range(8)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(10)
        self.assertEqual(outcomes, [True] * 8)
        self.assertEqual(self.bridge.controller.state["version"], 9)
        self.assertEqual(len(self.bridge.audit_log), 8)


if __name__ == "__main__":
    unittest.main()
