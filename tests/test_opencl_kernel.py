"""Exercise the actual kernel on an OpenCL CPU device, never as GPU evidence."""

import random
import json

import pytest
from fastapi.testclient import TestClient

from chronus.backends.lattice import LatticeOverflowError, PhiElement, phi_power, verify_fold
from chronus.backends.opencl_pv import OpenCLPVBackend
from chronus.execution import execution_router
from chronus.service.app import create_app
from chronus.service.dependencies import auth_service, service_config
from chronus.service.routers import workloads
from chronus.service.workload_store import SQLiteWorkloadStore

cl = pytest.importorskip("pyopencl")
np = pytest.importorskip("numpy")


@pytest.fixture(scope="module")
def cpu_opencl():
    try:
        devices = [
            d for p in cl.get_platforms() for d in p.get_devices()
            if d.type & cl.device_type.CPU
        ]
    except cl.Error:
        devices = []
    if not devices:
        pytest.skip("No OpenCL CPU device available")
    from importlib.resources import files

    backend = OpenCLPVBackend.__new__(OpenCLPVBackend)
    backend._cl, backend._np = cl, np
    backend.device = devices[0]
    backend.context = cl.Context([backend.device])
    backend.queue = cl.CommandQueue(backend.context)
    source = files("chronus.kernels").joinpath("pv_lattice.cl").read_text()
    backend.program = cl.Program(backend.context, source).build()
    return backend


@pytest.mark.parametrize("order", [0, 1, 2, 70, 90, 92, 130, 180, 260, 360])
def test_real_kernel_matches_python_reference(cpu_opencl, order):
    values = [PhiElement(1, 0), PhiElement(-1, 1, 3), PhiElement(0, -1, 5)]
    outputs, widths = cpu_opencl._dispatch(values, phi_power(order))
    verify_fold(values, outputs, order)
    assert sum(widths.values()) == len(values)
    if order == 360:
        assert widths["requires_256_bits"] > 0


def test_real_kernel_random_inputs_and_boundaries(cpu_opencl):
    rng = random.Random(590)
    values = [PhiElement(rng.randrange(-(2**63), 2**63), rng.randrange(-(2**63), 2**63)) for _ in range(100)]
    values += [PhiElement(-(2**63), 0), PhiElement(2**63 - 1, -1)]
    for order in (0, 1, 50, 90, 180):
        outputs, _ = cpu_opencl._dispatch(values, phi_power(order))
        verify_fold(values, outputs, order)


def test_real_kernel_rejects_256_bit_overflow(cpu_opencl):
    with pytest.raises(LatticeOverflowError):
        cpu_opencl._dispatch([PhiElement(2**63 - 1, 2**63 - 1)], phi_power(360))


def test_dispatch_receipt_and_norm_are_verified_on_cpu_runtime(cpu_opencl, monkeypatch):
    monkeypatch.setattr(cpu_opencl, "execution_mode", "SOFTWARE_EXECUTION")
    values = [PhiElement(-17, 29, 11), PhiElement(8, -9, 7)]
    outputs, receipt = cpu_opencl.dispatch_pv_fold(values, 150)
    verify_fold(values, outputs, 150)
    assert receipt["norm_invariant_verified"] is True
    assert receipt["execution_mode"] == "SOFTWARE_EXECUTION"
    assert receipt["device"]["zero_copy_verified"] is False
    assert sum(receipt["intermediate_width_counts"].values()) == 2


@pytest.mark.parametrize("corrupt", [False, True])
def test_api_path_rejects_mismatched_opencl_result(cpu_opencl, tmp_path, monkeypatch, corrupt):
    monkeypatch.setattr(cpu_opencl, "execution_mode", "SOFTWARE_EXECUTION")
    monkeypatch.setattr(service_config, "execution_backend_url", None)
    monkeypatch.setattr(
        workloads, "workload_store", SQLiteWorkloadStore(str(tmp_path / "test.sqlite3"))
    )
    monkeypatch.setitem(execution_router._backends, cpu_opencl.name, cpu_opencl)
    if corrupt:
        monkeypatch.setattr(
            cpu_opencl, "_dispatch",
            lambda values, factor: ([PhiElement(-1, 0)], {"fit_int64": 1}),
        )
    auth_service.register_tenant("opencl-test", "opencl-test-token")
    payload = json.dumps({
        "order": 90,
        "values": [{"a": "1", "b": "0", "denominator": "1"}],
    })
    with TestClient(create_app()) as client:
        response = client.post(
            "/workloads/submit",
            headers={"Authorization": "Bearer opencl-test-token"},
            json={
                "tenant_id": "opencl-test",
                "workload_type": "PV_LATTICE_FOLD",
                "backend_preference": "opencl-pv",
                "payload_bytes": payload,
            },
        )
    assert response.status_code == (502 if corrupt else 202)
    if not corrupt:
        receipt = response.json()["result"]
        assert receipt["execution_mode"] == "SOFTWARE_EXECUTION"
        assert receipt["result"]["norm_invariant_verified"] is True
        assert receipt["result"]["values"][0]["b"] == "2880067194370816120"
