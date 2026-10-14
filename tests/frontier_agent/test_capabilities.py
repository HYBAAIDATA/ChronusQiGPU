import pytest
from chronus.agent._contracts import ContractError
from chronus.agent.capabilities import CapabilitySet


def test_registration_not_competence(wired):
    r, *_ = wired
    assert r.capabilities.manifest()[0]["demonstrated_reliability"] is None
    with pytest.raises(ContractError):
        r.capabilities.get("missing")


def test_task_scope(wired):
    r, o, c, p, a = wired
    caps = CapabilitySet()
    caps.register(r.capabilities.get("unit-write")[0], a, task_key="candidate")
    with pytest.raises(ContractError):
        caps.get("unit-write", task_key="other")
