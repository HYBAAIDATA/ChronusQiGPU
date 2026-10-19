from dataclasses import replace
from fractions import Fraction as F
from tests.frontier_agent.conftest import H
from chronus.agent.verification import VerificationMethod, VerificationPolicy, verify


def test_dependence_ceiling(identity):
    method = VerificationMethod(
        "a",
        "self",
        identity.id,
        identity.operator,
        identity.training_process,
        "same",
        F(1),
        F(1),
        F(1),
        False,
        True,
        H,
    )
    policy = VerificationPolicy(F(3, 4), F(1, 2), F(1, 2))
    result = verify(identity, (method, replace(method, id="b")), policy, require_independence=True)
    assert not result.passed and result.confidence == F(1, 2)


def test_conflicting_verifier(wired):
    r, o, c, p, a = wired
    m = r.verification_provider(p.actions[0], a.observe(), replace(a.observe(), state="after"))[0]
    result = verify(r.identity, (m, replace(m, id="other", passed=False)), r.verification_policy)
    assert result.conflict and not result.passed
