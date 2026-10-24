"""The composition root serves the reasoning core: solve / learn, per tenant."""

from __future__ import annotations

import os

import pytest

from toe.ciaas_api import CIaaSService
from toe.custody import open_theseus_custody, theseus_available
from toe.planning import OperatorSpec
from toe.policy import Objective
from toe.problem import Problem, Structure
from toe.runtime import TenantContext, TOEIntelligenceRuntime, TOEIntelligenceRuntimeConfig
from toe.voyage import simulated_world, voyage_problem


from euclid.evidence import EvidenceChain  # noqa: E402 - the real chain, not a stand-in


def _runtime(**kw):
    cfg = TOEIntelligenceRuntimeConfig(
        enable_feedback=False, enable_asi=False, enable_platform=False
    )
    return TOEIntelligenceRuntime(config=cfg, evidence_chain=EvidenceChain(), **kw)


def test_solve_and_learn_through_the_runtime():
    rt = _runtime()
    tenant = TenantContext("acme")
    r1 = rt.solve(voyage_problem(), tenant)
    assert r1.ok and r1.result["status"] == "ACQUIRE_EVIDENCE"
    obs = simulated_world(r1.result["recommendation"]["interventions"], n=6, seed=101)
    r2 = rt.learn(r1.decision_id, obs, tenant)
    assert r2.ok and r2.result["revision"] is not None
    r3 = rt.solve(voyage_problem(z_state=0.25), tenant)
    assert r3.result["decision"]["selected_action"] == "raise_z=1.0"
    kinds = [r.kind for r in rt.evidence_chain.records]
    assert kinds == ["toe-solve", "toe-learn", "toe-solve"]


def test_tenants_do_not_share_learning():
    rt = _runtime()
    a, b = TenantContext("tenant-a"), TenantContext("tenant-b")
    r = rt.solve(voyage_problem(), a)
    rt.learn(r.decision_id, simulated_world({"x": 1.0}, n=6, seed=101), a)
    rb = rt.solve(voyage_problem(z_state=0.25), b)
    assert rb.result["identity"]["model_revision"] == 0
    assert rb.result["decision"]["selected_action"] == "raise_x=1.0"
    assert (
        rt.learn(r.decision_id, [{"x": 1.0, "z": 0.0, "y": 0.5}], b).error.code == "unknown_episode"
    )


def test_mining_mode_refuses_consensus_named_variables():
    rt = _runtime()
    bad = Problem(
        domain="any",
        structure=Structure.of([("nonce", "yield", 1.0)]),
        operators=(OperatorSpec("set_nonce", "nonce", (1.0,)),),
        objective=Objective("yield"),
    )
    resp = rt.solve(bad, TenantContext("pool-op", mode="mining"))
    assert not resp.ok and resp.error.code == "consensus_boundary_violation"
    # The same problem is fine for a non-mining tenant (vocabulary is domain-local).
    assert rt.solve(bad, TenantContext("lab")).ok


def test_problem_content_round_trips_through_the_api():
    # Explicit isolated authentication/tenant fixture, never production credentials.
    key = "isolated-api-fixture-not-production-credential"
    svc = CIaaSService(runtime=_runtime(), api_key=key)
    svc.register_tenant("acme")
    p = voyage_problem()
    _, denied = svc.handle_request("solve", p.content(), "acme")
    assert denied == 401
    _, unknown = svc.handle_request("solve", p.content(), "unknown", api_key=key)
    assert unknown == 403
    resp, status = svc.handle_request(
        "solve", p.content(), "acme", api_key=key, metadata={"domain": p.domain}
    )
    assert status == 200 and resp.result["identity"]["content_digest"] == p.content_digest()
    resp2, status2 = svc.handle_request(
        "learn",
        [{"x": 1.0, "z": 0.1, "y": 0.6}],
        "acme",
        api_key=key,
        metadata={"episode_sha256": resp.decision_id},
    )
    assert status2 == 200 and resp2.ok
    receipt = resp2.receipt
    assert receipt is not None
    assert receipt.tenant_id == "acme" and receipt.operation == "learn"
    assert receipt.evidence_source == "toe.machine.TOEMachine"
    assert receipt.payload_digest == svc.runtime._digest({
        "episode_sha256": resp.decision_id,
        "observed": [{"x": 1.0, "z": 0.1, "y": 0.6}],
    })
    assert receipt.result_digest == svc.runtime._digest(resp2.result)
    assert receipt.payload_digest != svc.runtime._digest({
        "episode_sha256": "different-episode",
        "observed": [{"x": 1.0, "z": 0.1, "y": 0.6}],
    })
    assert resp2.result["persisted"]["available"] is False
    _, missing = svc.handle_request(
        "learn", [], "acme", api_key=key, metadata={"episode_sha256": "nope"}
    )
    assert missing == 404


@pytest.mark.skipif(not theseus_available(), reason="THESEUS custody not importable")
def test_tenant_custody_survives_runtime_restart(tmp_path):
    key = os.urandom(32)

    def factory(tenant_id):
        return open_theseus_custody(tmp_path / tenant_id, hmac_key=key)

    rt = _runtime(custody_factory=factory)
    tenant = TenantContext("durable")
    r = rt.solve(voyage_problem(), tenant)
    rt.learn(r.decision_id, simulated_world({"x": 1.0}, n=6, seed=101), tenant)
    rt2 = _runtime(custody_factory=factory)
    again = rt2.solve(voyage_problem(z_state=0.25), tenant)
    assert again.result["identity"]["model_revision"] == 1
    assert rt2.machine_for(tenant).recovered_from["recovered"] is True


def test_learning_refuses_oversize_observations_before_model_mutation():
    rt = _runtime()
    tenant = TenantContext("acme")
    solved = rt.solve(voyage_problem(), tenant)
    machine = rt.machine_for(tenant)
    before = rt._digest(machine.snapshot())
    refused = rt.learn(solved.decision_id, {"x": "x" * 1_000_001}, tenant)
    assert not refused.ok and refused.error.code == "payload_invalid"
    assert refused.receipt is None
    assert rt._digest(machine.snapshot()) == before
