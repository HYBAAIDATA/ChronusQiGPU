from dataclasses import replace
from fractions import Fraction as F
import pytest
from chronus.agent._contracts import ContractError
from chronus.agent.counterfactual import Option, counterfactual_plan
from chronus.agent.value import Value
from chronus.agent.trust import TrustLevel


def test_inaction_explicit(wired):
    r, o, c, p, a = wired
    idle = Option(None, Value(0, 0, 0, 0, 0, 0, 0), F(0), 0, 0, "INACTION")
    assert (
        counterfactual_plan(
            (idle,),
            o,
            r.permissions,
            level=TrustLevel.OBSERVE,
            now=100,
            option_weight=0,
            information_weight=0,
        )
        == idle
    )
    with pytest.raises(ContractError):
        replace(idle, action=p.actions[0])
    with pytest.raises(ContractError):
        counterfactual_plan(
            (),
            o,
            r.permissions,
            level=TrustLevel.OBSERVE,
            now=100,
            option_weight=0,
            information_weight=0,
        )
