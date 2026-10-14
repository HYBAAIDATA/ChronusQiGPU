"""Real canonical runtime, AL HARAS, native registration and proof-state handler.

Local random HMAC entitlements exercise authorization, not external certification.
Filesystem state is temporary Linux SQLite/JSONL; no mining/network/provider I/O.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from Intelligence.capability_fabric import (
    AuthorizationDenied, CapabilityExecutionError, CapabilityManifest,
    CapabilityPermissions, CapabilityRegistrationError, CapabilityRegistry,
    DeterminismClass, ExecutionProfile, ResourceBudget, SideEffectClass,
)
from Intelligence.mathematical_research import MathematicalProofTracker
from Intelligence.proof_capability import register_proof_capability
from al_haras import ALHaras, GuardianPolicy, HashChainAudit, SubscriptionAuthority, SubscriptionClaims
from euclid import EuclidRuntime


def manifest(**changes):
    values = dict(capability_id="unit-contract", version="1.0.0", source_provenance=__file__,
        description="adversarial unit handler, not a production capability",
        permissions=CapabilityPermissions(allowed_profiles=tuple(ExecutionProfile)),
        resource_budget=ResourceBudget(), supported_operations=("run",),
        determinism=DeterminismClass.DETERMINISTIC, side_effects=SideEffectClass.READ_ONLY,
        verification_strategy="unit-only")
    values.update(changes)
    return CapabilityManifest(**values)


class FabricRegression(unittest.TestCase):
    def setUp(self):
        self.registry = CapabilityRegistry()
        self.calls = []

    def add(self, output=None, **changes):
        def handler(**kwargs):
            self.calls.append(kwargs)
            return {} if output is None else output
        self.registry.register(manifest(**changes), handler)

    def run_unit(self, **kwargs):
        return self.registry.dispatch("unit-contract", profile=ExecutionProfile.INTERNAL_RESEARCH, **kwargs)

    def test_shared_code_execution_denied_before_handler(self):
        self.add(permissions=CapabilityPermissions(can_execute_code=True, allowed_profiles=tuple(ExecutionProfile)))
        with self.assertRaises(AuthorizationDenied):
            self.registry.dispatch("unit-contract", profile=ExecutionProfile.SHARED_RESTRICTED)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.registry.get_audit_log()[-1].status, "FAILED")

    def test_failure_shapes_never_success(self):
        for output in ({"status": "FAILED"}, {"success": False}, {"executed": False},
                       {"error": "missing handler"}, {"status": "REFUSED"}, {"status": "UNAVAILABLE"}):
            with self.subTest(output=output):
                self.registry = CapabilityRegistry(); self.add(output)
                with self.assertRaises(CapabilityExecutionError): self.run_unit()
                self.assertEqual(self.registry.get_audit_log()[-1].status, "FAILED")

    def test_native_failure_dataclass_not_success(self):
        from Intelligence.salamander_transaction import RepairResult
        self.add(RepairResult("REFUSED", "external validation unavailable"))
        with self.assertRaises(CapabilityExecutionError): self.run_unit()
        self.assertEqual(self.registry.get_audit_log()[-1].status, "FAILED")

    def test_simulation_and_unverified_are_distinct(self):
        for output, status in (({"simulated": True}, "SIMULATED"), ({"status": "UNVERIFIED"}, "UNVERIFIED")):
            with self.subTest(status=status):
                self.registry = CapabilityRegistry(); self.add(output)
                self.assertEqual(self.run_unit()[1].status, status)

    def test_invalid_inputs_no_execution(self):
        self.add(input_schema={"type": "object", "required": ["n"], "additionalProperties": False,
            "properties": {"n": {"type": "integer", "minimum": 1, "maximum": 4}}})
        for kwargs in ({}, {"n": True}, {"n": 0}, {"n": 5}, {"n": "2"}, {"n": 2, "extra": 3}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(TypeError): self.run_unit(**kwargs)
        self.assertEqual(self.calls, [])
        self.assertEqual(len(self.registry.get_audit_log()), 6)
        self.assertEqual(self.run_unit(n=2)[1].status, "SUCCESS")

    def test_output_validation(self):
        self.add({"count": "not-int"}, output_schema={"type": "object", "required": ["count"],
            "properties": {"count": {"type": "integer"}}})
        with self.assertRaises(TypeError): self.run_unit()
        self.assertEqual(self.registry.get_audit_log()[-1].status, "FAILED")

    def test_unknown_and_disabled_audited(self):
        with self.assertRaises(KeyError): self.run_unit()
        self.add(enabled=False)
        with self.assertRaises(CapabilityExecutionError): self.run_unit()
        self.assertEqual([r.status for r in self.registry.get_audit_log()], ["FAILED", "FAILED"])

    def test_bad_profile_no_handler(self):
        self.add()
        with self.assertRaises(AuthorizationDenied): self.registry.dispatch("unit-contract", profile="internal")
        self.assertEqual(self.calls, [])

    def test_manifest_is_snapshot(self):
        schema={"required": ["n"]}; original=manifest(input_schema=schema)
        self.registry.register(original, lambda **kwargs: {})
        schema.clear(); self.registry.get_manifest("unit-contract").input_schema.clear()
        with self.assertRaises(TypeError): self.run_unit()

    def test_audit_is_detached(self):
        self.add({"findings": [{"code": "original"}]})
        receipt=self.run_unit()[1]; receipt.findings[0]["code"]="changed"
        returned=self.registry.get_audit_log(); returned[0].findings.clear()
        self.assertEqual(self.registry.get_audit_log()[0].findings, [{"code": "original"}])

    def test_invalid_schema_fails_at_registration(self):
        for schema in ({"$ref": "unresolved"}, {"type": "anything"}, {"required": "x"},
                       {"minimum": float("nan")}, {"minLength": True}, {"additionalProperties": {}},
                       {"properties": {"x": {"type": "bad"}}}):
            with self.subTest(schema=schema):
                with self.assertRaises(CapabilityRegistrationError): self.add(input_schema=schema)

    def test_nonfinite_output_not_success(self):
        self.add({"number": float("nan")})
        with self.assertRaises(ValueError): self.run_unit()
        self.assertEqual(self.registry.get_audit_log()[-1].status, "FAILED")

    def test_permission_contract_types(self):
        for permission in (CapabilityPermissions(can_execute_code="false"),
                           CapabilityPermissions(allowed_profiles=("internal",))):
            with self.subTest(permission=permission):
                with self.assertRaises(CapabilityRegistrationError): self.add(permissions=permission)

    def test_invalid_budget(self):
        for changes in ({"max_runtime_seconds": float("inf")}, {"max_findings": -1},
                        {"max_memory_mb": True}, {"max_file_bytes": 2, "max_total_bytes": 1}):
            with self.subTest(changes=changes):
                with self.assertRaises(CapabilityRegistrationError): ResourceBudget(**changes)

    def test_findings_limit(self):
        self.add({"findings": [{}, {}]}, resource_budget=ResourceBudget(max_findings=1))
        with self.assertRaises(CapabilityExecutionError): self.run_unit()

    def test_input_envelope_before_handler(self):
        self.add(resource_budget=ResourceBudget(max_file_bytes=16, max_total_bytes=16))
        with self.assertRaises(CapabilityExecutionError): self.run_unit(payload="x"*30)
        self.assertEqual(self.calls, [])

    def test_receipt_discloses_enforcement_limits(self):
        self.add(); receipt=self.run_unit()[1]
        self.assertFalse(receipt.side_effects["process_isolated"])
        self.assertFalse(receipt.side_effects["memory_enforced"])
        self.assertEqual(receipt.side_effects["runtime_enforcement"], "post-return")


class CanonicalBridgeIntegration(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.runtime=EuclidRuntime(creator_id="owner", state_dir=self.root/"euclid")
        self.registry=CapabilityRegistry(); self.tracker=MathematicalProofTracker()
        register_proof_capability(self.registry, self.tracker)
        self.runtime.bind_intelligence(self.registry, profile=ExecutionProfile.INTERNAL_RESEARCH,
                                      capabilities=["proof-conjecture"])
        self.authority=SubscriptionAuthority({"local": os.urandom(32)}, "local-test-authority")
        self.audit=HashChainAudit(self.root/"guardian"/"decisions.jsonl")
        self.runtime.guardian=ALHaras(self.authority, GuardianPolicy("local-test-policy",
            allowed_operations=frozenset({"intelligence.proof-conjecture"})), self.audit)
        self.grant()

    def tearDown(self):
        self.runtime.close(); self.temp.cleanup()

    def grant(self):
        self.runtime.rights.grant("owner", "intelligence", "intelligence.request", "dispatch")

    def token(self, tenant="tenant", actor="actor", expired=False):
        now=int(time.time())
        claims=SubscriptionClaims("test-subscription", tenant, "local-test-authority", "local",
            ("hyba.security",), (actor,), now-60, now-1 if expired else now+60)
        return self.authority.issue(claims)

    def dispatch(self, arguments, token=None, **changes):
        kw=dict(tenant_id="tenant", actor="actor", subscription_token=self.token() if token is None else token)
        kw.update(changes)
        return self.runtime.dispatch_specialist("intelligence",
            {"operation": "proof-conjecture", "arguments": arguments}, **kw)

    def register(self):
        return self.dispatch(dict(action="register", conjecture_id="c", domain="number-theory",
            statement="example conjecture, not proven", unresolved_steps=["unproved obligation"]))

    def test_real_native_registration_dispatch_result_and_audit(self):
        result=self.register()
        self.assertTrue(result["allowed"]); self.assertTrue(result["result"]["executed"])
        self.assertEqual(result["result"]["receipt"]["status"], "SUCCESS")
        self.assertFalse(result["result"]["independently_qualified"])
        self.assertIsNotNone(self.tracker.get_conjecture("c"))
        queried=self.dispatch({"action": "get", "conjecture_id": "c"})
        self.assertEqual(queried["result"]["output"]["status"], "conjectured")
        self.assertEqual(len(self.registry.get_audit_log()), 2)
        self.assertTrue(HashChainAudit.verify(self.audit.records))
        self.assertTrue(any(r.kind == "delegation-result" for r in self.runtime.evidence.records))

    def test_experiment_is_not_proof(self):
        self.register()
        result=self.dispatch(dict(action="experiment", conjecture_id="c", experiment_name="bounded",
            parameters={"n": 3}, results={"value": 9}, consistent=True))
        self.assertEqual(result["result"]["output"]["claim"], "NUMERICAL_EVIDENCE_NOT_FORMAL_PROOF")
        self.assertEqual(self.tracker.get_conjecture("c").status.value, "experimentally_evidenced")

    def test_invalid_expired_tampered_and_wrong_tenant_tokens_no_handler(self):
        valid=self.token(); body, signature=valid.split(".")
        bad=body+"."+("A" if signature[0] != "A" else "B")+signature[1:]
        for token in ("", bad, self.token(expired=True), self.token(tenant="other"), self.token(actor="other")):
            with self.subTest(token_kind=token[:5]):
                self.assertFalse(self.dispatch({"action": "register", "conjecture_id": "c", "domain": "d", "statement": "s"}, token=token)["allowed"])
        self.assertEqual(self.registry.get_audit_log(), [])
        self.assertIsNone(self.tracker.get_conjecture("c"))

    def test_creator_rights_revocation_blocks_dispatch(self):
        self.runtime.rights.revoke("owner", "intelligence", "intelligence.request", "dispatch")
        self.assertFalse(self.register()["allowed"])
        self.assertEqual(self.registry.get_audit_log(), [])

    def test_guardian_absence_refuses_even_with_rights(self):
        self.runtime.guardian=None
        self.assertFalse(self.register()["allowed"])
        self.assertEqual(self.registry.get_audit_log(), [])

    def test_missing_conjecture_is_not_success(self):
        with self.assertRaises(KeyError): self.dispatch({"action": "get", "conjecture_id": "absent"})
        self.assertEqual(self.registry.get_audit_log()[-1].status, "FAILED")
        self.assertFalse(any(r.kind == "delegation-result" for r in self.runtime.evidence.records))

    def test_profile_injection_refused_before_dispatch(self):
        with self.assertRaises(TypeError): self.dispatch({"conjecture_id": "c", "profile": "internal"})
        self.assertIsNone(self.tracker.get_conjecture("c"))

    def test_unregistration_and_permission_change_fail_closed(self):
        self.registry.unregister("proof-conjecture")
        self.assertFalse(self.register()["allowed"])
        register_proof_capability(self.registry, self.tracker)
        self.registry.unregister("proof-conjecture")
        self.registry.register(manifest(capability_id="proof-conjecture",
            permissions=CapabilityPermissions(can_execute_code=True)), lambda **kwargs: {})
        self.assertFalse(self.register()["allowed"])
        self.assertIsNone(self.tracker.get_conjecture("c"))

    def test_binding_does_not_create_rights(self):
        self.runtime.rights.revoke("owner", "intelligence", "intelligence.request", "dispatch")
        self.assertFalse(self.runtime.rights.permits("owner", "intelligence", "intelligence.request", "dispatch"))
        with self.assertRaises(ValueError):
            self.runtime.bind_intelligence(self.registry, profile=ExecutionProfile.INTERNAL_RESEARCH,
                                          capabilities=["proof-conjecture"])

    def test_mutation_capability_binding_denied(self):
        self.registry.register(manifest(capability_id="mutation", side_effects=SideEffectClass.SYSTEM_MUTATION), lambda: {})
        with self.assertRaises(AuthorizationDenied):
            self.runtime.bind_intelligence(self.registry, profile=ExecutionProfile.INTERNAL_RESEARCH,
                                          capabilities=["mutation"], organ_id="second")

    def test_closed_runtime(self):
        self.runtime.close()
        with self.assertRaises(RuntimeError): self.register()


class ImportCompositionRegression(unittest.TestCase):
    def test_leaf_import_does_not_initialize_engines(self):
        code='import sys; import Intelligence; from Intelligence.capability_fabric import CapabilityRegistry; assert "Intelligence.salamander" not in sys.modules; assert "Intelligence.orchestrator" not in sys.modules; assert "Intelligence.asi" not in sys.modules; assert "Intelligence.consciousness" not in sys.modules; assert Intelligence._ORCHESTRATOR is None'
        subprocess.run([sys.executable, "-c", code], check=True)

    def test_unknown_export_is_honest(self):
        import Intelligence
        with self.assertRaises(AttributeError): getattr(Intelligence, "not_an_export")


if __name__ == "__main__": unittest.main()
