"""Real-owner capability seams, not full deployment/security certification.

No replacement guardian or Salamander constructor is installed. TURING's actual
read-only capability probe is used for requalification. Keys/tokens are local
fixtures, not enterprise entitlements. No physical device is involved.
"""

from __future__ import annotations

import json
import time

import pytest

from al_haras import (
    ALHaras,
    GuardianPolicy,
    HashChainAudit,
    SubscriptionAuthority,
    SubscriptionClaims,
)
from euclid.contracts import Health
from euclid.organ_adapters.specialists import TuringQuantumOrgan
from euclid.runtime import EuclidRuntime
from salamander.control_plane import ActionRegistry, FailClosed
from salamander.models import ActionKind


@pytest.fixture
def boundary(tmp_path):
    authority = SubscriptionAuthority(
        {"fixture": b"local-capability-test-key-only-32bytes"}, "capability-test"
    )
    guardian = ALHaras(
        authority,
        GuardianPolicy(
            version="fixture-only",
            allowed_operations=frozenset(
                {
                    "turing.run-program",
                    "turing.capability-matrix",
                    "salamander.requalify",
                }
            ),
        ),
        HashChainAudit(tmp_path / "guardian.jsonl"),
    )
    runtime = EuclidRuntime(creator_id="tenant-a", state_dir=tmp_path / "euclid")
    runtime.guardian = guardian
    runtime.register_specialist("turing", TuringQuantumOrgan())
    runtime.rights.grant("tenant-a", "turing", "turing.request", "dispatch")
    runtime._organ_probes = {"turing": {"operation": "capability-matrix"}}
    try:
        yield runtime, guardian
    finally:
        runtime.close()


def token(guardian, *, tenant="tenant-a", expired=False, jti=None):
    now = int(time.time())
    return guardian.authority.issue(
        SubscriptionClaims(
            "fixture-subscription",
            tenant,
            "capability-test",
            "fixture",
            ("hyba.security",),
            ("operator",),
            now - 10,
            now - 1 if expired else now + 300,
            jti=jti,
        )
    )


def wire_actuation(runtime, guardian, provider):
    actions = ActionRegistry()
    actions.register(
        "requalify-organ",
        {ActionKind.REQUALIFY},
        runtime._requalify_organ,
        verifier_id="euclid.delegator-redispatch",
        verifier=runtime._verify_requalified,
    )
    runtime.autonomic = runtime._compose_actuation_plane(
        actions,
        guardian,
        provider,
        ledger_sink=lambda record: runtime.evidence.append("salamander-action", record),
    )


def dispatch(runtime, credential):
    return runtime.dispatch_specialist(
        "turing",
        {"operation": "capability-matrix"},
        tenant_id="tenant-a",
        actor="operator",
        subscription_token=credential,
    )


def test_real_guarded_turing_execution_preserves_owner_and_program_identity(boundary):
    runtime, guardian = boundary
    from turing_universal_quantum_computer.backends import Program

    program = Program(1).then("x", 0)
    answer = runtime.dispatch_specialist(
        "turing",
        {"operation": "run-program", "program": program.to_dict(), "prefer": "exact_algebraic"},
        tenant_id="tenant-a",
        actor="operator",
        subscription_token=token(guardian),
    )
    assert answer["allowed"] is True
    result = answer["result"]
    assert result["owner"] == "TURING"
    assert result["executed"] is True
    assert result["truth_class"] == "exact"
    assert result["program_digest"] == program.digest()
    assert result["measured_qpu"] is False
    assert answer["governance"]["evidence_id"]
    runtime.evidence.verify()
    # This backend result is NOT a SharedTuring certificate/custody acceptance.


@pytest.mark.parametrize("case", ["missing", "wrong-tenant", "expired"])
def test_guardian_denial_never_dispatches_turing(boundary, case):
    runtime, guardian = boundary
    credential = {
        "missing": "",
        "wrong-tenant": token(guardian, tenant="tenant-b"),
        "expired": token(guardian, expired=True),
    }[case]
    answer = dispatch(runtime, credential)
    assert answer["allowed"] is False
    assert not any(r.kind == "delegation-result" for r in runtime.evidence.records)


def test_one_use_entitlement_does_not_repeat_dispatch(boundary):
    runtime, guardian = boundary
    credential = token(guardian, jti="one-dispatch")
    assert dispatch(runtime, credential)["allowed"] is True
    assert dispatch(runtime, credential)["allowed"] is False
    assert sum(r.kind == "delegation-result" for r in runtime.evidence.records) == 1
    # AL HARAS nonce tracking here is process-local, not a cluster guarantee.


def test_missing_provider_keeps_real_requalification_closed(boundary):
    runtime, guardian = boundary
    wire_actuation(runtime, guardian, None)
    runtime.registry.get("turing").health = Health.DEGRADED
    with pytest.raises(FailClosed, match="token provider"):
        runtime.heal_organ("turing", reason="fixture", actor="operator")
    assert runtime.registry.get("turing").health is Health.DEGRADED


def test_real_authorized_heal_adapts_provider_once_without_evidence_secret(boundary):
    runtime, guardian = boundary
    credential = token(guardian)
    calls = []

    def provider(tenant, actor):
        calls.append((tenant, actor))
        return credential

    wire_actuation(runtime, guardian, provider)
    runtime.registry.get("turing").health = Health.DEGRADED
    result = runtime.heal_organ("turing", reason="fixture", actor="operator")
    assert result.verified is True
    assert calls == [("tenant-a", "operator")]
    assert runtime.registry.get("turing").health is Health.HEALTHY
    assert credential not in json.dumps(runtime.evidence.to_payload())
    assert credential not in json.dumps(runtime.autonomic.ledger.records)
    runtime.evidence.verify()


@pytest.mark.parametrize("case", ["unavailable", "invalid", "wrong-tenant"])
def test_real_actuation_denies_before_requalification(boundary, case):
    runtime, guardian = boundary

    def provider(tenant, actor):
        if case == "unavailable":
            raise OSError("fixture credential service unavailable")
        return "invalid" if case == "invalid" else token(guardian, tenant="tenant-b")

    wire_actuation(runtime, guardian, provider)
    runtime.registry.get("turing").health = Health.DEGRADED
    with pytest.raises(FailClosed, match="AL HARAS authorization denied"):
        runtime.heal_organ("turing", reason="fixture", actor="operator")
    assert runtime.registry.get("turing").health is Health.DEGRADED
    assert not any(r.kind == "delegation-result" for r in runtime.evidence.records)
