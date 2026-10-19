from dataclasses import replace
from fractions import Fraction as F
import pytest
from chronus.agent._contracts import ContractError
from chronus.agent.trust import TrustLevel


def test_only_qualified_signed_snapshot_promotes(qualification):
    s, r, a, g, k = qualification
    snapshot = s.qualify("scheduled", r, a, g, now=2, expires_at=7000)
    assert snapshot.level == TrustLevel.ADVISE
    assert k.verify(snapshot.body(), snapshot.signature)


def test_contamination_and_tamper_block(qualification):
    s, r, a, g, k = qualification
    with pytest.raises(ContractError):
        s.qualify("scheduled", replace(r, contamination=("leakage",)), a, g, now=2, expires_at=7000)
    with pytest.raises(ContractError):
        s.qualify("ordinary_task", r, a, g, now=2, expires_at=7000)


def test_bad_goodhart_suspends(qualification):
    s, r, a, g, k = qualification
    s.qualify("scheduled", r, a, g, now=2, expires_at=7000)
    out = s.qualify("incident", r, a, replace(g, verdict="GAMING"), now=3, expires_at=7000)
    assert out.level == TrustLevel.OBSERVE


def test_t1_direct_quorum_cannot_be_replaced_with_transfer(qualification):
    s, r, a, g, k = qualification
    s.qualify("scheduled", r, a, g, now=2, expires_at=7000)
    s.qualify("expansion", r, a, g, now=3, expires_at=7000)
    s.transfer_quorum = 13
    snapshot = s.qualify("expansion", r, a, g, now=4, expires_at=7000)
    assert snapshot.level == TrustLevel.ASSIST


def test_signed_strategy_standing_requires_strategy_specific_evaluation(qualification):
    from chronus.agent.strategy import ReasoningStrategy as S

    s, r, a, g, k = qualification
    with pytest.raises(ContractError):
        s.qualify_strategy(
            S.TOOL_SEARCH,
            "scheduled",
            r,
            a,
            g,
            now=2,
            expires_at=7000,
            minimum_success=F(1, 2),
            max_ece=F(1, 10),
        )


def test_drift_cycles_are_recorded_in_actual_qualification_path(qualification):
    s, r, a, g, k = qualification
    signer = s.reviewer_keys[g.reviewer]
    for cycle in (1, 2):
        check = replace(
            g, cycle=cycle, divergence=F(1, 5), verdict="DRIFTING", checked_at=cycle + 1
        )
        check = replace(check, signature=signer.sign(check.body()))
        s.metric_freeze_book.freeze(check.metric, check.metric_version, cycle=cycle, now=cycle + 1)
        out = s.qualify("scheduled", r, a, check, now=cycle + 2, expires_at=7000)
        assert out.level == TrustLevel.OBSERVE
    assert g.metric in s.metric_freeze_book._suspended
