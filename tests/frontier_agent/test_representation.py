from dataclasses import replace
from fractions import Fraction as F
import pytest
from chronus.agent._contracts import ContractError
from chronus.agent.representation import represent_problem


def test_acceptance_criteria_preserved(wired):
    r, o, c, p, a = wired
    assert (
        represent_problem(o, (), extractor=lambda *_: c.representation, confidence_floor=F(1, 2))
        == c.representation
    )
    with pytest.raises(ContractError):
        represent_problem(
            o,
            (),
            extractor=lambda *_: replace(c.representation, success_criteria=("other",)),
            confidence_floor=F(1, 2),
        )
