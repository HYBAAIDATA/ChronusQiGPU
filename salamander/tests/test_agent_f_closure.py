from __future__ import annotations

import time

import pytest

from al_haras import (
    ALHaras,
    GuardianPolicy,
    HashChainAudit,
    SubscriptionAuthority,
    SubscriptionClaims,
)
from salamander.authority import build_authorized_control_plane
from salamander.control_plane import ActionRegistry, FailClosed, RecoveryPlan, RecoveryStep
from salamander.models import ActionKind, ActionRequest


def _request(
    action_id: str,
    kind: ActionKind = ActionKind.REPLAN,
    *,
    handler: str = "bounded",
    tenant: str = "tenant-a",
    target: str = "device:gpu0",
) -> ActionRequest:
    return ActionRequest(
        action_id=action_id,
        kind=kind,
        handler=handler,
        tenant_id=tenant,
        target=target,
        reason="agent-f-closure-test",
        bounds={"max_attempts": 1},
        idempotency_key=f"idem:{action_id}",
        actor_id="agent-f",
    )


def _guardian(*operations: str) -> tuple[ALHaras, str]:
    secret = b"agent-f-test-key-material-" + b"x" * 16
    authority = SubscriptionAuthority({"k1": secret}, issuer="agent-f-test")
    now = int(time.time())
    claims = SubscriptionClaims(
        subscription_id="sub-1",
        tenant_id="tenant-a",
        issuer="agent-f-test",
        key_id="k1",
        capabilities=("hyba.security",),
        actors=("agent-f",),
        not_before=now - 5,
        expires_at=now + 3600,
    )
    token = authority.issue(claims)
    guardian = ALHaras(
        authority,
        GuardianPolicy(
            version="agent-f-test-v1",
            allowed_operations=frozenset(operations),
        ),
        HashChainAudit(),
    )
    return guardian, token


def _registry(*, reject_primary: bool = False) -> ActionRegistry:
    registry = ActionRegistry()

    def handler(request: ActionRequest):
        return {
            "post_observation": (
                "restored" if request.kind is ActionKind.ROLLBACK else "changed"
            )
        }

    def verifier(request: ActionRequest, response):
        if request.kind is ActionKind.ROLLBACK:
            return {
                "verified": response.get("post_observation") == "restored",
                "evidence_ref": "probe:rollback-restored",
                "observations": dict(response),
            }
        if reject_primary:
            return {
                "verified": False,
                "error": "postcondition rejected",
                "observations": dict(response),
            }
        return {
            "verified": response.get("post_observation") == "changed",
            "evidence_ref": "probe:changed",
            "observations": dict(response),
        }

    registry.register(
        "bounded",
        {ActionKind.REPLAN, ActionKind.ROLLBACK},
        handler,
        verifier_id="independent-agent-f-probe",
        verifier=verifier,
    )
    return registry


def test_production_constructor_requires_real_al_haras_verdict():
    guardian, token = _guardian("salamander.replan")
    plane = build_authorized_control_plane(
        registry=_registry(),
        guardian=guardian,
        token_provider=lambda _request: token,
    )
    result = plane.execute(_request("a1"))
    assert result.verified is True
    assert any(record["kind"] == "action-authorization" for record in plane.ledger.records)

    denied = build_authorized_control_plane(
        registry=_registry(),
        guardian=guardian,
        token_provider=lambda _request: "not-a-token",
    )
    with pytest.raises(FailClosed, match="AL HARAS authorization denied"):
        denied.execute(_request("a2"))


def test_recovery_reject_executes_authorized_verified_rollback():
    guardian, token = _guardian("salamander.replan", "salamander.rollback")
    plane = build_authorized_control_plane(
        registry=_registry(reject_primary=True),
        guardian=guardian,
        token_provider=lambda _request: token,
    )
    primary = _request("primary")
    rollback = _request("rollback", ActionKind.ROLLBACK)
    plan = RecoveryPlan(
        recovery_id="recovery-1",
        tenant_id="tenant-a",
        target="device:gpu0",
        steps=(RecoveryStep("step-1", primary, rollback=rollback),),
        max_actions=2,
        deadline_ns=time.time_ns() + 10_000_000_000,
    )

    results = plane.recover(plan)

    assert [result.status for result in results] == ["UNVERIFIED", "VERIFIED"]
    assert results[-1].action_id == "rollback"
    assert any(
        record["kind"] == "recovery-rollback-result"
        and record["payload"]["rollback_verified"] is True
        for record in plane.ledger.records
    )


def test_recovery_fails_closed_when_changed_state_has_no_rollback():
    guardian, token = _guardian("salamander.replan")
    plane = build_authorized_control_plane(
        registry=_registry(reject_primary=True),
        guardian=guardian,
        token_provider=lambda _request: token,
    )
    plan = RecoveryPlan(
        recovery_id="recovery-2",
        tenant_id="tenant-a",
        target="device:gpu0",
        steps=(RecoveryStep("step-1", _request("primary-no-rollback")),),
        max_actions=1,
        deadline_ns=time.time_ns() + 10_000_000_000,
    )

    with pytest.raises(FailClosed, match="has no rollback"):
        plane.recover(plan)
    assert any(
        record["kind"] == "recovery-rollback-required"
        for record in plane.ledger.records
    )


def test_recovery_plan_cannot_smuggle_foreign_tenant_or_target():
    guardian, token = _guardian("salamander.replan")
    plane = build_authorized_control_plane(
        registry=_registry(),
        guardian=guardian,
        token_provider=lambda _request: token,
    )
    foreign = _request("foreign", target="device:other")
    plan = RecoveryPlan(
        recovery_id="recovery-3",
        tenant_id="tenant-a",
        target="device:gpu0",
        steps=(RecoveryStep("step-1", foreign),),
        max_actions=1,
        deadline_ns=time.time_ns() + 10_000_000_000,
    )
    with pytest.raises(FailClosed, match="target does not match"):
        plane.recover(plan)
