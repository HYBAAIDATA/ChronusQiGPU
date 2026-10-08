"""Contract/adversarial tests. UnitFabric is synthetic, NOT production evidence."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from salamander.control_plane import EvidenceLedger
from salamander.models import Availability
from salamander.outcome_evidence import (
    CustodiedMiningOutcomeVerifier, EvidenceClass, RuntimeObservation, unqualified_readiness,
)
from salamander.runtime import DurableEvidenceLedger, MiningAutonomyBridge

SHA = "585d7b11d9cc8e183ff4d5cda44996a9ac30dc4e"


def observation(**updates):
    raw = dict(observation_id="obs:1", subject="worker:1", tenant="tenant:1",
               source_subsystem="pythia", metric="execution_progress",
               observed_value=1, expected_range={"operator": "range", "min": 1, "max": 10,
                                               "contract_ref": "contract"},
               timestamp_ns=300, evidence_class=EvidenceClass.MEASURED,
               provenance="independent-worker-progress-probe", source_commit=SHA,
               correlation_id="trace:1")
    raw.update(updates)
    return RuntimeObservation(**raw)


class UnitFabric:
    """Only a unit-test double of the shared fabric's read boundary."""
    def __init__(self):
        common = dict(tenant="tenant:1", source_commit=SHA, recovery_id="r1", subject="worker:1",
                      action_id="a1", action="restart_worker", resource="worker:1", correlation_id="trace:1")
        self.docs = {
            "proof": dict(common, schema="salamander.mining-outcome-proof/v1", authorization_ref="auth",
                          execution_ref="exec", postcondition_ref="post"),
            "auth": dict(common, schema="salamander.action-authorization/v1", decision="ALLOW",
                         policy_version="p1", actor="operator", risk="bounded", timestamp_ns=100, expires_ns=400),
            "exec": dict(common, schema="salamander.owned-action-execution/v1", executed=True,
                         evidence_class="OBSERVED", started_ns=150, completed_ns=200, actuator_id="chronus.worker"),
            "post": dict(common, schema="salamander.independent-postcondition/v1", verified=True,
                         verifier_id="pythia.progress-probe", observations=[observation().as_dict()],
                         expected_vs_observed={"expected": "progress", "observed": 1}),
        }
        self.docs["contract"] = dict(common, schema="salamander.postcondition-contract/v1",
                                     metric="execution_progress",
                                     expected_range={"operator": "range", "min": 1, "max": 10})
        self.sources = {"proof": "pythia", "auth": "al_haras", "exec": "chronus",
                        "post": "pythia", "contract": "pythia"}
        self.corrupt = set()
        self.fabric = self

    def graph(self):
        return {"bindings": [dict(binding_id=k, source_system=v) for k, v in self.sources.items()]}

    def verify(self, ref):
        return {"passed": ref in self.docs and ref not in self.corrupt}

    def read(self, ref):
        return json.dumps(self.docs[ref]).encode()


class ObservationTests(unittest.TestCase):
    def test_all_truth_classes_are_explicit(self):
        self.assertEqual(set(EvidenceClass), {EvidenceClass(x) for x in (
            "OBSERVED", "MEASURED", "DERIVED", "PREDICTED", "SIMULATED", "UNAVAILABLE")})

    def test_synthetic_derived_predicted_are_not_production(self):
        for cls in (EvidenceClass.SIMULATED, EvidenceClass.DERIVED, EvidenceClass.PREDICTED):
            with self.subTest(cls=cls):
                self.assertFalse(observation(evidence_class=cls).production_eligible(now_ns=350, max_age_ns=100))

    def test_missing_is_not_zero(self):
        with self.assertRaises(ValueError):
            observation(evidence_class=EvidenceClass.UNAVAILABLE, observed_value=0)
        self.assertIsNone(observation(evidence_class=EvidenceClass.UNAVAILABLE, observed_value=None).observed_value)

    def test_stale_future_and_unpinned_observations_fail(self):
        for changes in ({"timestamp_ns": 1}, {"timestamp_ns": 400}, {"source_commit": "unknown"}):
            with self.subTest(changes=changes):
                self.assertFalse(observation(**changes).production_eligible(now_ns=350, max_age_ns=100))

    def test_nonfinite_and_unjustified_thresholds_fail(self):
        with self.assertRaises(ValueError):
            observation(observed_value=float("nan"))
        self.assertFalse(observation(expected_range={"operator": "eq", "value": 1}).matches_contract())
        self.assertFalse(observation(observed_value=True).matches_contract())


class ProofTests(unittest.TestCase):
    def setUp(self):
        self.port = UnitFabric()
        self.verifier = CustodiedMiningOutcomeVerifier(self.port, tenant="tenant:1", source_commit=SHA, max_age_ns=100)
        self.recovery = dict(recovery_id="r1", state="VERIFIED", proof_binding_id="proof",
                             tenant="tenant:1", subject="worker:1", action_id="a1",
                             action="restart_worker", resource="worker:1", correlation_id="trace:1")

    def verdict(self):
        return self.verifier.verify(self.recovery, now_ns=350)

    def test_complete_contract_accepts_without_causal_claim(self):
        result = self.verdict()
        self.assertTrue(result.verified)
        self.assertEqual(result.causal_claim, "UNAVAILABLE")

    def test_reported_success_is_not_proof(self):
        self.recovery.pop("proof_binding_id")
        self.assertFalse(self.verdict().verified)

    def test_missing_al_haras_or_wrong_authority_fails(self):
        for ref in ("auth", "exec", "post"):
            with self.subTest(ref=ref):
                original = self.port.sources[ref]
                self.port.sources[ref] = "salamander"
                self.assertFalse(self.verdict().verified)
                self.port.sources[ref] = original

    def test_authorisation_denied_expired_or_posthoc_fails(self):
        original = copy.deepcopy(self.port.docs["auth"])
        for updates in ({"decision": "DENY"}, {"expires_ns": 199}, {"timestamp_ns": 151},
                        {"policy_version": ""}, {"actor": ""}, {"risk": ""}):
            with self.subTest(updates=updates):
                self.port.docs["auth"] = dict(original, **updates)
                self.assertFalse(self.verdict().verified)

    def test_cross_tenant_revision_trace_and_recovery_fail(self):
        original = copy.deepcopy(self.port.docs["post"])
        for updates in ({"tenant": "tenant:2"}, {"source_commit": "a" * 40},
                        {"correlation_id": "foreign"}, {"recovery_id": "r2"}, {"action_id": "a2"}):
            with self.subTest(updates=updates):
                self.port.docs["post"] = dict(original, **updates)
                self.assertFalse(self.verdict().verified)

    def test_actuator_success_does_not_override_bad_observation(self):
        self.port.docs["post"]["observations"][0]["observed_value"] = 0
        self.assertFalse(self.verdict().verified)

    def test_missing_verifier_and_self_verifier_fail(self):
        for value in ("", "chronus.worker"):
            self.port.docs["post"]["verifier_id"] = value
            self.assertFalse(self.verdict().verified)

    def test_missing_or_synthetic_stale_observations_fail(self):
        for changes in ({"evidence_class": "SIMULATED"}, {"timestamp_ns": 200},
                        {"source_subsystem": "chronus"}, {"timestamp_ns": 1},
                        {"tenant": "tenant:2"}, {"subject": "worker:2"}):
            with self.subTest(changes=changes):
                raw = observation().as_dict();raw.update(changes)
                self.port.docs["post"]["observations"] = [raw]
                self.assertFalse(self.verdict().verified)
        self.port.docs["post"]["observations"] = []
        self.assertFalse(self.verdict().verified)

    def test_corrupted_or_disabled_persistence_cannot_certify(self):
        for ref in ("proof", "auth", "exec", "post"):
            self.port.corrupt = {ref}
            self.assertFalse(self.verdict().verified)

    def test_recovery_binding_and_contradictory_outcome_fail(self):
        for key, value in (("tenant", "other"), ("subject", "other"),
                           ("correlation_id", "other"), ("state", "FAILED")):
            original = self.recovery[key]
            self.recovery[key] = value
            self.assertFalse(self.verdict().verified)
            self.recovery[key] = original

    def test_postcondition_threshold_cannot_be_changed_by_proof_producer(self):
        self.port.docs["post"]["observations"][0]["expected_range"]["min"] = 0
        self.assertFalse(self.verdict().verified)
        self.port.docs["post"]["observations"][0]["expected_range"]["min"] = 1
        self.port.corrupt = {"contract"}
        self.assertFalse(self.verdict().verified)

    def test_execution_required_and_no_canned_receipt(self):
        self.port.docs["exec"]["executed"] = False
        self.assertFalse(self.verdict().verified)

    def test_verifier_exceptions_are_unavailable(self):
        with patch.object(self.port, "read", side_effect=RuntimeError("secret-token")):
            result = self.verdict()
        self.assertFalse(result.verified)
        self.assertNotIn("secret-token", result.reason)


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "mirror.jsonl"
        self.bridge = MiningAutonomyBridge(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_reported_verified_is_retained_not_certified(self):
        self.bridge._record_recoveries({"recent": [dict(recovery_id="r1", state="VERIFIED", commands=["RESTART_LANE"], dispatched=["RESTART_LANE"])]}, 350)
        state = self.bridge.snapshot()
        self.assertFalse(state["classification"]["SELF_HEALING"])
        self.assertEqual(state["measured_result"]["reported_state"], "VERIFIED")
        self.assertEqual(state["measured_result"]["state"], "UNVERIFIED")
        self.assertFalse(state["qualification"]["production_ready"])

    def test_deferred_is_not_execution(self):
        self.bridge._record_recoveries({"recent": [dict(recovery_id="r1", state="VERIFIED", commands=["SEVER_LANE"], deferred=["SEVER_LANE"])]}, 350)
        self.assertEqual(self.bridge.snapshot()["action_taken"]["action_taken"], [])

    def test_empty_command_set_does_not_classify_as_automatic(self):
        issue = self.bridge._diagnose({"recovery": {"open": [{"commands": []}]}})
        self.assertEqual(issue["action_class"], "REQUIRES_APPROVAL")

    def test_optimisation_and_rollback_claims_not_verified(self):
        self.bridge._record_optimisation({"last_event": {"event": "ROLLED_BACK", "rollback": True}}, 350)
        state = self.bridge.snapshot()
        self.assertFalse(state["classification"]["SELF_OPTIMISING"])
        self.assertEqual(state["last_optimisation_outcome"]["rollback"], "UNAVAILABLE")
        self.assertTrue(state["last_optimisation_outcome"]["reported_rollback"])

    def test_restart_does_not_restore_unverified_or_historical_success(self):
        self.bridge.ledger.append("runtime-healing-outcome", {"state": "VERIFIED", "event_key": "legacy"}, at_ns=350)
        self.bridge.ledger.append("runtime-optimisation-outcome", {"event": "ACCEPTED"}, at_ns=350)
        restored = MiningAutonomyBridge(self.path)
        self.assertEqual(len(restored.ledger.records), 2)
        self.assertFalse(restored.snapshot()["classification"]["SELF_HEALING"])
        self.assertFalse(restored.snapshot()["classification"]["SELF_OPTIMISING"])

    def test_failed_append_is_retryable(self):
        item = {"recent": [dict(recovery_id="r1", state="VERIFIED", commands=["RESTART_LANE"])]}
        with patch.object(self.bridge.ledger, "append", side_effect=OSError("storage unavailable")):
            with self.assertRaises(OSError): self.bridge._record_recoveries(item, 350)
        self.bridge._record_recoveries(item, 350)
        self.assertEqual(len(self.bridge.ledger.records), 1)

    def test_nonfinite_measurement_unavailable(self):
        self.assertEqual(self.bridge._availability(float("nan")), Availability.UNAVAILABLE)
        self.assertEqual(self.bridge._availability(float("inf")), Availability.UNAVAILABLE)

    def test_non_error_completion_does_not_invent_healthy(self):
        raw = {"schema": "pythia.mining_evidence/1", "last_execution": {"completion_state": "UNKNOWN"}}
        self.assertEqual(self.bridge.observe_mining_snapshot(raw)["health"], "UNAVAILABLE")
        health_record = next(record for record in self.bridge.ledger.records
                             if record["kind"] == "health-decision")
        execution = next(obs for obs in health_record["payload"]["observations"]
                         if obs["dimension"] == "execution")
        self.assertIsNone(execution["value"])
        self.assertEqual(execution["availability"], "UNAVAILABLE")

    def test_custodied_contract_reaches_existing_bridge(self):
        port = UnitFabric()
        verifier = CustodiedMiningOutcomeVerifier(port, tenant="tenant:1", source_commit=SHA, max_age_ns=100)
        bridge = MiningAutonomyBridge(self.path, outcome_verifier=verifier)
        bridge._record_recoveries({"recent": [dict(recovery_id="r1", state="VERIFIED", proof_binding_id="proof", dispatched=["RESTART_LANE"],
                                  tenant="tenant:1", subject="worker:1", action_id="a1",
                                  action="restart_worker", resource="worker:1", correlation_id="trace:1")]}, 350)
        self.assertTrue(bridge.snapshot()["classification"]["SELF_HEALING"])
        self.assertFalse(bridge.snapshot()["qualification"]["production_ready"])


class LedgerTests(unittest.TestCase):
    def test_sink_failure_does_not_commit_memory_or_head(self):
        def fail(_): raise OSError("custody down")
        ledger = EvidenceLedger(sink=fail)
        with self.assertRaises(OSError): ledger.append("observation", {"x": 1}, at_ns=1)
        self.assertEqual(ledger.records, ())
        self.assertEqual(ledger.head, "0" * 64)

    def test_nested_payload_does_not_mutate_custody_identity(self):
        ledger = EvidenceLedger();payload = {"nested": {"x": 1}}
        ledger.append("observation", payload, at_ns=1)
        payload["nested"]["x"] = 2
        self.assertTrue(ledger.verify())

    def test_mirror_tamper_rejected_on_fresh_open(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mirror"
            ledger = DurableEvidenceLedger(path);ledger.append("x", {"x": 1}, at_ns=1)
            path.write_text(path.read_text().replace('"x":1', '"x":2'))
            with self.assertRaises(RuntimeError): DurableEvidenceLedger(path)

    def test_readiness_not_settable_from_claims(self):
        readiness = unqualified_readiness()
        self.assertEqual(len(readiness["gates"]), 12)
        self.assertFalse(readiness["production_ready"])


if __name__ == "__main__":
    unittest.main()
