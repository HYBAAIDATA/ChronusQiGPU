from dataclasses import replace
from fractions import Fraction as F
import pytest
from chronus.agent._contracts import ContractError
from tests.frontier_agent.conftest import H
from chronus.agent.anti_goodhart import OutcomeSample, anti_goodhart_review


def test_independent_proxy_divergence(qualification, identity, task):
    s, r, a, g, k = qualification
    check = anti_goodhart_review(
        identity,
        task,
        r.metrics,
        (OutcomeSample(F(1), F(0), H, "reviewer"),) * 2,
        metric="outcome",
        drift_threshold=F(1, 4),
        reviewer="unit-reviewer",
        signer=s.reviewer_keys["unit-reviewer"],
        now=2,
        expires_at=100,
    )
    assert check.verdict == "DRIFTING"
    assert not check.admitted(task=task, metrics=r.metrics, now=3, keys=s.reviewer_keys)


def test_g1_three_metrics_two_families_and_frozen_versions(qualification):
    from chronus.agent.anti_goodhart import valid_gate_metrics

    s, r, a, g, k = qualification
    assert valid_gate_metrics(g.gate_metrics)
    assert not valid_gate_metrics(g.gate_metrics[:2])
    with pytest.raises(ContractError):
        s.metric_freeze_book.freeze(g.metric, "changed-during-cycle", cycle=0, now=2)


def test_g1_two_consecutive_divergent_cycles_suspend(qualification, task):
    s, r, a, g, k = qualification
    signer = s.reviewer_keys[g.reviewer]
    for cycle in (1, 2):
        check = replace(
            g, cycle=cycle, divergence=F(1, 5), verdict="DRIFTING", checked_at=cycle + 1
        )
        check = replace(check, signature=signer.sign(check.body()))
        s.metric_freeze_book.freeze(check.metric, check.metric_version, cycle=cycle, now=cycle + 1)
        assert not s.metric_freeze_book.record(
            check,
            task=task,
            metrics=r.metrics,
            now=cycle + 2,
            keys=s.reviewer_keys,
            divergence_max=F(1, 10),
        )
    assert g.metric in s.metric_freeze_book._suspended
