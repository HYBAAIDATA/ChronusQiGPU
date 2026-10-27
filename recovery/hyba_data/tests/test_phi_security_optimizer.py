from hermes.offerings.phi_security_optimizer import (
    DefensiveSignal,
    PHI,
    allocate_review_slots,
    rank_signals,
    score_signal,
)


def test_phi_freshness_is_bounded_and_reduces_stale_signal_priority():
    fresh = score_signal(DefensiveSignal("fresh", 1, 1, 1, age_units=0))
    stale = score_signal(DefensiveSignal("stale", 1, 1, 1, age_units=1))
    assert fresh["priority_score"] == 1.0
    assert abs(stale["priority_score"] - (1.0 / PHI)) < 1e-12
    assert stale["priority_score"] < fresh["priority_score"]


def test_rank_is_deterministic_and_never_authorizes_actions():
    signals = [
        DefensiveSignal("b", 0.8, 0.7, 0.9),
        DefensiveSignal("a", 0.8, 0.7, 0.9),
        DefensiveSignal("c", 0.1, 0.2, 0.3),
    ]
    first = rank_signals(signals)
    second = rank_signals(reversed(signals))
    assert first["ranking_sha256"] == second["ranking_sha256"]
    assert [item["signal_id"] for item in first["ranking"]] == ["a", "b", "c"]
    assert first["action_authorized"] is False
    assert first["actuation_performed"] is False


def test_invalid_scores_and_duplicate_ids_fail_closed():
    import pytest

    with pytest.raises(ValueError):
        score_signal(DefensiveSignal("bad", 1.1, 1, 1))
    with pytest.raises(ValueError):
        rank_signals([DefensiveSignal("same", 1, 1, 1), DefensiveSignal("same", 0, 1, 1)])


def test_review_slot_allocation_sums_exactly_and_prioritizes_first():
    allocation = allocate_review_slots(["critical", "high", "normal"], 17)
    assert sum(allocation.values()) == 17
    assert allocation["critical"] >= allocation["high"] >= allocation["normal"]


def test_empty_slot_allocation():
    assert allocate_review_slots([], 0) == {}

def test_consolidated_offering_exposes_phi_triage_and_audits_digest():
    from hermes.offerings.national_security import NationalSecurityOffering

    offering = NationalSecurityOffering()
    result = offering.rank_defensive_signals([
        DefensiveSignal("web-edge", 0.9, 0.8, 0.95),
        DefensiveSignal("database", 0.7, 0.9, 0.8, age_units=1),
    ])
    assert result["schema"] == "hyba.phi_defensive_triage/v1"
    assert result["hyba_audit_integrity"] is True
    assert result["recommendation_only"] is True
    assert result["action_authorized"] is False
    assert result["actuation_performed"] is False
