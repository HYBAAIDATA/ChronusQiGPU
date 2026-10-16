from dataclasses import replace
import pytest
from chronus.agent.assurance import assurance_required, AssuranceLevel as A
from chronus.agent.capabilities import RiskTier
from chronus.agent.trust import TrustLevel


@pytest.mark.parametrize(
    "risk,expected",
    [
        (RiskTier.T5_IRREVERSIBLE_OR_SAFETY_CRITICAL, A.CERTIFIED),
        (RiskTier.T4_EXTERNAL_CONSEQUENTIAL, A.EXTERNALLY_REVIEWED),
        (RiskTier.T3_EXTERNAL_REVERSIBLE, A.EXTERNALLY_REVIEWED),
        (RiskTier.T1_INTERNAL_REVERSIBLE, A.INTERNALLY_REVIEWED),
    ],
)
def test_risk_ladder(task, risk, expected):
    assert assurance_required(TrustLevel.OBSERVE, replace(task, risk_tier=risk)) == expected


def test_attestation_binding(qualification, identity, task):
    s, r, a, g, k = qualification
    assert a.admissible(identity, task, r.metrics, 2, s.verifier_keys)
    assert not replace(a, evidence_digest="f" * 64).admissible(
        identity, task, r.metrics, 2, s.verifier_keys
    )
    assert not a.admissible(identity, task, r.metrics, 8000, s.verifier_keys)
