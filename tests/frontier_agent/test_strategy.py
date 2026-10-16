from dataclasses import replace
from fractions import Fraction as F
import pytest
from chronus.agent._contracts import ContractError, digest
from chronus.agent.strategy import (
    ReasoningStrategy as S,
    Strategy,
    TaskCharacterisation,
    SelectorPolicy,
    StrategyTrackRecord,
    select_reasoning_strategy,
    update_strategy_statistics,
)
from chronus.agent.trust import TrustLevel
from chronus.agent.audit import MACSigner
from conftest import H


def select(task, ledger, *, authority=TrustLevel.ASSIST, registry=None, statistics=(), policy=None):
    signer = MACSigner("unit-governance", b"g" * 32)
    registry = registry or (Strategy(S.TOOL_SEARCH, 1, F(1), ("external",), (), 2, True),)
    policy = policy or SelectorPolicy(F(1, 4), F(1, 2), F(1, 2), F(0), 100, 10, 2, F(1, 2))
    return select_reasoning_strategy(
        registry,
        task,
        authority=authority,
        policy=policy,
        statistics=statistics,
        verify_statistics=signer.verify,
        now=100,
        ledger=ledger,
    )


def characterisation(task, **changes):
    return replace(
        TaskCharacterisation(task.key, F(0), F(0), "REVERSIBLE", "LOCAL", 100, (), (), F(1)),
        **changes
    )


def record(task, **changes):
    signer = MACSigner("unit-governance", b"g" * 32)
    r = replace(
        StrategyTrackRecord(S.TOOL_SEARCH, task.key, F(1), F(0), False, 1, 1000, H, ""), **changes
    )
    r = replace(r, context_fingerprint=digest(("unit-agent", H, "b" * 64, "unit-policy")))
    return replace(r, signature=signer.sign(r.body()))


def test_s1_authority_gating_before_rank(task, ledger):
    plan = select(
        characterisation(task), ledger, authority=TrustLevel.OBSERVE, statistics=(record(task),)
    )
    assert S.TOOL_SEARCH not in plan.ranked and plan.mode == "STOP"


def test_s2_untested_pessimistic_and_task_bound(task, ledger):
    plan = select(characterisation(task), ledger)
    assert plan.mode == "STOP"
    plan = select(characterisation(task), ledger, statistics=(record(task, task_key="other"),))
    assert plan.mode == "STOP"
    plan = select(characterisation(task), ledger, statistics=(record(task),))
    assert plan.primary == S.TOOL_SEARCH


def test_s3_external_irreversible_checkpoint(task, ledger):
    plan = select(
        characterisation(task, reversibility="IRREVERSIBLE", verifiability="EXTERNAL_ONLY"),
        ledger,
        statistics=(record(task),),
    )
    assert plan.checkpoint_before_acting


def test_s4_wait_and_stop_retained(task, ledger):
    plan = select(characterisation(task), ledger, statistics=(record(task),))
    assert S.STOP not in plan.ranked and S.DO_NOTHING_OR_WAIT in plan.ranked


def test_s5_ambiguity_portfolio_and_fallback(task, ledger):
    plan = select(
        characterisation(task, ambiguity=F(1), reversibility="IRREVERSIBLE"),
        ledger,
        statistics=(record(task),),
    )
    assert plan.mode == "PROPOSE" and (plan.fallback is not None or plan.no_fallback_reason)
    plan = select(characterisation(task, novelty=F(1)), ledger, statistics=(record(task),))
    assert plan.mode == "SEQUENTIAL_WITH_CHECKPOINT" and plan.checkpoint_before_acting
    assert plan.fallback is not None or plan.no_fallback_reason


def test_s6_quarantine_cannot_be_lifted_by_unsigned_learning(task, ledger):
    r = record(task, quarantined=True)
    plan = select(characterisation(task), ledger, statistics=(r,))
    assert S.TOOL_SEARCH not in plan.ranked
    episode = dict(
        strategy="TOOL_SEARCH",
        task_key=task.key,
        outcome="passed",
        actual_cost=1,
        estimated_cost=1,
        failure_mode="none",
        fallback_used=False,
        human_intervention=False,
        evidence=H,
    )
    update_strategy_statistics(episode, ledger, now=101)
    assert S.TOOL_SEARCH not in select(characterisation(task), ledger, statistics=(r,)).ranked


def test_stale_tampered_record_cannot_inflate_success(task, ledger):
    r = record(task)
    assert (
        select(
            characterisation(task), ledger, statistics=(replace(r, success_lower_bound=F(1, 2)),)
        ).mode
        == "STOP"
    )
    assert (
        select(characterisation(task), ledger, statistics=(record(task, expires_at=99),)).mode
        == "STOP"
    )


def test_budget_and_evidence_gate(task, ledger):
    plan = select(characterisation(task, remaining_budget=0), ledger, statistics=(record(task),))
    assert plan.mode == "STOP"
    registry = (Strategy(S.TOOL_SEARCH, 1, F(1), (), ("missing",), 2, True),)
    assert (
        select(characterisation(task), ledger, registry=registry, statistics=(record(task),)).mode
        == "STOP"
    )


def test_authority_and_assurance_are_independent_axes(task, ledger):
    from chronus.agent.assurance import AssuranceLevel

    registry = (Strategy(S.TOOL_SEARCH, 1, F(1), (), (), 0, True, AssuranceLevel.CERTIFIED),)
    plan = select(
        characterisation(task),
        ledger,
        registry=registry,
        authority=TrustLevel.OWN,
        statistics=(record(task),),
    )
    assert S.TOOL_SEARCH not in plan.ranked
    with pytest.raises(ContractError):
        Strategy(S.STOP, 0, F(1), (), (), 0, False)
