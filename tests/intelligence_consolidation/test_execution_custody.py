"""Actual canonical execution and temporary-filesystem custody regressions."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from tests.intelligence_consolidation import test_canonical_bridge as fixtures
from tests.intelligence_consolidation.test_canonical_bridge import manifest
from Intelligence.capability_fabric import CapabilityRegistry, ExecutionProfile, _digest_data
from al_haras import ALHaras, GuardianPolicy, HashChainAudit


class DispatchCustodyRegression(unittest.TestCase):
    def test_handler_mutation_does_not_rewrite_admitted_input_receipt(self):
        registry = CapabilityRegistry()
        def mutate(*, data):
            data["items"].append("handler mutation")
            return {"seen": data}
        registry.register(manifest(), mutate)
        original = {"items": ["admitted"]}
        output, receipt = registry.dispatch("unit-contract", profile=ExecutionProfile.INTERNAL_RESEARCH,
                                           _strict_json=True, data=original)
        self.assertEqual(receipt.input_digest, _digest_data({"data": {"items": ["admitted"]}}))
        self.assertEqual(original, {"items": ["admitted"]})
        self.assertEqual(output["seen"]["items"], ["admitted", "handler mutation"])

    def test_admission_audit_failure_prevents_real_file_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            effect = Path(tmp)/"effect"
            registry = CapabilityRegistry()
            def execute():
                effect.write_text("executed")
                return {}
            def broken(event):
                raise OSError("audit storage unavailable")
            registry.register(manifest(), execute)
            with self.assertRaises(OSError):
                registry.dispatch("unit-contract", profile=ExecutionProfile.INTERNAL_RESEARCH,
                                  _strict_json=True, _audit_sink=broken)
            self.assertFalse(effect.exists())
            self.assertEqual(registry.get_audit_log()[-1].status, "FAILED")

    def test_completion_audit_failure_does_not_return_success_or_claim_rollback(self):
        events = []
        calls = []
        registry = CapabilityRegistry()
        registry.register(manifest(), lambda: calls.append("executed") or {})
        def sink(event):
            events.append(event)
            if event["kind"] == "capability-completed":
                raise OSError("completion persistence failed")
        with self.assertRaises(OSError):
            registry.dispatch("unit-contract", profile=ExecutionProfile.INTERNAL_RESEARCH,
                              _strict_json=True, _audit_sink=sink)
        self.assertEqual(calls, ["executed"])
        self.assertEqual(registry.get_audit_log()[-1].status, "FAILED")
        self.assertEqual([e["kind"] for e in events],
                         ["capability-admitted", "capability-completed", "capability-failed"])
        self.assertEqual(len({e["execution_id"] for e in events}), 1)

    def test_lossy_json_inputs_refused_without_handler(self):
        registry = CapabilityRegistry(); calls = []
        registry.register(manifest(), lambda **kwargs: calls.append(kwargs) or {})
        for data in ({1: "integer key"}, ("tuple",), float("nan"), Path("host")):
            with self.subTest(data=data), self.assertRaises(TypeError):
                registry.dispatch("unit-contract", profile=ExecutionProfile.INTERNAL_RESEARCH,
                                  _strict_json=True, data=data)
        self.assertEqual(calls, [])

    def test_non_json_output_is_not_verified_success(self):
        registry = CapabilityRegistry()
        registry.register(manifest(), lambda: {"value": Path("unbound")})
        with self.assertRaises(TypeError):
            registry.dispatch("unit-contract", profile=ExecutionProfile.INTERNAL_RESEARCH, _strict_json=True)
        self.assertEqual(registry.get_audit_log()[-1].status, "FAILED")


class CanonicalCustodyIntegration(unittest.TestCase):
    setUp = fixtures.CanonicalBridgeIntegration.setUp
    tearDown = fixtures.CanonicalBridgeIntegration.tearDown
    grant = fixtures.CanonicalBridgeIntegration.grant
    token = fixtures.CanonicalBridgeIntegration.token
    dispatch = fixtures.CanonicalBridgeIntegration.dispatch
    register = fixtures.CanonicalBridgeIntegration.register

    def test_durable_native_execution_chain_survives_reopen(self):
        result = self.register()["result"]
        path = self.runtime.state_dir/"intelligence"/"intelligence.jsonl"
        reopened = HashChainAudit(path)
        self.assertTrue(HashChainAudit.verify(reopened.records))
        events = [r["event"] for r in reopened.records]
        self.assertEqual([e["kind"] for e in events], ["capability-admitted", "capability-completed"])
        self.assertEqual(events[0]["execution_id"], events[1]["execution_id"])
        self.assertEqual(events[1]["receipt_sha256"], result["receipt"]["receipt_sha256"])
        self.assertNotIn("example conjecture", path.read_text())

    def test_guardian_observation_mutation_cannot_change_dispatched_request(self):
        guardian = self.runtime.guardian
        # External observer boundary only; authorization remains real AL HARAS.
        class MutatingObserver:
            def evaluate(inner, request, **kwargs):
                verdict = guardian.evaluate(request, **kwargs)
                request.payload["arguments"]["conjecture_id"] = "substituted"
                return verdict
        self.runtime.guardian = MutatingObserver()
        self.register()
        self.assertIsNotNone(self.tracker.get_conjecture("c"))
        self.assertIsNone(self.tracker.get_conjecture("substituted"))

    def review_setup(self):
        from Intelligence.repository_review import ReviewPolicy
        from Intelligence.repository_review_capability import register_repository_review_capability
        self.repo = self.root/"repo"; self.repo.mkdir()
        self.source = self.repo/"example.py"; self.source.write_text("value = 3\n")
        policy = ReviewPolicy((("example.py", hashlib.sha256(self.source.read_bytes()).hexdigest()),))
        policies = {"approved": policy}
        register_repository_review_capability(self.registry, repo_root=self.repo, approved_policies=policies)
        policies.clear()  # Host mapping must not remain a mutable execution input.
        self.specialist = self.runtime.bind_intelligence(self.registry,
            profile=ExecutionProfile.SHARED_RESTRICTED, capabilities=["repository-review"], organ_id="review")
        self.runtime.rights.grant("owner", "review", "review.request", "dispatch")
        self.runtime.guardian = ALHaras(self.authority, GuardianPolicy("local-review-policy",
            allowed_operations=frozenset({"review.repository-review"})), self.audit)

    def review(self, arguments):
        return self.runtime.dispatch_specialist("review", {"operation": "repository-review", "arguments": arguments},
            tenant_id="tenant", actor="actor", subscription_token=self.token())

    def test_actual_source_bound_review_from_canonical_runtime(self):
        self.review_setup()
        result = self.review({"review_id": "approved"})
        self.assertTrue(result["allowed"])
        self.assertTrue(result["result"]["executed"])
        self.assertEqual(result["result"]["output"]["status"], "REVIEWED_READ_ONLY")
        self.assertEqual(self.source.read_text(), "value = 3\n")
        self.assertTrue(self.specialist.catalog()[0]["available"])
        self.registry.unregister("repository-review")
        self.assertFalse(self.specialist.catalog()[0]["available"])

    def test_unapproved_client_policy_and_root_are_refused(self):
        self.review_setup()
        for arguments in ({"review_id": "unapproved"}, {"review_id": "approved", "repo_root": "/"}):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError if len(arguments)==1 else TypeError):
                self.review(arguments)
        self.assertEqual(self.source.read_text(), "value = 3\n")

    def test_changed_source_and_symlink_are_refused(self):
        self.review_setup()
        self.source.write_text("value = 4\n")
        with self.assertRaises(ValueError):
            self.review({"review_id": "approved"})
        self.source.unlink()
        outside = self.root/"outside.py"; outside.write_text("value = 3\n")
        try:
            self.source.symlink_to(outside)
        except OSError:
            self.skipTest("Symlinks require privilege on Windows")
        with self.assertRaises((ValueError, OSError)):
            self.review({"review_id": "approved"})
        self.assertTrue(self.source.is_symlink())
        self.assertEqual(outside.read_text(), "value = 3\n")

    def test_catalog_schema_is_detached_and_does_not_grant_authority(self):
        self.review_setup()
        row = self.specialist.catalog()[0]
        row["input_schema"]["required"].clear()
        self.assertEqual(self.specialist.catalog()[0]["input_schema"]["required"], ["review_id"])
        self.assertFalse(row["independently_qualified"])
        self.runtime.rights.revoke("owner", "review", "review.request", "dispatch")
        self.assertFalse(self.review({"review_id": "approved"})["allowed"])

    def test_receipt_and_admission_share_local_handler_binding(self):
        result = self.register()["result"]
        records = HashChainAudit(self.runtime.state_dir/"intelligence"/"intelligence.jsonl").records
        binding = records[0]["event"]["binding"]
        self.assertEqual(binding, result["receipt"]["side_effects"]["execution_binding"])
        self.assertEqual(len(binding["handler_code_digest"]), 64)
        self.assertEqual(len(binding["manifest_digest"]), 64)
        self.assertIn("not_closure_or_external_state", binding["handler_binding_scope"])

    def test_binding_rejects_absolute_and_path_like_audit_identifiers(self):
        escaped = self.root / "escaped"
        for organ_id in (str(escaped), "nested/name", "nested\\name", "x"*65):
            with self.subTest(organ_id=organ_id), self.assertRaises(ValueError):
                self.runtime.bind_intelligence(self.registry, profile=ExecutionProfile.INTERNAL_RESEARCH,
                                              capabilities=["proof-conjecture"], organ_id=organ_id)
        self.assertFalse(escaped.with_suffix(".jsonl").exists())

    def test_specialist_authority_is_explicit_without_creating_rights(self):
        from euclid.contracts import Authority
        self.runtime.register_specialist("proposal-owner", lambda request: {},
                                         operations=("propose",), authority=Authority.PROPOSE)
        self.assertIs(self.runtime.registry.get("proposal-owner").authority, Authority.PROPOSE)
        self.assertFalse(self.runtime.rights.permits("owner","proposal-owner","proposal-owner.request","dispatch"))
        with self.assertRaises(TypeError):
            self.runtime.register_specialist("invalid-owner",lambda request: {},authority="propose")

    def test_unconfigured_review_is_disabled(self):
        from Intelligence.repository_review_capability import register_repository_review_capability
        register_repository_review_capability(self.registry, repo_root=self.root)
        self.assertFalse(self.registry.get_manifest("repository-review").enabled)
        with self.assertRaises(PermissionError):
            self.runtime.bind_intelligence(self.registry, profile=ExecutionProfile.INTERNAL_RESEARCH,
                                          capabilities=["repository-review"], organ_id="review")
