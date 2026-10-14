from dataclasses import replace
from fractions import Fraction as F
from chronus.agent.value import agent_is_admissible


def test_catastrophe_is_hard_constraint(wired):
    r, o, c, p, a = wired
    action = p.actions[0]
    assert not agent_is_admissible(
        replace(action.value, expected_value=10**20), o.constraints, F(1, 100), action.request
    )
    assert not agent_is_admissible(
        action.value, o.constraints, F(0), replace(action.request, jurisdiction="other")
    )
