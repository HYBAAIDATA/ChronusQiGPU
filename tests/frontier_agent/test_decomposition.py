from dataclasses import replace
import pytest
from chronus.agent._contracts import ContractError
from chronus.agent.decomposition import Subgoal, Decomposition, decompose


def test_cycle_and_uncovered_goal_fail(wired):
    r, o, c, p, a = wired
    d = Decomposition(
        o.id,
        (Subgoal("one", o.success_criteria, (), "interface", "acceptance"),),
        "verify",
        "restore",
    )
    assert decompose(o, (d,)) == d
    with pytest.raises(ContractError):
        decompose(o, (replace(d, subgoals=(replace(d.subgoals[0], dependencies=("one",)),)),))
