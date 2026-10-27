from dataclasses import dataclass
from typing import Any

from hermes.offerings.toe_platform_adapter import TOEPlatformAdapter


class FakeProblem:
    def __init__(self, **kwargs: Any):
        self.kwargs = kwargs

    def validate(self):
        return []


@dataclass
class FakeTenant:
    tenant_id: str
    mode: str = "standard"
    allowed_claims: frozenset[str] = frozenset()


class FakeRuntime:
    def __init__(self, response=None, error=None):
        self.response = response or {"ok": True, "degraded": False, "result": {}, "receipt": {"receipt_id": "r1"}}
        self.error = error
        self.calls = []

    def solve(self, problem, tenant):
        self.calls.append((problem, tenant))
        if self.error:
            raise self.error
        return self.response


def make_adapter(runtime):
    return TOEPlatformAdapter(runtime, problem_type=FakeProblem, tenant_type=FakeTenant)


def test_adapter_returns_advisory_toe_response():
    runtime = FakeRuntime()
    result = make_adapter(runtime).assess(
        {"event_id": "e1"}, tenant_id="tenant-a", purpose="defensive-risk-triage"
    )
    assert result["status"] == "available"
    assert result["recommendation_only"] is True
    assert result["action_authorized"] is False
    assert runtime.calls[0][1].tenant_id == "tenant-a"


def test_adapter_fails_closed_on_runtime_error():
    result = make_adapter(FakeRuntime(error=RuntimeError("unavailable"))).assess(
        {"event_id": "e2"}, tenant_id="tenant-a", purpose="defensive-risk-triage"
    )
    assert result["status"] == "unavailable"
    assert result["action_authorized"] is False


def test_adapter_rejects_missing_tenant_and_non_mapping_observation():
    adapter = make_adapter(FakeRuntime())
    missing_tenant = adapter.assess({"event_id": "e3"}, tenant_id=" ", purpose="review")
    invalid_observation = adapter.assess([], tenant_id="tenant-a", purpose="review")
    assert missing_tenant["error"]["code"] == "invalid_tenant"
    assert invalid_observation["error"]["code"] == "invalid_observation"
