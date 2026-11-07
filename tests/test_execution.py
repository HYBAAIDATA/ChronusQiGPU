import pytest

from chronus.execution import ExecutionRouter


class FixtureBackend:
    name = "fixture"
    supported_workloads = frozenset({"FIXTURE_WORKLOAD"})

    def supports(self, workload_type):
        return workload_type in self.supported_workloads

    def execute(self, payload, workload_type):
        return {"payload_size": len(payload), "workload_type": workload_type}


def test_execution_router_registers_and_selects_named_backend():
    router = ExecutionRouter()
    router.register_backend(FixtureBackend())

    receipt = router.execute(b"payload", "FIXTURE_WORKLOAD", "fixture")

    assert receipt.backend == "fixture"
    assert receipt.execution_state == "EXECUTED"
    assert receipt.result["payload_size"] == 7
    assert router.list_backends()["fixture"] == ["FIXTURE_WORKLOAD"]


def test_execution_router_rejects_unknown_or_unsupported_backends():
    router = ExecutionRouter()
    router.register_backend(FixtureBackend())

    with pytest.raises(ValueError, match="not registered"):
        router.execute(b"payload", "FIXTURE_WORKLOAD", "missing")
    with pytest.raises(ValueError, match="does not support"):
        router.execute(b"payload", "OTHER_WORKLOAD", "fixture")
    with pytest.raises(ValueError, match="unique"):
        router.register_backend(FixtureBackend())
