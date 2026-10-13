from Intelligence.verification_gate import check_completion


def test_incomplete_without_context():
    r = check_completion(
        context_loaded=False,
        evidence_retrieved=True,
        verification_executed=True,
        tests_passed=True,
    )
    assert not r.passed
    assert "context" in r.reason


def test_complete_when_all_present():
    r = check_completion(
        context_loaded=True,
        evidence_retrieved=True,
        verification_executed=True,
        tests_passed=True,
    )
    assert r.passed


def test_canonical_requires_owner():
    r = check_completion(
        context_loaded=True,
        evidence_retrieved=True,
        verification_executed=True,
        tests_passed=True,
        touches_canonical=True,
        owner_approval_recorded=False,
    )
    assert not r.passed
