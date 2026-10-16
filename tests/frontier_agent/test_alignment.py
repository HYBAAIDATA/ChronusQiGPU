from dataclasses import replace
import pytest
from chronus.agent.alignment import check_alignment


@pytest.mark.parametrize("field", ["proxy_only", "loophole", "stakeholder_violation", "goal_drift"])
def test_proxy_no_approval(wired, field):
    r, o, c, p, a = wired
    assert not check_alignment(replace(p.actions[0], **{field: True}), o).aligned
