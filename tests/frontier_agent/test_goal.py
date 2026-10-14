import pytest
from chronus.agent._contracts import ContractError
from chronus.agent.goal import infer_real_objective


def test_ambiguous_goal_refused(ledger):
    with pytest.raises(ContractError):
        infer_real_objective("be smart", ledger, now=1)
