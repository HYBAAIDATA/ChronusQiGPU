import json

import pytest

from chronus.backends.lattice import LatticeOverflowError, PhiElement, phi_power
from chronus.execution import ExecutionRouter

pytestmark = pytest.mark.real


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


def test_lattice_fold_defaults_to_exact_native_reference():
    element = PhiElement(-(2**63), 2**63 - 1, 7)
    payload = json.dumps(
        {
            "order": 360,
            "values": [{"a": str(element.a), "b": str(element.b), "denominator": "7"}],
        }
    ).encode()
    receipt = ExecutionRouter().execute(payload, "PV_LATTICE_FOLD")
    expected = element.multiply(phi_power(360))
    assert receipt.execution_mode == "NATIVE_CPU_REFERENCE"
    assert receipt.result["device_signature"] is None
    assert receipt.result["norm_invariant_verified"] is True
    assert receipt.result["values"] == [
        {
            "a": str(expected.a),
            "b": str(expected.b),
            "denominator": "7",
        }
    ]
    assert max(abs(expected.a), abs(expected.b)) >= 2**255


@pytest.mark.parametrize(
    "payload",
    [
        b'{"order":361,"values":[{"a":1,"b":0,"denominator":1}]}',
        b'{"order":0,"values":[{"a":9223372036854775808,"b":0,"denominator":1}]}',
        b'{"order":0,"values":[{"a":1,"b":0,"denominator":0}]}',
        b'{"order":0,"values":[{"a":true,"b":0,"denominator":1}]}',
    ],
)
def test_lattice_reference_rejects_invalid_input(payload):
    with pytest.raises((ValueError, LatticeOverflowError)):
        ExecutionRouter().execute(payload, "PV_LATTICE_FOLD")
