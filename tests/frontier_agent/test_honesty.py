from conftest import H
from chronus.agent.honesty import Claim, honest_report


def test_unsupported_claim_not_verified():
    report = honest_report(Claim("test", verification_refs=(H,)), established_refs=set())
    assert not any(report["states"].values())
