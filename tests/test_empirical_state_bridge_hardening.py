"""Focused bridge regressions. DiskPort is a test double, not OVID qualification.

Installed acceptance separately exercises the actual shared CompositionRoot port.
"""

import copy
import hashlib
import json
import subprocess
import sys
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


from euclid.capabilities.empirical_recovery import (
    PublicationRecoveryRequest,
    reconcile_publication,
)


class DiskPort:
    def __init__(self, path, audit):
        self.path, self.audit = path, audit
        self.fail_after_write = False

    def latest(self, kind):
        files = sorted(self.path.glob("*.json")) if self.path.exists() else []
        return SimpleNamespace(binding_id=files[-1].stem) if files else None

    def put(self, kind, payload, **kwargs):
        if self.audit.records[-1]["event"]["phase"] != "PREPARED":
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
            [r["event"]["phase"] for r in self.audit.records],
            ["ADMITTED", "PREPARED", "COMMITTED"],
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
            [r["event"]["phase"] for r in self.audit.records],
            ["ADMITTED", "ROLLED_BACK"],
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

    def recovery_request(self, **changes):
        binding = self.port.latest(self.bridge.STATE_KIND)
        args = dict(
            owner_id="host",
            binding_id=binding.binding_id,
            envelope_sha256=hashlib.sha256(self.port.read(binding.binding_id)).hexdigest(),
            caller_id="recovery-operator",
            operator_token=self.token,
            deadline_epoch=time.time() + 60,
        )
        args.update(changes)
        return PublicationRecoveryRequest(**args)

    def recovery(self, req=None, **changes):
        args = dict(
            recovery_authorizer=lambda req: req.caller_id == "recovery-operator"
            and secrets.compare_digest(req.operator_token, self.token),
            audit=HashChainAudit(self.audit.path),
            data_port=self.port,
        )
        args.update(changes)
        return reconcile_publication(req or self.recovery_request(), **args)

    def orphan(self):
        self.port.fail_after_write = True
        with self.assertRaises(StateCommitUncertain):
            self.bridge.dispatch(self.request())
        self.port.fail_after_write = False

    def test_prepared_failure_restores_local_state_without_custody_effect(self):
        append = self.audit.append
        before = copy.deepcopy(self.bridge.controller.state)

        def failure(event):
            if event["phase"] == "PREPARED":
                raise OSError("intent fsync failure")
            return append(event)

        self.audit.append = failure
        with self.assertRaises(StateCommitUncertain):
            self.bridge.dispatch(self.request())
        self.assertEqual(self.bridge.controller.state, before)
        self.assertFalse(self.port.path.exists())
        with self.assertRaises(StateCommitUncertain):
            self.bridge.dispatch(self.request())

    def test_recover_publish_then_raise_and_reopen(self):
        self.orphan()
        receipt = self.recovery()
        reopened = self.make_bridge(audit=HashChainAudit(self.audit.path))
        self.assertEqual(reopened.controller.state["reliability_weights"]["atomic"], 0.7)
        self.assertEqual(reopened.audit_log, [receipt])
        self.assertEqual(len(list(self.port.path.glob("*.json"))), 1)
        self.assertNotIn(self.token, self.audit.path.read_text())
        # Recovery never silently un-quarantines a running instance.
        with self.assertRaises(StateCommitUncertain):
            self.bridge.dispatch(self.request())

    def test_recovery_independent_authority_is_required(self):
        self.orphan()
        for authorizer in (None, lambda req: False, lambda req: 1):
            with self.assertRaises(PermissionError):
                self.recovery(recovery_authorizer=authorizer)
        for changes in ({"operator_token": "x" * 100}, {"caller_id": "operator"}):
            with self.assertRaises(PermissionError):
                self.recovery(self.recovery_request(**changes))

        def failed(req):
            raise OSError("authority unavailable")

        with self.assertRaises(PermissionError):
            self.recovery(recovery_authorizer=failed)
        self.assertEqual(len(self.audit.records), 2)

    def test_recovery_deadline_and_shape_validation(self):
        self.orphan()
        for changes in (
            {"deadline_epoch": False},
            {"deadline_epoch": float("nan")},
            {"deadline_epoch": time.time() - 1},
            {"envelope_sha256": "bad"},
            {"operator_token": ""},
            {"caller_id": ""},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.recovery(self.recovery_request(**changes))
        with self.assertRaises(ValueError):
            reconcile_publication({})

    def test_recovery_memory_only_audit_refused(self):
        self.orphan()
        with self.assertRaises(PermissionError):
            self.recovery(audit=HashChainAudit())

    def test_recovery_stale_target_refused(self):
        self.orphan()
        with self.assertRaises(StateCommitUncertain):
            self.recovery(self.recovery_request(binding_id="stale"))

    def test_recovery_hash_and_foreign_owner_refused(self):
        self.orphan()
        with self.assertRaises(StateCommitUncertain):
            self.recovery(self.recovery_request(envelope_sha256="0" * 64))
        with self.assertRaises(ValueError):
            self.recovery(self.recovery_request(owner_id="other-owner"))

    def test_recovery_tampered_state_even_with_recomputed_request_hash_refused(self):
        self.orphan()
        path = next(self.port.path.glob("*.json"))
        envelope = json.loads(path.read_bytes())
        envelope["state"]["reliability_weights"]["atomic"] = 0.1
        envelope["receipt"]["new_state_hash"] = hashlib.sha256(
            json.dumps(envelope["state"], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        path.write_text(json.dumps(envelope))
        with self.assertRaises(StateCommitUncertain):
            self.recovery()

    def test_recovery_legacy_orphan_without_prepared_intent_refused(self):
        self.orphan()
        legacy = HashChainAudit(self.root / "legacy.jsonl")
        legacy.append(self.audit.records[0]["event"])
        with self.assertRaises(StateCommitUncertain):
            self.recovery(audit=legacy)

    def test_recovery_duplicate_intent_and_rolled_back_refused(self):
        self.orphan()
        intent = self.audit.records[-1]["event"]
        for extra in (intent, {**intent, "phase": "ROLLED_BACK"}):
            spool = HashChainAudit(self.root / (secrets.token_hex(4) + ".jsonl"))
            for record in self.audit.records:
                spool.append(record["event"])
            spool.append(extra)
            with self.assertRaises(StateCommitUncertain):
                self.recovery(audit=spool)

    def test_recovery_requires_prior_committed_lineage(self):
        self.bridge.dispatch(self.request())
        self.orphan()
        receipt = self.recovery()
        self.assertEqual(self.make_bridge().controller.state["version"], 3)
        self.assertEqual(len(self.make_bridge().audit_log), 2)
        self.assertEqual(receipt.budget_consumed, 1)

    def test_recovery_missing_prior_completion_refused(self):
        self.bridge.dispatch(self.request())
        self.orphan()
        spool = HashChainAudit(self.root / "missing-prior.jsonl")
        for record in self.audit.records:
            if record["event"]["phase"] != "COMMITTED":
                spool.append(record["event"])
        with self.assertRaises(StateCommitUncertain):
            self.recovery(audit=spool)

    def test_recovery_append_failure_remains_quarantined(self):
        self.orphan()

        def failed(event):
            raise OSError("recovery disk failure")

        self.audit.append = failed
        with self.assertRaises(StateCommitUncertain):
            self.recovery(audit=self.audit)
        with self.assertRaises(StateCommitUncertain):
            self.make_bridge(audit=HashChainAudit(self.audit.path))

    def test_recovery_completion_failure_retry_is_idempotent(self):
        self.orphan()
        append = self.audit.append

        def append_then_fail(event):
            result = append(event)
            if event["phase"] == "COMMITTED":
                raise OSError("completion fsynced then caller lost response")
            return result

        self.audit.append = append_then_fail
        with self.assertRaises(StateCommitUncertain):
            self.recovery(audit=self.audit)
        receipt = self.recovery()
        self.assertEqual(self.recovery(), receipt)
        self.assertEqual(len(self.make_bridge().audit_log), 1)
        self.assertEqual(len(list(self.port.path.glob("*.json"))), 1)
        with self.assertRaises(PermissionError):
            self.recovery(recovery_authorizer=None)

    def test_recovery_completion_failure_before_write_can_retry(self):
        self.orphan()
        append = self.audit.append

        def fail_before(event):
            if event["phase"] == "COMMITTED":
                raise OSError("completion failed before append")
            return append(event)

        self.audit.append = fail_before
        with self.assertRaises(StateCommitUncertain):
            self.recovery(audit=self.audit)
        with self.assertRaises(StateCommitUncertain):
            self.make_bridge(audit=HashChainAudit(self.audit.path))
        self.recovery()
        self.assertEqual(len(self.make_bridge().audit_log), 1)

    def test_restore_receipt_cannot_be_copied_to_a_new_binding(self):
        self.bridge.dispatch(self.request())
        original = next(self.port.path.glob("*.json"))
        (self.port.path / "99999999.json").write_bytes(original.read_bytes())
        with self.assertRaises(StateCommitUncertain):
            self.make_bridge()

    def test_recovery_custody_changes_after_admission_refused(self):
        self.orphan()
        append = self.audit.append

        def change_after(event):
            result = append(event)
            if event["phase"] == "RECOVERY_ADMITTED":
                (self.port.path / "99999999.json").write_bytes(b"{}")
            return result

        self.audit.append = change_after
        with self.assertRaises(StateCommitUncertain):
            self.recovery(audit=self.audit)
        self.assertFalse(any(r["event"]["phase"] == "COMMITTED" for r in self.audit.records))

    def test_recovery_corrupt_audit_refused(self):
        self.orphan()
        self.audit.path.write_text(self.audit.path.read_text().replace('"PREPARED"', '"FAKE"'))
        with self.assertRaises(AuditIntegrityError):
            self.recovery()

    def test_cross_process_orphan_recovery_preserves_operational_state(self):
        # Real durable audit + DiskPort test double; explicitly not native OVID,
        # package qualification, canonical runtime or a deployed authority test.
        bootstrap = r"""
import importlib.util, sys, pathlib, json, hashlib, time, os
root, spool, action = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3]
for name, relative in [
 ('al_haras.audit', 'al_haras/audit.py'),
 ('euclid.capabilities.empirical_state_bridge', 'euclid/capabilities/empirical_state_bridge.py'),
 ('euclid.capabilities.empirical_recovery', 'euclid/capabilities/empirical_recovery.py'),
 ('bridge_tests', 'tests/test_empirical_state_bridge_hardening.py')]:
 path = pathlib.Path(sys.argv[4]) if name == 'bridge_tests' else root/relative
 if not path.exists():
  module=__import__(name, fromlist=['*']); continue
 spec=importlib.util.spec_from_file_location(name, path)
 module=importlib.util.module_from_spec(spec); sys.modules[name]=module; spec.loader.exec_module(module)
from al_haras.audit import HashChainAudit
from euclid.capabilities.empirical_state_bridge import EmpiricalStateBridge, StateTransitionRequest
from euclid.capabilities.empirical_recovery import PublicationRecoveryRequest, reconcile_publication
audit=HashChainAudit(spool/'audit.jsonl'); port=module.DiskPort(spool/'state',audit)
if action=='interrupt':
 def stop_after_write(kind, payload, **kwargs):
  module.DiskPort.put(port, kind, payload, **kwargs)
  os._exit(23)  # No completion append, destructor or orderly close.
 port.put=stop_after_write
 bridge=EmpiricalStateBridge(audit=audit,data_port=port,authorizer=lambda req: True)
 bridge.dispatch(StateTransitionRequest(bridge.APPROVED_CAPABILITY_ID,'unit-operator','UPDATE_RELIABILITY',{'domain':'atomic','weight':0.73},time.time()+60,1,'unit-only'))
else:
 binding=port.latest(EmpiricalStateBridge.STATE_KIND)
 raw=port.read(binding.binding_id)
 req=PublicationRecoveryRequest('host',binding.binding_id,hashlib.sha256(raw).hexdigest(),'unit-recovery','unit-only',time.time()+60)
 reconcile_publication(req,audit=audit,data_port=port,recovery_authorizer=lambda req: req.caller_id=='unit-recovery')
 bridge=EmpiricalStateBridge(audit=HashChainAudit(spool/'audit.jsonl'),data_port=port)
 print(json.dumps({'version':bridge.controller.state['version'],'weight':bridge.controller.state['reliability_weights']['atomic'],'receipts':len(bridge.audit_log)}))
"""
        root = Path(__file__).resolve().parents[1]
        args = [sys.executable, "-I"] + (["-O"] if sys.flags.optimize else [])
        args += ["-c", bootstrap, str(root), str(self.root)]
        stopped = subprocess.run(
            [*args, "interrupt", str(Path(__file__).resolve())], capture_output=True, text=True
        )
        self.assertEqual(stopped.returncode, 23, stopped.stderr)
        recovered = subprocess.run(
            [*args, "recover", str(Path(__file__).resolve())], capture_output=True, text=True
        )
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        self.assertEqual(
            json.loads(recovered.stdout), {"version": 2, "weight": 0.73, "receipts": 1}
        )


if __name__ == "__main__":
    unittest.main()
