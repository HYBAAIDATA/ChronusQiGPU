"""Tests for Euclid / Salamander Native Capability Fabric.

Validates:
- Manifest registration, schemas, and resource envelopes.
- Profile-based authorization boundaries (INTERNAL_RESEARCH vs SHARED_RESTRICTED).
- Fail-closed security: dangerous write/exec capabilities rejected under SHARED_RESTRICTED.
- Deterministic execution receipts binding inputs, outputs, and findings.
- Runtime budget enforcement and audit log custody.
- Direct SalamanderEngine profile and capability execution integration.
"""

from __future__ import annotations

import time
import pytest
from pathlib import Path

from Intelligence.capability_fabric import (
    AuthorizationDenied,
    CapabilityExecutionError,
    CapabilityExecutionReceipt,
    CapabilityManifest,
    CapabilityPermissions,
    CapabilityRegistrationError,
    CapabilityRegistry,
    DeterminismClass,
    ExecutionProfile,
    ResourceBudget,
    SideEffectClass,
)
from Intelligence.salamander import SalamanderEngine


def test_manifest_validation_contract() -> None:
    """CapabilityManifest enforces non-empty strings and valid configurations."""
    with pytest.raises(CapabilityRegistrationError, match="capability_id"):
        CapabilityManifest(
            capability_id="",
            version="1.0.0",
            source_provenance="tests",
            description="invalid",
            permissions=CapabilityPermissions(),
            resource_budget=ResourceBudget(),
            supported_operations=("test",),
            determinism=DeterminismClass.DETERMINISTIC,
            side_effects=SideEffectClass.READ_ONLY,
            verification_strategy="unit",
        )

    with pytest.raises(CapabilityRegistrationError, match="version"):
        CapabilityManifest(
            capability_id="valid-id",
            version="",
            source_provenance="tests",
            description="invalid",
            permissions=CapabilityPermissions(),
            resource_budget=ResourceBudget(),
            supported_operations=("test",),
            determinism=DeterminismClass.DETERMINISTIC,
            side_effects=SideEffectClass.READ_ONLY,
            verification_strategy="unit",
        )

    with pytest.raises(CapabilityRegistrationError, match="source_provenance"):
        CapabilityManifest(
            capability_id="valid-id",
            version="1.0.0",
            source_provenance="",
            description="invalid",
            permissions=CapabilityPermissions(),
            resource_budget=ResourceBudget(),
            supported_operations=("test",),
            determinism=DeterminismClass.DETERMINISTIC,
            side_effects=SideEffectClass.READ_ONLY,
            verification_strategy="unit",
        )


def test_registry_registration_and_duplicate_rejection() -> None:
    """Registry accepts valid manifests and rejects duplicates or non-callables."""
    registry = CapabilityRegistry()
    manifest = CapabilityManifest(
        capability_id="sample-cap",
        version="1.0.0",
        source_provenance="Intelligence/sample.py",
        description="Sample capability",
        permissions=CapabilityPermissions(),
        resource_budget=ResourceBudget(),
        supported_operations=("run",),
        determinism=DeterminismClass.DETERMINISTIC,
        side_effects=SideEffectClass.READ_ONLY,
        verification_strategy="exact",
    )

    with pytest.raises(CapabilityRegistrationError, match="callable"):
        registry.register(manifest, adapter_fn="not-callable")  # type: ignore

    registry.register(manifest, adapter_fn=lambda **kwargs: {"ok": True})

    with pytest.raises(CapabilityRegistrationError, match="already registered"):
        registry.register(manifest, adapter_fn=lambda **kwargs: {"ok": True})

    assert registry.get_manifest("sample-cap") == manifest
    assert registry.unregister("sample-cap") is True
    assert registry.unregister("sample-cap") is False
    assert registry.get_manifest("sample-cap") is None


def test_profile_authorization_boundaries() -> None:
    """Profile enforcement: SHARED_RESTRICTED strictly forbids dangerous permissions."""
    read_only_perms = CapabilityPermissions(
        can_read_repository=True,
        can_write_repository=False,
        allowed_profiles=(ExecutionProfile.INTERNAL_RESEARCH, ExecutionProfile.SHARED_RESTRICTED),
    )
    assert read_only_perms.is_permitted_for(ExecutionProfile.INTERNAL_RESEARCH) is True
    assert read_only_perms.is_permitted_for(ExecutionProfile.SHARED_RESTRICTED) is True

    # Write-capable permission
    write_perms = CapabilityPermissions(
        can_read_repository=True,
        can_write_repository=True,
        allowed_profiles=(ExecutionProfile.INTERNAL_RESEARCH, ExecutionProfile.SHARED_RESTRICTED),
    )
    assert write_perms.is_permitted_for(ExecutionProfile.INTERNAL_RESEARCH) is True
    # In SHARED_RESTRICTED profile, write permission is prohibited by rule
    assert write_perms.is_permitted_for(ExecutionProfile.SHARED_RESTRICTED) is False

    # Spawn process permission
    process_perms = CapabilityPermissions(
        can_read_repository=True,
        can_spawn_process=True,
        allowed_profiles=(ExecutionProfile.INTERNAL_RESEARCH, ExecutionProfile.SHARED_RESTRICTED),
    )
    assert process_perms.is_permitted_for(ExecutionProfile.SHARED_RESTRICTED) is False


def test_dispatch_authorization_gate_and_receipt() -> None:
    """Dispatching a capability under SHARED_RESTRICTED raises AuthorizationDenied if unauthorized."""
    registry = CapabilityRegistry()
    priv_manifest = CapabilityManifest(
        capability_id="privileged-mutation",
        version="1.0.0",
        source_provenance="Intelligence/mutation.py",
        description="Internal-only mutation",
        permissions=CapabilityPermissions(
            can_read_repository=True,
            can_write_repository=True,
            allowed_profiles=(ExecutionProfile.INTERNAL_RESEARCH,),
        ),
        resource_budget=ResourceBudget(),
        supported_operations=("mutate",),
        determinism=DeterminismClass.DETERMINISTIC,
        side_effects=SideEffectClass.ISOLATED_MUTATION,
        verification_strategy="receipt",
    )
    registry.register(priv_manifest, adapter_fn=lambda **kwargs: {"mutated": True})

    # Dispatch under SHARED_RESTRICTED must fail at authorization
    with pytest.raises(AuthorizationDenied, match="not permitted under execution profile 'shared'"):
        registry.dispatch(
            "privileged-mutation",
            profile=ExecutionProfile.SHARED_RESTRICTED,
            target="some_target",
        )

    # Failed dispatch must still generate an audit receipt with status FAILED
    audit = registry.get_audit_log()
    assert len(audit) == 1
    assert audit[0].capability_id == "privileged-mutation"
    assert audit[0].status == "FAILED"
    assert audit[0].profile == "shared"

    # Dispatch under INTERNAL_RESEARCH succeeds and produces deterministic receipt
    output, receipt = registry.dispatch(
        "privileged-mutation",
        profile=ExecutionProfile.INTERNAL_RESEARCH,
        target="some_target",
    )
    assert output == {"mutated": True}
    assert receipt.status == "SUCCESS"
    assert receipt.profile == "internal"
    assert receipt.duration_seconds >= 0.0
    assert len(receipt.receipt_sha256) == 64
    assert len(registry.get_audit_log()) == 2


def test_runtime_budget_exhaustion() -> None:
    """Capabilities exceeding runtime budget raise CapabilityExecutionError."""
    registry = CapabilityRegistry()
    slow_manifest = CapabilityManifest(
        capability_id="slow-operation",
        version="1.0.0",
        source_provenance="Intelligence/slow.py",
        description="Slow capability",
        permissions=CapabilityPermissions(
            allowed_profiles=(ExecutionProfile.INTERNAL_RESEARCH,),
        ),
        resource_budget=ResourceBudget(max_runtime_seconds=0.05),
        supported_operations=("sleep",),
        determinism=DeterminismClass.DETERMINISTIC,
        side_effects=SideEffectClass.READ_ONLY,
        verification_strategy="none",
    )

    def _slow_adapter(**kwargs: Any) -> Any:
        time.sleep(0.08)
        return {"done": True}

    registry.register(slow_manifest, adapter_fn=_slow_adapter)

    with pytest.raises(CapabilityExecutionError, match="exceeded runtime budget"):
        registry.dispatch("slow-operation", profile=ExecutionProfile.INTERNAL_RESEARCH)


def test_schema_requirement_enforcement() -> None:
    """Missing required schema parameters are rejected prior to execution."""
    registry = CapabilityRegistry()
    manifest = CapabilityManifest(
        capability_id="schema-strict",
        version="1.0.0",
        source_provenance="Intelligence/schema.py",
        description="Strict capability",
        permissions=CapabilityPermissions(
            allowed_profiles=(ExecutionProfile.INTERNAL_RESEARCH,),
        ),
        resource_budget=ResourceBudget(),
        supported_operations=("run",),
        determinism=DeterminismClass.DETERMINISTIC,
        side_effects=SideEffectClass.READ_ONLY,
        verification_strategy="schema",
        input_schema={"required": ["mandatory_param"]},
    )
    registry.register(manifest, adapter_fn=lambda **kwargs: {"echo": kwargs})

    with pytest.raises(TypeError, match="missing required argument: 'mandatory_param'"):
        registry.dispatch("schema-strict", profile=ExecutionProfile.INTERNAL_RESEARCH)

    out, receipt = registry.dispatch(
        "schema-strict",
        profile=ExecutionProfile.INTERNAL_RESEARCH,
        mandatory_param="valid_val",
    )
    assert out == {"echo": {"mandatory_param": "valid_val"}}
    assert receipt.status == "SUCCESS"


def test_salamander_engine_capability_fabric_integration() -> None:
    """SalamanderEngine exposes capabilities and enforces profile restrictions."""
    engine = SalamanderEngine()

    # Default profile is INTERNAL_RESEARCH
    assert engine.profile == ExecutionProfile.INTERNAL_RESEARCH

    # Native capabilities are registered
    manifests = engine.capability_registry.list_capabilities()
    cap_ids = {m.capability_id for m in manifests}
    assert "repository-review" in cap_ids
    assert "isolated-repair" in cap_ids
    assert "proof-conjecture" in cap_ids
    assert "repair-learning-query" in cap_ids

    # Query learning ledger capability via direct execute_capability
    res, receipt = engine.execute_capability(
        "repair-learning-query",
        issue_type="ast_defect",
        problem_signature="test_sig",
    )
    assert res["issue_type"] == "ast_defect"
    assert "empirical_success_rate" in res
    assert receipt.status == "SUCCESS"

    # Switch profile to SHARED_RESTRICTED
    engine.profile = ExecutionProfile.SHARED_RESTRICTED

    # In SHARED_RESTRICTED, read-only capabilities are allowed
    shared_caps = {
        m.capability_id
        for m in engine.capability_registry.list_capabilities(profile=engine.profile)
    }
    assert "repository-review" in shared_caps
    assert "proof-conjecture" in shared_caps
    assert "repair-learning-query" in shared_caps
    assert "isolated-repair" not in shared_caps
    assert "source-repair" not in shared_caps

    # Attempting to execute isolated-repair under SHARED_RESTRICTED raises AuthorizationDenied
    with pytest.raises(AuthorizationDenied, match="not permitted under execution profile 'shared'"):
        engine.execute_capability(
            "isolated-repair",
            target_file=Path("core_engine/sample.py"),
            replacement_code="x = 1\n",
            defect_probe=lambda p: False,
            validator_fn=lambda b, c, p: True,
            authorization_token="INTERNAL_RESEARCH_AUTONOMOUS_OPERATOR",
        )
