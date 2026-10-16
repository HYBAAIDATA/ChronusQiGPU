"""Real local ledger, canonical runtime/AL HARAS and shared native handler.

Local test subscription issuer is not independent authority/certification.
No repair execution is authorized by the observation-only capability.
"""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from Intelligence.isolated_repair import RepairLearningLedger, IsolatedRepairExecutor, RepairEvidencePersistenceError
from Intelligence.repair_learning_capability import register_repair_learning_capability
from Intelligence.capability_fabric import CapabilityRegistry, ExecutionProfile, CapabilityRegistrationError
from al_haras import ALHaras, GuardianPolicy, HashChainAudit, SubscriptionAuthority, SubscriptionClaims
from euclid import EuclidRuntime


def record(ledger, **changes):
    values = dict(problem_signature="sig", issue_type="ast", target_path="module.py",
                  baseline_sha256="a" * 64, candidate_sha256="b" * 64,
                  status="COMMITTED", pre_probe_reproduced=True,
                  post_probe_cleared=True, validator_passed=True, duration_seconds=0.1)
    values.update(changes)
    return ledger.record_outcome(**values)


class LedgerRegression(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "outcomes.json"
        self.ledger = RepairLearningLedger(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_repeated_load_does_not_inflate_counts(self):
        record(self.ledger)
        other = RepairLearningLedger(self.path)
        other.load(); other.load()
        self.assertEqual(other.outcome_statistics("ast", "sig")["sample_count"], 1)

    def test_empty_population_is_not_empirical_half_success(self):
        stats = self.ledger.outcome_statistics("ast", "sig")
        self.assertIsNone(stats["empirical_success_rate"])
        self.assertEqual(stats["evidence_class"], "NO_OBSERVATIONS")
        self.assertEqual(self.ledger.get_success_rate("ast", "sig"), 0.5)  # legacy prior only

    def test_failed_outcome_retained_and_not_committed(self):
        record(self.ledger)
        record(self.ledger, status="ROLLED_BACK", post_probe_cleared=False)
        self.assertEqual(self.ledger.outcome_statistics("ast", "sig")["empirical_success_rate"], 0.5)
        self.assertEqual(len(json.loads(self.path.read_text())), 2)

    def test_invalid_committed_evidence_refused(self):
        for field in ("pre_probe_reproduced", "post_probe_cleared", "validator_passed"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                record(self.ledger, **{field: False})
        self.assertFalse(self.path.exists())

    def test_storage_failure_is_not_acknowledged(self):
        record(self.ledger); before = self.path.read_bytes()
        with patch("Intelligence.isolated_repair.os.replace", side_effect=OSError("injected publication failure")):
            with self.assertRaises(OSError): record(self.ledger)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.ledger.outcome_statistics("ast", "sig")["sample_count"], 1)
        self.assertEqual(list(self.path.parent.glob(".repair-outcomes-*")), [])

    def test_corrupt_file_fails_without_erasing_current_state(self):
        record(self.ledger); self.path.write_text("not JSON")
        with self.assertRaises(ValueError): self.ledger.load()
        self.assertEqual(self.ledger.outcome_statistics("ast", "sig")["sample_count"], 1)

    def test_duplicate_record_identity_rejected(self):
        record(self.ledger); data = json.loads(self.path.read_text())
        self.path.write_text(json.dumps(data * 2))
        with self.assertRaises(ValueError): self.ledger.load()

    def test_strategy_key_cannot_collide_via_colons(self):
        record(self.ledger, issue_type="a:b", problem_signature="c")
        self.assertEqual(self.ledger.outcome_statistics("a", "b:c")["sample_count"], 0)

    def test_public_default_token_has_no_authority_and_is_not_logged(self):
        target = self.path.parent / "module.py"; target.write_text("broken = True\n")
        executor = IsolatedRepairExecutor(self.path.parent)
        called = []
        receipt = executor.execute_closed_loop_repair(target_file=target,
            replacement_code="broken = False\n", defect_probe=lambda p: called.append(p),
            validator_fn=lambda *a: True,
            authorization_token="INTERNAL_RESEARCH_AUTONOMOUS_OPERATOR")
        self.assertEqual(receipt.status, "REJECTED_UNAUTHORIZED")
        self.assertNotIn("INTERNAL_RESEARCH", receipt.reason)
        self.assertEqual(called, [])
        self.assertEqual(target.read_text(), "broken = True\n")

    def test_explicit_host_authorization_still_executes_real_local_repair(self):
        target = self.path.parent / "module.py"
        target.write_text("broken = True\n")
        executor = IsolatedRepairExecutor(self.path.parent, learning_ledger=self.ledger,
                                          authorized_tokens=["host-configured-test-only"])
        receipt = executor.execute_closed_loop_repair(
            target_file=target, replacement_code="broken = False\n",
            defect_probe=lambda path: "True" in path.read_text(),
            validator_fn=lambda old, new, path: old != new and path.read_text() == "broken = False\n",
            authorization_token="host-configured-test-only", issue_type="ast", problem_signature="sig")
        self.assertEqual(receipt.status, "COMMITTED")
        self.assertEqual(target.read_text(), "broken = False\n")
        self.assertEqual(self.ledger.outcome_statistics("ast", "sig")["sample_count"], 1)
        self.assertTrue(self.path.exists())

    def test_outcome_storage_failure_recovers_actual_published_source(self):
        target = self.path.parent / "module.py"
        target.write_text("broken = True\n")
        blocker = self.path.parent / "blocked"; blocker.write_text("not a directory")
        ledger = RepairLearningLedger(blocker / "ledger.json")
        executor = IsolatedRepairExecutor(self.path.parent, learning_ledger=ledger,
                                          authorized_tokens=["host-configured-test-only"])
        with self.assertRaises(RepairEvidencePersistenceError) as caught:
            executor.execute_closed_loop_repair(
                target_file=target, replacement_code="broken = False\n",
                defect_probe=lambda path: "True" in path.read_text(),
                validator_fn=lambda *args: True,
                authorization_token="host-configured-test-only")
        self.assertTrue(caught.exception.source_restored)
        self.assertEqual(target.read_text(), "broken = True\n")
        self.assertEqual(executor.get_history(), [])
        self.assertEqual(ledger.outcome_statistics("ast_defect", "generic_repair")["sample_count"], 0)

    def test_custody_failure_preserves_observed_third_party_change(self):
        target = self.path.parent / "module.py"; target.write_text("broken = True\n")
        executor = IsolatedRepairExecutor(self.path.parent, learning_ledger=self.ledger,
                                          authorized_tokens=["host-configured-test-only"])
        def concurrent_change(_records):
            target.write_text("third_party = True\n")
            raise OSError("injected custody failure and independent writer")
        with patch.object(self.ledger, "_persist", side_effect=concurrent_change):
            with self.assertRaises(RepairEvidencePersistenceError) as caught:
                executor.execute_closed_loop_repair(target_file=target,
                    replacement_code="broken = False\n", defect_probe=lambda p: "broken = True" in p.read_text(),
                    validator_fn=lambda *args: True, authorization_token="host-configured-test-only")
        self.assertFalse(caught.exception.source_restored)
        self.assertEqual(target.read_text(), "third_party = True\n")
        self.assertIn("do not retry", str(caught.exception))
        self.assertEqual(executor.get_history(), [])

    def test_explicit_empty_authority_stays_empty(self):
        self.assertEqual(IsolatedRepairExecutor(self.path.parent, authorized_tokens=[]).authorized_tokens, frozenset())
        with self.assertRaises(ValueError): IsolatedRepairExecutor(self.path.parent, authorized_tokens="token")


class CanonicalRepairQuery(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.ledger = RepairLearningLedger(self.root / "repair.json")
        self.registry = CapabilityRegistry()
        register_repair_learning_capability(self.registry, self.ledger)
        self.runtime = EuclidRuntime(creator_id="owner", state_dir=self.root / "euclid")
        self.runtime.bind_intelligence(self.registry, profile=ExecutionProfile.SHARED_RESTRICTED,
                                      capabilities=["repair-learning-query"])
        self.authority = SubscriptionAuthority({"local": os.urandom(32)}, "test-only")
        self.audit = HashChainAudit(self.root / "guardian.jsonl")
        self.runtime.guardian = ALHaras(self.authority, GuardianPolicy("query-only",
            allowed_operations=frozenset({"intelligence.repair-learning-query"})), self.audit)
        self.runtime.rights.grant("owner", "intelligence", "intelligence.request", "dispatch")

    def tearDown(self):
        self.runtime.close(); self.temp.cleanup()

    def dispatch(self, **arguments):
        now = int(time.time())
        token = self.authority.issue(SubscriptionClaims("s", "tenant", "test-only", "local",
            ("hyba.security",), ("actor",), now - 5, now + 60))
        return self.runtime.dispatch_specialist("intelligence",
            {"operation": "repair-learning-query", "arguments": arguments}, tenant_id="tenant",
            actor="actor", subscription_token=token)

    def test_real_query_has_no_executor_or_implicit_write(self):
        result = self.dispatch(issue_type="ast", problem_signature="sig")
        self.assertTrue(result["allowed"])
        output = result["result"]["output"]
        self.assertIsNone(output["empirical_success_rate"])
        self.assertEqual(output["sample_count"], 0)
        self.assertFalse(self.ledger.storage_path.exists())
        self.assertEqual(self.registry.get_audit_log()[-1].status, "SUCCESS")
        self.assertTrue(HashChainAudit.verify(self.audit.records))

    def test_observed_outcomes_survive_restore_and_canonical_dispatch(self):
        record(self.ledger); self.ledger.load(); self.ledger.load()
        result = self.dispatch(issue_type="ast", problem_signature="sig")
        self.assertEqual(result["result"]["output"]["sample_count"], 1)
        self.assertEqual(result["result"]["output"]["empirical_success_rate"], 1.0)
        self.assertFalse(result["result"]["independently_qualified"])

    def test_revoked_rights_do_not_reach_handler(self):
        self.runtime.rights.revoke("owner", "intelligence", "intelligence.request", "dispatch")
        self.assertFalse(self.dispatch()["allowed"])
        self.assertEqual(self.registry.get_audit_log(), [])

    def test_malformed_request_not_accepted(self):
        for value in (True, "", "x" * 257):
            with self.subTest(value=str(value)[:10]):
                with self.assertRaises(TypeError):
                    self.dispatch(issue_type=value)
        self.assertTrue(all(r.status == "FAILED" for r in self.registry.get_audit_log()))

    def test_nullable_schema_rejects_bad_rate_outputs(self):
        from Intelligence.capability_fabric import _validate_schema, _check_schema
        schema = {"type": ["number", "null"], "minimum": 0, "maximum": 1}
        _check_schema(schema)
        for value in (None, 0, 0.5, 1):
            _validate_schema(value, schema)
        for value in (False, "0.5", -0.1, 1.1, float("nan")):
            with self.subTest(value=value), self.assertRaises(TypeError):
                _validate_schema(value, schema)
        for kinds in ([], ["number", "number"], ["null", []], [False]):
            with self.subTest(kinds=kinds), self.assertRaises(CapabilityRegistrationError):
                _check_schema({"type": kinds})

    def test_duplicate_registration_refused(self):
        with self.assertRaises(CapabilityRegistrationError):
            register_repair_learning_capability(self.registry, self.ledger)
