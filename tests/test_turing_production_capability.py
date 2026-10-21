"""Governed local capability delivery through the real shared production root."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
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
from aethel.enterprise.production_organism import ProductionOrganism
from euclid.contracts import Health
from salamander.control_plane import FailClosed
from toe.foundation import UNIFIED_THEORY as PYTHIA_FOUNDATION
from turing_universal_quantum_computer.backends import Program
from turing_universal_quantum_computer.unified_theory import (
    UNIFIED_THEORY as TURING_FOUNDATION,
)

FOUNDATION_DIGEST = "dc8328e59f1a7422697ceb535c6e9b548383a1e505b6fd7a3a1b39358ac9ee83"


@pytest.fixture
def factory(tmp_path):
    organisms = []

    def create(*, configured=True):
        authority = SubscriptionAuthority(
            {"fixture": b"production-capability-local-fixture-key"}, "production-test"
        )
        guardian = ALHaras(
            authority,
            GuardianPolicy(
                version="fixture",
                allowed_operations=frozenset(
                    {
                        "turing.run-program",
                        "turing.capability-matrix",
                        "salamander.requalify",
                    }
                ),
            ),
            HashChainAudit(tmp_path / f"guardian-{len(organisms)}.jsonl"),
        )
        calls = []

        def credential(tenant="tenant-a", actor="operator"):
            now = int(time.time())
            return authority.issue(
                SubscriptionClaims(
                    "fixture",
                    tenant,
                    "production-test",
                    "fixture",
                    ("hyba.security",),
                    (actor,),
                    now - 5,
                    now + 300,
                )
            )

        def provider(tenant, actor):
            calls.append((tenant, actor))
            return credential(tenant, actor)

        organism = ProductionOrganism(
            tmp_path / f"organism-{len(organisms)}",
            hmac_key=b"shared-custody-local-fixture-key-32b",
            tenant="tenant-a",
            creator_id="different-creator",
            guardian=guardian,
            subscription_token_provider=provider if configured else None,
            allow_insecure_dev_key=True,
        )
        organisms.append(organism)
        organism.start()
        return organism, credential, calls

    try:
        yield create
    finally:
        for organism in reversed(organisms):
            organism.stop()


def run(organism, credential, program, *, routed=False):
    request = {
        "operation": "run-program",
        "program": program.to_dict(),
        "prefer": "exact_algebraic",
    }
    kwargs = {"tenant_id": "tenant-a", "actor": "operator", "subscription_token": credential()}
    if routed:
        return organism.euclid.route_specialist(request, **kwargs)
    return organism.euclid.dispatch_specialist("turing", request, **kwargs)


def test_installed_pythia_and_turing_wheels_expose_pinned_foundation():
    assert PYTHIA_FOUNDATION.verify()
    assert TURING_FOUNDATION.verify()
    assert PYTHIA_FOUNDATION.payload() == TURING_FOUNDATION.payload()
    assert PYTHIA_FOUNDATION.digest == TURING_FOUNDATION.digest == FOUNDATION_DIGEST


def test_governed_turing_uses_canonical_certificate_and_shared_replay(factory):
    organism, credential, _ = factory()
    program = Program(1).then("x", 0)
    response = run(organism, credential, program)
    assert response["allowed"] is True
    result = response["result"]
    assert result["owner"] == "TURING" and result["executed"] is True
    assert result["truth_class"] == "exact"
    assert result["program_digest"] == program.digest()
    report = result["pipeline_report"]
    assert report["verdict"] == "PASS"
    assert report["certificate"] and report["witness"]
    assert organism.turing.replay()["passed"] is True
    graph = organism.lifecycle.fabric.graph()["bindings"]
    assert {"turing_certificate", "turing_replay", "turing_euclid_handoff"} <= {
        item["kind"] for item in graph
    }
    assert all(organism.lifecycle.fabric.verify(item["binding_id"])["passed"] for item in graph)
    assert organism._euclid_raw.registry.get("turing").handler is not None
    json.dumps(response)  # No live state object leaks across the service envelope.


def test_euclid_routes_real_capability_without_replacing_turing_authority(factory):
    organism, credential, _ = factory()
    response = run(organism, credential, Program(1).then("h", 0), routed=True)
    assert response["routed"] is True
    assert response["routing"]["organ_id"] == "turing"
    assert response["result"]["pipeline_report"]["verdict"] == "PASS"
    assert response["result"]["owner"] == "TURING"
    assert any(r.kind == "routing-decision" for r in organism._euclid_raw.evidence.records)


def test_explicit_actuation_uses_custody_tenant_not_creator_identity(factory):
    organism, _, calls = factory()
    raw = organism._euclid_raw
    raw.registry.get("turing").health = Health.DEGRADED
    result = organism.euclid.heal_organ("turing", reason="local probe", actor="operator")
    assert result.verified is True
    assert calls == [("tenant-a", "operator")]
    assert raw.registry.get("turing").health is Health.HEALTHY
    assert organism.status()["salamander_actuation"]["ready"] is True
    assert any(
        item["kind"] == "salamander_control_evidence"
        for item in organism.lifecycle.fabric.graph()["bindings"]
    )


def test_unconfigured_actuation_remains_closed_and_reports_reason(factory):
    organism, _, calls = factory(configured=False)
    with pytest.raises(FailClosed, match="token provider"):
        organism.euclid.heal_organ("turing", reason="local probe", actor="operator")
    state = organism.status()["salamander_actuation"]
    assert state["configured"] is False and state["ready"] is False
    assert "token provider" in state["reason"] and calls == []


def test_valid_other_tenant_entitlement_cannot_write_this_shared_fabric(factory):
    organism, credential, _ = factory()
    before = len(organism.turing.last_bindings)
    response = organism.euclid.dispatch_specialist(
        "turing",
        {"operation": "run-program", "program": Program(1).to_dict()},
        tenant_id="tenant-b",
        actor="operator",
        subscription_token=credential("tenant-b"),
    )
    assert response["allowed"] is False
    assert response["governance"]["reason"] == "TENANT_BOUNDARY_MISMATCH"
    assert len(organism.turing.last_bindings) == before
    assert not any(r.kind == "delegation-result" for r in organism._euclid_raw.evidence.records)


def test_concurrent_governed_runs_keep_each_certificate_bound(factory):
    organism, credential, _ = factory()
    programs = [Program(1).then(gate, 0) for gate in ("x", "h", "z", "s")]
    with ThreadPoolExecutor(max_workers=4) as pool:
        answers = list(pool.map(lambda p: run(organism, credential, p), programs))
    for program, response in zip(programs, answers):
        result = response["result"]
        assert result["program_digest"] == program.digest()
        assert result["pipeline_report"]["verdict"] == "PASS"
        assert result["pipeline_report"]["program_digest"] == program.digest()
    assert organism.turing.replay()["passed"] is True
    handoffs = [
        item
        for item in organism.lifecycle.fabric.graph()["bindings"]
        if item["kind"] == "turing_euclid_handoff"
    ]
    assert len(handoffs) == len(programs)
