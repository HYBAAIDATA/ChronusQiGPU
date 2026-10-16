import pytest
from chronus.agent._contracts import ContractError
from chronus.agent.robustness import harden_against


def test_defence_is_not_measurement():
    assert harden_against("TOOL_FAILURE")["tested"] is False
    with pytest.raises(ContractError):
        harden_against("MAGIC")
