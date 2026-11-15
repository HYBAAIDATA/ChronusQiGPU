"""QiGPU orchestration and hardware-agnostic surface tests."""

import base64
import json

import pytest

from chronus.execution import ExecutionRouter, NativeMathReferenceBackend
from chronus.execution.qigpu import QiGPUOrchestrator


class FakeAccelerator:
    name = "fake-gpu"
    execution_mode = "PHYSICAL_ACCELERATOR"
    supported_workloads = frozenset({"PV_LATTICE_FOLD"})

    def supports(self, workload_type):
        return workload_type in self.supported_workloads

    def probe_silicon(self):
        return {"device_name": "fake", "known_answer_test": "passed"}


def test_cpu_substrate_is_always_present():
    orchestrator = QiGPUOrchestrator(ExecutionRouter())
    inventory = orchestrator.inventory()
    assert inventory["hardware_agnostic"] is True
    assert inventory["default_surface"] == "python-math-reference"
    assert inventory["accelerator_surfaces"] == []
    surface = inventory["surfaces"][0]
    assert surface["kind"] == "cpu_substrate"
    assert surface["execution_mode"] == "NATIVE_CPU_REFERENCE"


def test_client_accelerator_surface_scales_in_when_provisioned():
    router = ExecutionRouter()
    router.register_backend(FakeAccelerator())
    inventory = QiGPUOrchestrator(router).inventory()
    assert inventory["accelerator_surfaces"] == ["fake-gpu"]
    accelerator = next(
        s for s in inventory["surfaces"] if s["surface_id"] == "fake-gpu"
    )
    assert accelerator["kind"] == "client_accelerator"
    assert accelerator["telemetry"]["known_answer_test"] == "passed"


def test_resolve_honors_client_preference_and_fails_closed():
    router = ExecutionRouter()
    router.register_backend(FakeAccelerator())
    orchestrator = QiGPUOrchestrator(router)
    assert orchestrator.resolve("PV_LATTICE_FOLD", "fake-gpu") == "fake-gpu"
    assert orchestrator.resolve("PV_LATTICE_FOLD", None) == "python-math-reference"
    with pytest.raises(ValueError, match="not provisioned"):
        orchestrator.resolve("PV_LATTICE_FOLD", "missing-gpu")
    with pytest.raises(ValueError, match="does not support"):
        orchestrator.resolve("LUCAS_PV_SCALING", "fake-gpu")
    with pytest.raises(ValueError, match="no execution surface"):
        orchestrator.resolve("UNKNOWN_WORKLOAD", None)


def test_phylotaxis_store_and_theseus_retrieve_via_native_backend():
    backend = NativeMathReferenceBackend()
    store = backend.execute(
        json.dumps({"data": "base64:" + base64.b64encode(b"golden").decode()}).encode(),
        "PHYLOTAXIS_STORE",
    )
    record = store["theseus_record"]
    assert store["storage"] == "ovid-phyllotaxis"
    assert 0 <= record["coordinate"]["lane"] < 32
    retrieved = backend.execute(
        json.dumps({"object_id": record["object_id"]}).encode(), "THESEUS_RETRIEVE"
    )
    assert retrieved["digest_verified"] is True
    assert base64.b64decode(retrieved["data"][7:]) == b"golden"
    with pytest.raises(ValueError, match="not stored"):
        backend.execute(
            json.dumps(
                {"object_id": record["object_id"], "tenant_id": "other"}
            ).encode(),
            "THESEUS_RETRIEVE",
        )


def test_auto_select_climbs_into_client_accelerator_when_provisioned():
    router = ExecutionRouter()
    orchestrator = QiGPUOrchestrator(router)
    assert orchestrator.auto_select("PV_LATTICE_FOLD") == (
        "python-math-reference",
        "cpu-substrate",
    )
    router.register_backend(FakeAccelerator())
    assert orchestrator.auto_select("PV_LATTICE_FOLD") == (
        "fake-gpu",
        "client-accelerator",
    )
    # Workloads the accelerator does not support stay on the CPU substrate.
    assert orchestrator.auto_select("LUCAS_PV_SCALING") == (
        "python-math-reference",
        "cpu-substrate",
    )
    with pytest.raises(ValueError, match="no execution surface"):
        orchestrator.auto_select("UNKNOWN_WORKLOAD")


def test_trinity_store_option_persists_folded_state():
    backend = NativeMathReferenceBackend()
    result = backend.execute(
        json.dumps(
            {
                "increment": 479,
                "store": True,
                "values": [{"a": 1, "b": 0, "denominator": 1}],
            }
        ).encode(),
        "TRINITY_SCALE_FOLD_STORE",
    )
    storage = result["storage"]
    assert storage["theseus_record"]["scale_index"] == 479
    retrieved = backend.execute(
        json.dumps(
            {
                "object_id": storage["theseus_record"]["object_id"],
                "tenant_id": "trinity",
            }
        ).encode(),
        "THESEUS_RETRIEVE",
    )
    assert json.loads(base64.b64decode(retrieved["data"][7:])) == result["state"]
