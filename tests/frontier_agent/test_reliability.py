from fractions import Fraction as F
import pytest
from chronus.agent._contracts import ContractError
from tests.frontier_agent.conftest import trial
from chronus.agent.reliability import measure_reliability, lower_success_bound


def test_conservative_bounds(task):
    m = measure_reliability(task, tuple(trial(str(i)) for i in range(8)))
    assert 0 < m.success_99 < m.success_95 < m.success_80 < m.success_50 < 1
    assert m.recovery_rate is None


def test_failure_and_recovery(task):
    m = measure_reliability(
        task, (trial("a", accepted=False), trial("b", initial_failure=True, recovered=True))
    )
    assert m.recovery_rate == 1
    assert m.success_99 < F(1, 2)
    assert measure_reliability(task, (trial(accepted=False),)).cost_per_success is None


def test_duplicate_and_resource_bound(task):
    with pytest.raises(ContractError):
        measure_reliability(task, (trial(), trial()))
    with pytest.raises(ContractError):
        lower_success_bound(129, 129, F(19, 20))
