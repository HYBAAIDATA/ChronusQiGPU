"""EUCLID's real AL HARAS / Salamander actuation seam.

The obsolete whole-module authority doubles are intentionally gone. Positive
checks use a signed local fixture token, the canonical authorizer/control plane,
and TURING's actual read-only probe. They do not certify a deployed service.
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
def runtime(tmp_path):
    authority = SubscriptionAuthority(
        {"fixture": b"euclid-actuation-local-fixture-key-32"}, "euclid-actuation-test"
    )
    guardian = ALHaras(
        authority,
        GuardianPolicy(version="fixture", allowed_operations=frozenset({"salamander.requalify"})),
        HashChainAudit(tmp_path / "guardian.jsonl"),
    )
    now = int(time.time())
    credential = authority.issue(
        SubscriptionClaims(
            "fixture",
            "c",
            "euclid-actuation-test",
            "fixture",
            ("hyba.security",),
            ("ops-1",),
            now - 5,
            now + 300,
        )
    )
    rt = EuclidRuntime(creator_id="c", state_dir=tmp_path / "euclid")
    rt.register_specialist("turing", TuringQuantumOrgan())
    rt.rights.grant("c", "turing", "turing.request", "dispatch")
    rt._organ_probes = {"turing": {"operation": "capability-matrix"}}
    try:
        yield rt, guardian, credential
    finally:
        rt.close()


def wire(rt, guardian, provider):
    actions = ActionRegistry()
    actions.register(
        "requalify-organ",
        {ActionKind.REQUALIFY},
        rt._requalify_organ,
        verifier_id="euclid.delegator-redispatch",
        verifier=rt._verify_requalified,
    )
    rt.autonomic = rt._compose_actuation_plane(
        actions,
        guardian,
        provider,
        ledger_sink=lambda record: rt.evidence.append("salamander-action", record),
    )


def assert_no_dispatch(rt):
    assert not any(r.kind == "delegation-result" for r in rt.evidence.records)


def test_no_guardian_actuation_refused_before_handler(runtime):
    rt, _, _ = runtime
    wire(rt, None, None)
    with pytest.raises(FailClosed, match="guardian"):
        rt.heal_organ("turing", reason="degraded", actor="ops-1")
    assert_no_dispatch(rt)
    assert any(r.kind == "salamander-actuation-unavailable" for r in rt.evidence.records)


def test_guardian_without_token_provider_refused(runtime):
    rt, guardian, _ = runtime
    wire(rt, guardian, None)
    with pytest.raises(FailClosed, match="token provider"):
        rt.heal_organ("turing", reason="degraded", actor="ops-1")
    assert_no_dispatch(rt)


def test_missing_actor_refused_before_handler(runtime):
    rt, guardian, credential = runtime
    wire(rt, guardian, lambda tenant, actor: credential)
    for actor in (None, "", "   "):
        with pytest.raises(FailClosed, match="actor"):
            rt.heal_organ("turing", reason="degraded", actor=actor)
    assert_no_dispatch(rt)


def test_authorized_heal_executes_and_verifies(runtime):
    rt, guardian, credential = runtime
    wire(rt, guardian, lambda tenant, actor: credential)
    rt.registry.get("turing").health = Health.DEGRADED
    result = rt.heal_organ("turing", reason="degraded", actor="ops-1")
    assert result.verified is True
    assert rt.registry.get("turing").health is Health.HEALTHY
    assert any(
        r.kind == "heal-attempt" and r.payload["actor"] == "ops-1" for r in rt.evidence.records
    )
    assert any(r["kind"] == "action-authorization" for r in rt.autonomic.ledger.records)


def test_constructor_refusal_leaves_actuation_unavailable(runtime, monkeypatch):
    import salamander.authority

    def refusing(**kwargs):
        raise PermissionError("fixture constructor refusal")

    # Only this negative path injects a failure. The actual authority module
    # and canonical authorizer class remain available to the observe-only plane.
    monkeypatch.setattr(salamander.authority, "build_authorized_control_plane", refusing)
    rt, guardian, credential = runtime
    wire(rt, guardian, lambda tenant, actor: credential)
    with pytest.raises(FailClosed, match="unavailable"):
        rt.heal_organ("turing", reason="degraded", actor="ops-1")
    assert_no_dispatch(rt)


def test_token_never_enters_evidence_or_payload(runtime):
    rt, guardian, credential = runtime
    wire(rt, guardian, lambda tenant, actor: credential)
    rt.registry.get("turing").health = Health.DEGRADED
    assert rt.heal_organ("turing", reason="degraded", actor="ops-1").verified
    assert credential not in json.dumps(rt.evidence.to_payload())
    assert credential not in json.dumps(rt.autonomic.ledger.records)
