"""Contract test suite for the sequential pipeline C1-C4 and the
governance contracts 12.8-12.10 (CONTRACTS.md section 16)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
import yaml

from al_haras.claims_yaml import evaluate_release
from al_haras.claims_yaml import load_claims
from al_haras.deployment_manifest import ManifestRejected
from al_haras.deployment_manifest import ServiceBinding
from al_haras.deployment_manifest import compile_deployment
from al_haras.deployment_manifest import load_manifest
from al_haras.deployment_manifest import sign_manifest
from al_haras.deployment_manifest import verify_manifest
from al_haras.pairings import PairingRecord
from al_haras.pairings import PairingRejected
from al_haras.pairings import PairingStatus
from al_haras.pairings import PairingTest
from al_haras.pairings import admit_pairing
from al_haras.pairings import load_pairings
from hyba_contracts.types import BackendCertificate
from hyba_contracts.types import BackendClass
from hyba_contracts.types import EnterprisePolicyContext
from hyba_contracts.types import FoldContract
from hyba_contracts.types import FoldMode
from hyba_contracts.types import OperatorContract
from hyba_contracts.planning import AuthorizedQuery
from hyba_contracts.planning import ExecutionPlan
from hyba_contracts.planning import FallbackPolicy
from hyba_contracts.planning import PlanningRejected
from hyba_contracts.planning import QueryBudget
from hyba_contracts.planning import QueryRequest
from hyba_contracts.planning import authorize_query
from hyba_contracts.planning import build_execution_plan
from hyba_profiles.intent_manifest import IntentRejected
from hyba_profiles.intent_manifest import load_intent_manifest

ROOT = Path(__file__).resolve().parents[1]
KEY = b"k" * 32

MANIFEST = ROOT / "manifests" / "intent.example.yaml"


def _encode(x):
    return (x, None)


def _decode(x, _r):
    return x


def _policy(**over) -> EnterprisePolicyContext:
    values = dict(
        actor_principal="user",
        tenant="t",
        instance="i",
        purpose="test",
        residency="local",
        retention="p30",
        exactness_required=True,
        operator_allowed=True,
        reconstruction_allowed=False,
        training_allowed=False,
        export_allowed=False,
        degraded_operation_allowed=False,
        sovereign_domain="local",
        classification_level="internal",
    )
    values.update(over)
    return EnterprisePolicyContext(**values)


def _query(**over) -> QueryRequest:
    values = dict(
        statement="select fold of object",
        operators=("fold",),
        exactness_mode="exact",
        residency=("local",),
    )
    values.update(over)
    return QueryRequest(**values)


def _authorize(q=None, **over) -> AuthorizedQuery:
    kw = dict(
        policy_context=_policy(),
        allowed_backends=("cpu-exact", "mla1517"),
        allowed_exactness_modes=("exact",),
        allowed_operators=("fold", "unfold"),
        budget=QueryBudget(bytes_moved=4096, proof_bytes=1024),
        residency_constraint=("local",),
        reconstruction_permitted=False,
        export_permitted=False,
    )
    kw.update(over)
    return authorize_query(q or _query(), **kw)


def _fold() -> FoldContract:
    return FoldContract(
        family="fibonacci",
        domain="objects",
        exactness_mode="exact",
        encode=_encode,
        decode=_decode,
        supported_operators=("fold",),
        invariant_set=("i1",),
        residual_bound="0",
        canonical_hash_rule="sha256",
        backend_requirements=(),
    )


def _operator(mode: FoldMode = FoldMode.PRESERVE) -> OperatorContract:
    return OperatorContract(
        operator="fold",
        accepted_fold_families=("fibonacci",),
        mode=mode,
        input_invariants=("i1",),
        output_invariants=("i1",),
        residual_rule="none",
        proof_rule="hash",
        deterministic=True,
        backend_capabilities=(),
    )


def _backend() -> BackendCertificate:
    return BackendCertificate(
        backend_name="cpu-exact",
        backend_class=BackendClass.CLASSICAL_EXACT,
        device_id="cpu0",
        exactness_modes=("exact",),
        overflow_behavior="fail_closed",
        supported_operators=("fold",),
        attestation="att",
        conformance_hash="hash",
    )


def _plan(q=None, **over) -> ExecutionPlan:
    kw = dict(
        plan_id="p1",
        query=q or _authorize(),
        object_ids=("o1",),
        fold_contract=_fold(),
        operator_contract=_operator(),
        backend=_backend(),
        operator_mode=FoldMode.PRESERVE,
        residual_budget=0,
        movement_budget=1024,
        proof_requirement="hash",
        fallback_policy=FallbackPolicy(permitted=False, marked=False),
    )
    kw.update(over)
    return build_execution_plan(**kw)


# --- C1: IntentManifest -----------------------------------------------------


def test_c1_valid_manifest_compiles():
    intent = load_intent_manifest(MANIFEST)
    assert intent.deployment_profile == "developer"
    assert intent.silent_fallback is False
    result = __import__("hyba_profiles", fromlist=["compile_assembly"]).compile_assembly(
        intent, signing_key=KEY
    )
    assert result.lock.signature
    assert result.blueprint.resource_plan["exactness"] == "exact"


def test_c1_invalid_manifest_rejected_with_reason():
    bad = yaml.safe_load(MANIFEST.read_text())
    bad["kind"] = "SomethingElse"
    with pytest.raises(IntentRejected) as exc:
        load_intent_manifest(bad)
    assert exc.value.reasons


def test_c1_silent_fallback_rejected():
    bad = yaml.safe_load(MANIFEST.read_text())
    bad["intent"]["execution"]["silentFallback"] = True
    with pytest.raises(IntentRejected) as exc:
        load_intent_manifest(bad)
    assert any("silentFallback" in r for r in exc.value.reasons)


def test_c1_missing_residency_rejected():
    bad = yaml.safe_load(MANIFEST.read_text())
    del bad["intent"]["data"]["residency"]
    with pytest.raises(IntentRejected) as exc:
        load_intent_manifest(bad)
    assert any("residency" in r for r in exc.value.reasons)


# --- C2: AssemblyLock --------------------------------------------------------


def test_c2_assembly_lock_immutable():
    from hyba_profiles import compile_assembly

    intent = load_intent_manifest(MANIFEST)
    result = compile_assembly(intent, signing_key=KEY)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.lock.signature = "tampered"  # type: ignore[misc]


def test_c2_policy_derived_from_lock_not_invented():
    from hyba_profiles import compile_assembly

    intent = load_intent_manifest(MANIFEST)
    result = compile_assembly(intent, signing_key=KEY)
    policies = result.blueprint.policies
    assert policies["private_networking"] == intent.private_networking
    assert policies["customer_managed_keys"] == intent.customer_managed_keys


def test_c2_policy_cannot_weaken_invariant():
    from hyba_profiles import compile_assembly

    intent = dataclasses.replace(load_intent_manifest(MANIFEST), silent_fallback=True)
    result = compile_assembly(intent, signing_key=KEY)
    assert result.blueprint.policies["silent_fallback"] is False


# --- C3: AuthorizedQuery -----------------------------------------------------


def test_c3_unauthorized_operator_rejected_at_planning():
    q = _query(operators=("fold", "smuggle"))
    with pytest.raises(PlanningRejected) as exc:
        _authorize(q)
    assert any("smuggle" in r for r in exc.value.reasons)


def test_c3_unauthorized_exactness_rejected_at_planning():
    q = _query(exactness_mode="approx")
    with pytest.raises(PlanningRejected) as exc:
        _authorize(q)
    assert any("exactness" in r for r in exc.value.reasons)


def test_c3_budget_enforced_before_execution():
    q = _query(estimated=QueryBudget(bytes_moved=10_000))
    with pytest.raises(PlanningRejected) as exc:
        _authorize(q)
    assert any("bytes_moved" in r for r in exc.value.reasons)


# --- C4: ExecutionPlan -------------------------------------------------------


def test_c4_operator_mode_must_match_contract():
    with pytest.raises(PlanningRejected):
        _plan(operator_mode=FoldMode.TRANSFORM)


def test_c4_fold_family_must_match_contract():
    other = dataclasses.replace(_fold(), family="zeckendorf")
    with pytest.raises(PlanningRejected):
        _plan(fold_contract=other)


def test_c4_fallback_marked_when_permitted():
    with pytest.raises(PlanningRejected):
        _plan(fallback_policy=FallbackPolicy(permitted=True, marked=False))
    plan = _plan(fallback_policy=FallbackPolicy(permitted=True, marked=True))
    assert plan.fallback_policy.marked


def test_c4_no_silent_rehydration():
    op = _operator(mode=FoldMode.REHYDRATE)
    with pytest.raises(PlanningRejected) as exc:
        _plan(operator_contract=op, operator_mode=FoldMode.REHYDRATE)
    assert any("rehydrat" in r for r in exc.value.reasons)


def test_c4_valid_plan_builds_and_hashes():
    plan = _plan()
    assert plan.hash() == plan.hash()
    assert plan.backend_target == "cpu-exact"


# --- 12.8: claims.yaml -------------------------------------------------------


def test_claims_registry_loads_and_evaluates_clean():
    registry = load_claims(ROOT / "claims.yaml")
    assert registry.claims
    report = evaluate_release(registry, ROOT)
    assert report.passed, report.violations


def test_verified_claim_requires_baseline_and_command():
    registry = load_claims(ROOT / "claims.yaml")
    broken = dataclasses.replace(registry.claims[0], test_command="", baseline="")
    registry = dataclasses.replace(registry, claims=(broken,) + registry.claims[1:])
    report = evaluate_release(registry, ROOT)
    assert not report.passed
    assert any("test_command" in v for v in report.violations)
    assert any("baseline" in v for v in report.violations)


def test_prohibited_claim_found_in_external_material_fails(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "marketing.md").write_text("we achieve 10 EH/s easily")
    registry = load_claims(ROOT / "claims.yaml")
    report = evaluate_release(registry, tmp_path, external_dirs=("docs",))
    assert not report.passed
    assert any("PROHIBITED" in v for v in report.violations)


# --- 12.9: pairings.yaml -----------------------------------------------------


def test_pairings_registry_loads_spec_lists():
    registry = load_pairings(ROOT / "pairings.yaml")
    assert len(registry.verified) == 10
    assert len(registry.prohibited) == 6
    assert len(registry.refuted_results) == 6


def test_new_pairing_requires_verified_record():
    registry = load_pairings(ROOT / "pairings.yaml")
    candidate = PairingRecord(name="new_pair", pair=("a", "b"), status=PairingStatus.HYPOTHESIS)
    with pytest.raises(PairingRejected) as exc:
        admit_pairing(registry, candidate)
    assert any("VERIFIED" in r for r in exc.value.reasons)


def test_verified_pairing_needs_complete_test_record():
    registry = load_pairings(ROOT / "pairings.yaml")
    candidate = PairingRecord(
        name="fresh_pair",
        pair=("fibonacci", "lucas"),
        status=PairingStatus.VERIFIED,
    )
    with pytest.raises(PairingRejected):
        admit_pairing(registry, candidate)
    admitted = admit_pairing(
        registry,
        PairingRecord(
            name="fresh_pair",
            pair=("fibonacci", "lucas"),
            status=PairingStatus.VERIFIED,
            pairing_test=PairingTest(
                test_command="pytest x",
                baseline="b",
                reproduce_command="pytest x",
            ),
        ),
    )
    assert admitted.name == "fresh_pair"


def test_prohibited_pairing_blocked():
    registry = load_pairings(ROOT / "pairings.yaml")
    banned = registry.prohibited[0]
    candidate = PairingRecord(
        name=banned.name,
        pair=banned.pair,
        status=PairingStatus.VERIFIED,
        pairing_test=PairingTest("t", "b", "r"),
    )
    with pytest.raises(PairingRejected):
        admit_pairing(registry, candidate)


# --- 12.10: signed deployment manifest ---------------------------------------


def test_shipped_manifest_is_signed_and_verifies():
    manifest = load_manifest(ROOT / "manifests" / "pythia.platform.signed.json")
    key = (ROOT / "manifests" / "dev-signing.key").read_bytes()
    assert verify_manifest(manifest, key)


def test_tampered_manifest_fails_verification():
    manifest = load_manifest(ROOT / "manifests" / "pythia.platform.signed.json")
    key = (ROOT / "manifests" / "dev-signing.key").read_bytes()
    tampered = dataclasses.replace(manifest, version="9.9.9")
    assert not verify_manifest(tampered, key)


def test_unsigned_manifest_fails_closed():
    manifest = load_manifest(ROOT / "manifests" / "pythia.platform.signed.json")
    key = (ROOT / "manifests" / "dev-signing.key").read_bytes()
    unsigned = dataclasses.replace(manifest, signature="")
    assert not verify_manifest(unsigned, key)
    assert not verify_manifest(manifest, b"")


def test_disconnected_service_rejected():
    manifest = load_manifest(ROOT / "manifests" / "pythia.platform.signed.json")
    broken = dataclasses.replace(
        manifest,
        services=(
            ServiceBinding(
                name="rogue",
                object_model="other",
                policy_engine="hyba-policy",
                lineage_store="cassini-ledger",
            ),
        ),
    )
    with pytest.raises(ManifestRejected):
        sign_manifest(broken, KEY)


def test_compile_deployment_is_deterministic():
    manifest = load_manifest(ROOT / "manifests" / "pythia.platform.signed.json")
    assert compile_deployment(manifest) == compile_deployment(manifest)
    assert manifest.compile_hash == compile_deployment(manifest)["plan_hash"]
