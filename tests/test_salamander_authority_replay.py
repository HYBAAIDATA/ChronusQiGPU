"""Boundary/replay UNIT evidence; not production-composition qualification.

AL HARAS signing, verification and audit are actual repository components.
The actuator below is intentionally a unit fixture and cannot certify a voyage.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import time

import pytest

from al_haras import ALHaras, GuardianPolicy, HashChainAudit, SubscriptionAuthority, SubscriptionClaims
from salamander.authority import ALHarasActionAuthorizer
from salamander.control_plane import ActionRegistry, AutonomicControlPlane, EvidenceLedger, FailClosed, RecoveryPlan, RecoveryStep
from salamander.models import ActionKind, ActionRequest


def request(action_id="one", *, tenant="tenant-a", key="same"):
    return ActionRequest(action_id, ActionKind.REPLAN, "owner", tenant, "subject", "unit-replay",
                         {"max_attempts": 1}, idempotency_key=key, actor_id="actor")


def fixture(*, ledger=None, max_recoveries=1):
    signer = SubscriptionAuthority({"unit": b"unit-only-test-material-32-bytes!!"}, issuer="unit")
    now = int(time.time())
    tokens = {tenant: signer.issue(SubscriptionClaims(
        subscription_id="sub:"+tenant, tenant_id=tenant, issuer="unit", key_id="unit",
        capabilities=("hyba.security",), actors=("actor",), not_before=now-1, expires_at=now+300,
    )) for tenant in ("tenant-a", "tenant-b")}
    guardian = ALHaras(signer, GuardianPolicy(version="unit-policy", allowed_operations=frozenset(
        {"salamander.replan", "salamander.rollback"})), HashChainAudit())
    adapter = ALHarasActionAuthorizer(guardian, lambda r: tokens[r.tenant_id])
    calls = []
    registry = ActionRegistry()
    registry.register("owner", {ActionKind.REPLAN, ActionKind.ROLLBACK},
                      lambda r: calls.append(r.action_id) or {}, verifier_id="unit-independent-probe",
                      verifier=lambda r, _: {"verified": True, "evidence_ref": "unit-probe:"+r.action_id})
    plane = AutonomicControlPlane(registry=registry, ledger=ledger, authorizer=adapter,
                                  max_recoveries_per_target=max_recoveries)
    return plane, calls, adapter


def test_authorisation_cannot_be_disabled():
    with pytest.raises(FailClosed, match="cannot be disabled"):
        AutonomicControlPlane(registry=ActionRegistry(), require_authorization=False)


def test_named_fake_authorizer_is_not_governance():
    plane, calls, _ = fixture()
    plane.authorizer = lambda _: {"allowed": True, "authority": "AL_HARAS", "evidence_id": "fake"}
    with pytest.raises(FailClosed, match="AUTHORIZER_UNAVAILABLE"):
        plane.execute(request())
    assert calls == []


def test_direct_registry_call_cannot_skip_authorisation():
    plane, calls, _ = fixture()
    with pytest.raises(FailClosed, match="requires bound"):
        plane.registry.execute(request())
    assert calls == []


def test_receipt_cannot_authorize_different_target_or_tenant():
    plane, calls, adapter = fixture()
    receipt = adapter(request())
    for wrong in (replace(request(), target="other"), replace(request(), tenant_id="tenant-b")):
        with pytest.raises(FailClosed, match="forged or unbound"):
            plane.registry.execute(wrong, authorization=receipt)
    assert calls == []


def test_receipt_is_single_use():
    plane, calls, adapter = fixture()
    receipt = adapter(request())
    plane.registry.execute(request(), authorization=receipt)
    with pytest.raises(FailClosed, match="forged or unbound"):
        plane.registry.execute(request(), authorization=receipt)
    assert calls == ["one"]


def test_expired_receipt_cannot_act(monkeypatch):
    plane, calls, adapter = fixture()
    receipt = adapter(request())
    expires = adapter._grants[receipt["evidence_id"]][1]
    monkeypatch.setattr("salamander.authority.time.time", lambda: expires)
    with pytest.raises(FailClosed, match="expired"):
        plane.registry.execute(request(), authorization=receipt)
    assert calls == []


def test_corrupt_real_guardian_audit_cannot_act():
    plane, calls, adapter = fixture()
    receipt = adapter(request())
    adapter.guardian.audit._records[0]["event"]["actor"] = "other"
    with pytest.raises(FailClosed, match="forged or unbound"):
        plane.registry.execute(request(), authorization=receipt)
    assert calls == []


def test_idempotency_is_contextual_not_cross_tenant():
    plane, calls, _ = fixture()
    a, b = request(), request("two", tenant="tenant-b")
    plane.execute(a)
    plane.execute(b)
    assert plane.execute(a).action_id == "one"
    assert calls == ["one", "two"]
    with pytest.raises(FailClosed, match="different request"):
        plane.execute(replace(a, target="other"))


def test_simultaneous_duplicate_only_dispatches_once():
    plane, calls, _ = fixture()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: plane.execute(request()), range(4)))
    assert all(r.verified for r in results)
    assert calls == ["one"]


def test_budget_and_completed_action_survive_ledger_reconstruction():
    plane, calls, _ = fixture()
    plan = RecoveryPlan("recovery", "tenant-a", "subject", (RecoveryStep("step", request()),),
                        1, time.time_ns()+1_000_000_000)
    assert plane.recover(plan)[0].verified
    reopened = EvidenceLedger.from_payload(plane.ledger.to_payload())
    fresh, fresh_calls, _ = fixture(ledger=reopened)
    assert fresh.execute(request()).verified
    assert fresh_calls == []
    with pytest.raises(FailClosed, match="budget exhausted"):
        fresh.recover(replace(plan, recovery_id="second"))
    assert fresh.ledger.records[-1]["kind"] == "recovery-escalated"
    assert calls == ["one"]


def test_crash_after_effect_before_result_cannot_replay_effect():
    def sink(record):
        if record["kind"] == "action-result":
            raise OSError("unit-injected-result-write-failure")
    plane, calls, _ = fixture(ledger=EvidenceLedger(sink))
    with pytest.raises(OSError):
        plane.execute(request())
    assert calls == ["one"]
    fresh, fresh_calls, _ = fixture(ledger=EvidenceLedger.from_payload(plane.ledger.to_payload()))
    with pytest.raises(FailClosed, match="uncertain"):
        fresh.execute(request())
    assert fresh_calls == []


def test_corrupt_healing_chain_fails_reconstruction():
    plane, _, _ = fixture()
    plane.execute(request())
    ledger = EvidenceLedger.from_payload(plane.ledger.to_payload())
    ledger._records[0]["payload"]["allowed"] = False
    with pytest.raises(FailClosed, match="digest mismatch"):
        fixture(ledger=ledger)


def test_chain_head_mismatch_is_not_ignored():
    plane, _, _ = fixture()
    plane.execute(request())
    plane.ledger._head = "0" * 64
    with pytest.raises(FailClosed, match="head mismatch"):
        fixture(ledger=plane.ledger)


def test_failed_rollback_is_critical_not_accepted():
    plane, calls, _ = fixture()
    # Unit rejection probe rejects both primary and rollback. The coordinator
    # must not return a completed recovery when independent restoration fails.
    kinds, handler, verifier_id, _ = plane.registry._handlers["owner"]
    plane.registry._handlers["owner"] = (kinds, handler, verifier_id,
        lambda *_: {"verified": False, "error": "unit-rejected"})
    rollback = replace(request("rollback", key="rollback"), kind=ActionKind.ROLLBACK)
    plan = RecoveryPlan("failed-rollback", "tenant-a", "subject",
                        (RecoveryStep("step", request(), rollback=rollback),),
                        2, time.time_ns()+1_000_000_000)
    with pytest.raises(FailClosed, match="rollback failed independent verification"):
        plane.recover(plan)
    assert calls == ["one", "rollback"]
