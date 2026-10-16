from dataclasses import replace
from fractions import Fraction as F
import pytest
from chronus.agent._contracts import ContractError
from conftest import H
from chronus.agent.hypothesis import Hypothesis, ExperimentResult, scientific_cycle


def test_competing_falsifiable_hypotheses():
    a = Hypothesis("a", "cause A", ("p",), ("f",), F(1, 2), F(1, 2))
    b = replace(a, id="b", statement="cause B")
    results = scientific_cycle(
        (a, b), run_experiment=lambda h: ExperimentResult(H, F(1, 4), F(3, 4), h.id == "a")
    )
    assert results[0].state == "REFUTED" and results[0].posterior == F(1, 4)
    with pytest.raises(ContractError):
        scientific_cycle((a,), run_experiment=lambda _: None)
