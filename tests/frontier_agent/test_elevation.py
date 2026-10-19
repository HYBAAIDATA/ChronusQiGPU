import pytest
from chronus.agent.elevation import elevate


def test_requires_host_service():
    with pytest.raises(TypeError):
        elevate(object(), "scheduled", None, None, None, now=1, expires_at=2)
