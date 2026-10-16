"""Real public-package contract regressions; no aliases, mocks, or pytest shim.

Synthetic harness tests below establish plumbing only, not empirical emergence.
"""
import dataclasses
import hashlib
import hmac
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import euclid
import euclid.emergence as public
from euclid.emergence.models import (
    CapabilityManifest, NoveltyReport, TelemetryRecord, SubstrateProperties,
    SubstrateExecutionResult, DiscoveryEnvelope, ReproductionProtocol,
    EmergentCandidate, QualifiedEmergent, RejectedQualification,
    SuspendedQualification, ColonyConfig, CondensationEvent,
)
from euclid.emergence.telemetry import (
    AgentTelemetry, TelemetryKeyManager, TelemetryStream, detect_novelty,
)
from euclid.emergence.substrate import StandardSyncExecutor, RunHarness
from euclid.emergence.cultivator import AgentColony, CondensationCultivator
from euclid.emergence.condensation import ConsortiumGovernance
from euclid.emergence.trusted_core import DivergenceMonitor, EmergentQualificationService
from euclid.emergence.folding.recursive_folding import (
    verify_frozen_max_fold, FROZEN_MAX_FOLD, FROZEN_MAX_FOLD_SIGNATURE,
)


def record(**updates):
    values = dict(run_id="run", substrate_id="substrate", iteration_index=0,
                  task_signature="task", programmed_actions_used=("navigate",),
                  novel_elements=NoveltyReport(), timestamps={"start": 1.25},
                  seeds={"rng": 42}, env_hash="environment")
    values.update(updates)
    return TelemetryRecord(**values).with_computed_hash()


def properties(**updates):
    values = dict(executor_type="sync", observation_latency=5.0,
                  action_granularity="atomic", compute_substrate="declared-vm")
    values.update(updates)
    return SubstrateProperties(**values)


class Contracts(unittest.TestCase):
    def test_actual_public_package(self):
        self.assertTrue(Path(euclid.__file__).is_file())
        self.assertEqual(euclid.EuclidRuntime.__module__, "euclid.runtime")
        self.assertIs(public.CapabilityManifest, CapabilityManifest)
        self.assertEqual(len(public.__all__), 44)
        for name in public.__all__:
            self.assertTrue(hasattr(public, name), name)

    def test_actual_runtime_initialization_remains_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = euclid.EuclidRuntime(creator_id="contract-test-owner", state_dir=directory)
            try:
                self.assertTrue((Path(directory) / "euclid_memory.sqlite3").is_file())
                self.assertFalse(runtime.reachability.integrated("philos"))
                self.assertEqual(runtime.registry.report(), [])
                # No synthetic organ registration is used to fake a bridge.
            finally:
                runtime.close()

    def test_manifest_semantic_binding(self):
        a = CapabilityManifest({"a"}, {("a", "b")}, {"s"})
        b = dataclasses.replace(a, declared_compositions={("b", "a")})
        self.assertNotEqual(a.compute_hash(), b.compute_hash())
        self.assertEqual(a.compute_hash(), CapabilityManifest({"a"}, {("a", "b")}, {"s"}).compute_hash())

    def test_manifest_normalizes_caller_mutation(self):
        actions = {"a"}
        manifest = CapabilityManifest(actions)
        actions.add("b")
        self.assertEqual(manifest.declared_actions, frozenset({"a"}))

    def test_cross_process_hash_seed_stability(self):
        command = [sys.executable, "-c", "from euclid.emergence.models import CapabilityManifest; print(CapabilityManifest({'a','b'},{('a','b')},{'s'}).compute_hash())"]
        outputs = [subprocess.check_output(command, env=dict(os.environ, PYTHONHASHSEED=seed)) for seed in ("1", "11")]
        self.assertEqual(*outputs)

    def test_telemetry_binds_novelty_and_invariants(self):
        r = record()
        for kwargs in ({"novel_elements": NoveltyReport(("novel",))},
                       {"invariant_violations": ("violation",)},
                       {"seeds": {"rng": 43}}, {"env_hash": "other"}):
            self.assertNotEqual(r.compute_digest(), dataclasses.replace(r, **kwargs).compute_digest())

    def test_record_hash_not_recursively_bound(self):
        r = record()
        self.assertEqual(r.record_hash, r.compute_digest())
        self.assertEqual(r.compute_digest(), dataclasses.replace(r, record_hash="wrong").compute_digest())
        self.assertNotIn("record_hash", json.loads(r.canonical_json()))

    def test_telemetry_snapshot_immutable(self):
        times = {"t": 1.0}
        r = record(timestamps=times)
        digest = r.compute_digest()
        times["t"] = 9.0
        self.assertEqual(digest, r.compute_digest())
        with self.assertRaises(TypeError):
            r.timestamps["t"] = 2.0

    def test_nonfinite_payload_rejected(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.assertRaises(ValueError):
                record(timestamps={"start": value})
            with self.assertRaises(ValueError):
                properties(observation_latency=value)

    def test_iteration_and_seed_types(self):
        for value in (True, -1, 1.5):
            with self.assertRaises(ValueError):
                record(iteration_index=value)
        with self.assertRaises(ValueError):
            record(seeds={"rng": "42"})

    def test_signature_tamper_and_revocation(self):
        km = TelemetryKeyManager()
        r = record()
        sig = km.sign_record(r, "local-test-signer")
        self.assertTrue(km.verify_signature(r, sig))
        self.assertFalse(km.verify_signature(dataclasses.replace(r, novel_elements=NoveltyReport(("tamper",))), sig))
        km.revoke_key(sig.key_id)
        self.assertFalse(km.verify_signature(r, sig))

    def test_payload_remains_float64_boundary(self):
        value = 1.0000000000000002
        self.assertEqual(json.loads(record(timestamps={"t": value}).canonical_json())["timestamps"]["t"], value)

    def test_actual_telemetry_to_stream(self):
        stream, telemetry = TelemetryStream(), AgentTelemetry()
        r, sig = telemetry.on_iteration(
            agent_id="agent", task_signature="task", actions=["navigate"],
            observations=["obs"], decisions=["navigate", "new_action"],
            run_id="run", substrate_id="substrate", iteration_index=0,
            manifest=CapabilityManifest({"navigate"}), telemetry_stream=stream,
        )
        self.assertTrue(telemetry.key_manager.verify_signature(r, sig))
        self.assertEqual(stream.count(), 1)
        self.assertTrue(stream.verify_integrity()[0])
        self.assertIn("new_action", r.novel_elements.unattributed)

    def test_substrate_identity_binds_description(self):
        p = properties()
        for kwargs in ({"sandbox_id": "other"}, {"memory_limit_mb": 128},
                       {"complexity_axis_tags": ("depth:2",)}):
            self.assertNotEqual(p.compute_id(), dataclasses.replace(p, **kwargs).compute_id())

    def test_run_hash_binds_full_records(self):
        p = properties()
        result = SubstrateExecutionResult(p.compute_id(), p, 1, telemetry_records=[record()])
        original = result.compute_run_hash()
        result.telemetry_records[0] = record(novel_elements=NoveltyReport(("new",)))
        self.assertNotEqual(original, result.compute_run_hash())
        mutated = result.compute_run_hash()
        result.run_hash = "not-part-of-payload"
        self.assertEqual(mutated, result.compute_run_hash())

    def test_run_rejects_identity_mismatch(self):
        with self.assertRaises(ValueError):
            SubstrateExecutionResult("wrong", properties(), 0)

    def test_envelope_expansion_explicit_semantics(self):
        source = DiscoveryEnvelope(10, .5, .5, {"alpha": (0, 10)})
        expanded = source.scale_margin(1.5)
        self.assertEqual(expanded.parameter_bounds["alpha"], (-2.5, 12.5))
        self.assertEqual(expanded.max_observation_latency, 15)
        self.assertAlmostEqual(expanded.compute_budget_sec, 1/3)
        self.assertEqual(source.parameter_bounds["alpha"], (0, 10))
        with self.assertRaises(ValueError):
            source.scale_margin(.5)

    def test_invalid_bounds_and_protocol(self):
        with self.assertRaises(ValueError):
            DiscoveryEnvelope(1, 1, 1, {"x": (2, 1)})
        for seeds, tolerance in (((), .95), ((True,), .95), ((42,), 1.1)):
            with self.assertRaises(ValueError):
                ReproductionProtocol("task", seeds, "manifest", "env", ("observable",), tolerance)

    def test_candidate_supports_actual_folding_source(self):
        p = ReproductionProtocol("task", (42,), "manifest", "env", ("x",))
        c = EmergentCandidate("id", "cap", "sub", DiscoveryEnvelope(1, .5, .5), p, source="fold(depth=0)+model_1")
        self.assertIn("source", c.to_dict())

    def test_outcomes_serialize_distinctly(self):
        outcomes = [QualifiedEmergent("id", "cap", .95, {}, {}, "local-token", "local-governance"),
                    RejectedQualification("id", "cap", "gate1", "missing evidence"),
                    SuspendedQualification("id", "cap", "drift", 1, .25, "drift")]
        self.assertEqual([json.loads(json.dumps(v.to_dict()))["status"] for v in outcomes],
                         ["QUALIFIED", "REJECTED", "SUSPENDED"])

    def test_bounded_synthetic_colony_and_breeding(self):
        colony = AgentColony(ColonyConfig("test", interaction_topology="recursive_folding"))
        self.assertEqual(len(colony.run(iterations=12)), 12)
        self.assertTrue(colony.stream.verify_integrity()[0])
        children = CondensationCultivator().breed([colony], target_size=2, generation=1)
        self.assertEqual(len(children), 2)
        self.assertTrue(all(child.generation == 1 for child in children))

    def test_bounded_synthetic_harness(self):
        p = properties()
        executor = StandardSyncExecutor(p)
        h = RunHarness({p.compute_id(): executor})
        result = h.execute(None, ["task"], p.compute_id(), tiers=[3])
        self.assertEqual(result.iterations_completed, 3)
        self.assertEqual(len(result.telemetry_records), 3)
        self.assertEqual(result.run_hash, result.compute_run_hash())

    def test_novelty_and_divergence_consumers(self):
        novelty = detect_novelty(["navigate", "x"], [], CapabilityManifest({"navigate"}))
        self.assertIn("x", novelty.unattributed)
        divergent, report = DivergenceMonitor().divergence_detected([record(invariant_violations=("tripwire",))])
        self.assertTrue(divergent)
        self.assertEqual(report["divergence_metric"], "invariant_violations")

    def test_event_and_adjudication_contract(self):
        event = CondensationEvent({"criticality": {"avalanche_count": 10, "power_law_fit": .8}}, ["a", "b"])
        with self.assertRaises(CondensationEvent):
            raise event
        verdict = ConsortiumGovernance().adjudicate(event, ["a", "b", "c"], [True, True, True])
        self.assertEqual(verdict.promoted_status, "QUALIFIED_HYPOTHESIS")
        self.assertEqual(verdict.event_id, event.event_id)
        # This checks schema plumbing, not independent reviewer identities.

    def test_qualification_refuses_missing_authority(self):
        from euclid.emergence.trusted_core.access_control import InvalidGovernanceTokenError
        with self.assertRaises(InvalidGovernanceTokenError):
            EmergentQualificationService().qualify(None, None, None)


class SecurityRegressions(unittest.TestCase):
    def test_frozen_ceiling_rejects_recomputed_public_salt_mac(self):
        forged = hmac.new(b"euclid_phi2_frozen_recursion_ceiling_2026", b"MAX_FOLD=999", hashlib.sha256).hexdigest()
        self.assertFalse(verify_frozen_max_fold(999, forged))
        self.assertTrue(verify_frozen_max_fold(FROZEN_MAX_FOLD, FROZEN_MAX_FOLD_SIGNATURE))

    def test_signature_identity_cannot_be_relabelled(self):
        km, r = TelemetryKeyManager(), record()
        sig = km.sign_record(r, "alice")
        self.assertFalse(km.verify_signature(r, dataclasses.replace(sig, signer_identity="mallory")))
        self.assertFalse(km.verify_signature(r, dataclasses.replace(sig, algorithm="not-Ed25519")))

    def test_explicit_key_cannot_sign_as_other_identity(self):
        km = TelemetryKeyManager()
        kid = km.generate_key_for_signer("alice")
        with self.assertRaises(PermissionError):
            km.sign_record(record(), "mallory", key_id=kid)

    def test_key_identifier_cannot_be_overwritten(self):
        km = TelemetryKeyManager()
        km.generate_key_for_signer("alice", "fixed")
        with self.assertRaises(ValueError):
            km.generate_key_for_signer("mallory", "fixed")


if __name__ == "__main__":
    unittest.main()
