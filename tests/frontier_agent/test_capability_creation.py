from dataclasses import replace
import pytest
from chronus.agent._contracts import ContractError
from conftest import H
from chronus.agent.capability_creation import Attempt, detect_capability_gap, CapabilityCandidate
from chronus.agent.trust import TrustLevel


def test_gap_needs_multiple_strategies(task):
    assert (
        detect_capability_gap(
            task, (Attempt("one", False, H), Attempt("one", False, H)), minimum_failures=2
        )
        is None
    )
    assert detect_capability_gap(
        task, (Attempt("one", False, H), Attempt("two", False, H)), minimum_failures=2
    )


def test_candidate_cannot_inherit_authority(task):
    t = replace(task, workflow="candidate:new")
    with pytest.raises(ContractError):
        CapabilityCandidate(
            "new", None, "CONSTRUCTION", t, None, None, False, False, TrustLevel.OWN
        )


def test_candidate_requires_earned_assurance_and_is_task_scoped(
    qualification, identity, task, ledger, wired
):
    from chronus.agent.capability_creation import (
        create_capability,
        integrate_capability,
        retire_capability,
    )
    from chronus.agent.capabilities import CapabilitySet, Capability
    from chronus.agent.evaluation import evaluate_agent

    s, r, a, g, k = qualification
    t = replace(task, workflow="candidate:new")
    evaluator = s.evaluator_keys["unit-evaluator"]
    report = evaluate_agent(
        identity,
        t,
        r.suite,
        runner=lambda cohort, *_: next(c for c in r.cohorts if c.cohort == cohort),
        evaluator="unit-evaluator",
        signer=evaluator,
        now=2,
    )
    att = replace(a, task_key=t.key, evidence_digest=report.metrics.evidence_digest, signature="")
    att = replace(att, signature=s.verifier_keys["unit-assurance"].sign(att.body()))
    contract = Capability(
        "new", "request", "observed output", "unit suite", ("failure",), ("hash",)
    )
    base = CapabilityCandidate("new", contract, "COMPOSITION", t, report, att, False, False)
    gap = detect_capability_gap(
        task, (Attempt("a", False, H), Attempt("b", False, H)), minimum_failures=2
    )
    candidate = create_capability(
        gap,
        propose=lambda _: base,
        sandbox=lambda _: True,
        red_team=lambda _: True,
        ledger=ledger,
        now=2,
    )
    registry = CapabilitySet()
    adapter = wired[-1]
    integrated = integrate_capability(
        candidate,
        identity,
        registry,
        adapter,
        ledger,
        now=3,
        evaluator_keys=s.evaluator_keys,
        verifier_keys=s.verifier_keys,
        max_age=100,
    )
    assert integrated.authority == TrustLevel.OBSERVE
    with pytest.raises(ContractError):
        registry.get("new", task_key=task.key)
    assert registry.get("new", task_key=t.key)[1] is adapter
    retired = retire_capability(integrated, registry, ledger, now=4, reason="unit degradation")
    assert retired.deployment_state == "RETIRED"
    with pytest.raises(ContractError):
        registry.get("new", task_key=t.key)


def test_missing_assurance_is_not_filled_by_required_level(
    task, identity, ledger, qualification, wired
):
    from chronus.agent.capability_creation import integrate_capability
    from chronus.agent.capabilities import CapabilitySet, Capability

    s, r, a, g, k = qualification
    candidate = CapabilityCandidate(
        "new",
        Capability("new", "i", "o", "suite", ("failure",), ("evidence",)),
        "CONSTRUCTION",
        replace(task, workflow="candidate:new"),
        r,
        None,
        True,
        True,
        deployment_state="EVALUATED",
    )
    with pytest.raises(ContractError):
        integrate_capability(
            candidate,
            identity,
            CapabilitySet(),
            wired[-1],
            ledger,
            now=2,
            evaluator_keys=s.evaluator_keys,
            verifier_keys=s.verifier_keys,
            max_age=100,
        )
