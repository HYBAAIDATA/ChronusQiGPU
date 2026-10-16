from fractions import Fraction as F
import pytest
from chronus.agent._contracts import ContractError
from chronus.agent.multi_agent import DelegationPacket, delegate, resolve_disagreement
from chronus.agent.trust import TrustLevel


def test_no_implicit_delegation(wired):
    r, o, c, p, a = wired
    packet = DelegationPacket("child", r.task_class.key, ("unissued",), 1, 200, "stop")
    calls = []
    with pytest.raises(ContractError):
        delegate(
            packet,
            p.actions[0].request,
            r.permissions,
            level=TrustLevel.ASSIST,
            now=100,
            dispatcher=calls.append,
        )
    assert not calls
    with pytest.raises(ContractError):
        resolve_disagreement((("yes", F(1)), ("no", F(1))))
