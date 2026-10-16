from dataclasses import replace
import pytest
from chronus.agent.trust import TrustLevel


@pytest.mark.parametrize(
    "field,value",
    [
        ("resource", "elsewhere"),
        ("scope", "other"),
        ("purpose", "publish"),
        ("limit", 10001),
        ("duration", 9000),
        ("task_key", "other"),
    ],
)
def test_six_tuple_denial(wired, field, value):
    r, o, c, p, a = wired
    assert not r.permissions.permitted(
        replace(p.actions[0].request, **{field: value}), level=TrustLevel.ASSIST, now=100
    )


def test_aggregate_usage_and_revocation(wired):
    r, o, c, p, a = wired
    req = replace(p.actions[0].request, limit=6000)
    assert r.permissions.permitted(req, level=TrustLevel.ASSIST, now=100, consume=True)
    assert not r.permissions.permitted(req, level=TrustLevel.ASSIST, now=100, consume=True)
    r.permissions.revoke("g", now=101)
    assert not r.permissions.permitted(p.actions[0].request, level=TrustLevel.ASSIST, now=102)
