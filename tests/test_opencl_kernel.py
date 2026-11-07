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

try:
    import pyopencl as cl
except ImportError:
    cl = None

try:
    import numpy as np
except ImportError:
    np = None

if cl is None or np is None:
    pytestmark = pytest.mark.skip(reason="pyopencl or numpy not available")



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
        assert widths["executed_256_bit"] > 0


def test_real_kernel_random_inputs_and_boundaries(cpu_opencl):
    rng = random.Random(590)
    values = [PhiElement(rng.randrange(-(2**63), 2**63), rng.randrange(-(2**63), 2**63)) for _ in range(100)]
    values += [PhiElement(-(2**63), 0), PhiElement(2**63 - 1, -1)]
    for order in (0, 1, 50, 90, 180):
        outputs, _ = cpu_opencl._dispatch(values, phi_power(order))
        verify_fold(values, outputs, order)


@pytest.mark.parametrize(
    ("factor", "values", "expected_tiers"),
    [
        (PhiElement(1, 0), [PhiElement(-(2**63), 2**63 - 1)],
         {"executed_64_bit": 1, "executed_128_bit": 0, "executed_256_bit": 0}),
        (PhiElement(2, 2), [PhiElement(2**63 - 1, -(2**63 - 1))],
         {"executed_64_bit": 0, "executed_128_bit": 1, "executed_256_bit": 0}),
        (PhiElement(2**64, 0), [PhiElement(-(2**63), 0)],
         {"executed_64_bit": 0, "executed_128_bit": 1, "executed_256_bit": 0}),
        (PhiElement(2**65, 0), [PhiElement(-(2**63), 0)],
         {"executed_64_bit": 0, "executed_128_bit": 0, "executed_256_bit": 1}),
        (PhiElement(1, 1), [PhiElement(1, 1), PhiElement(2**63 - 1, 2**63 - 1)],
         {"executed_64_bit": 1, "executed_128_bit": 1, "executed_256_bit": 0}),
        (PhiElement(2**127, 0), [PhiElement(0, 0)],
         {"executed_64_bit": 0, "executed_128_bit": 0, "executed_256_bit": 1}),
    ],
)
def test_real_kernel_execution_tiers(cpu_opencl, factor, values, expected_tiers):
    outputs, tiers = cpu_opencl._dispatch(values, factor)
    assert outputs == [value.multiply(factor) for value in values]
    assert tiers == expected_tiers


def test_real_kernel_rejects_negative_factors(cpu_opencl):
    with pytest.raises(ValueError, match="non-negative"):
        cpu_opencl._dispatch([PhiElement(1, 1)], PhiElement(-1, 0))


def test_real_kernel_random_factors_and_tier_counts(cpu_opencl):
    rng = random.Random(128256)
    values = [
        PhiElement(rng.randrange(-(2**63), 2**63), rng.randrange(-(2**63), 2**63))
        for _ in range(60)
    ] + [PhiElement(0, 0), PhiElement(1, -1), PhiElement(-(2**63), 0)]
    for bits in (1, 31, 63, 64, 65, 100, 126, 128, 180):
        factor = PhiElement(rng.getrandbits(bits), rng.getrandbits(bits))
        outputs, tiers = cpu_opencl._dispatch(values, factor)
        assert outputs == [value.multiply(factor) for value in values]
        expected = dict.fromkeys(tiers, 0)
        for value in values:
            ac, bd = value.a * factor.a, value.b * factor.b
            ad, bc = value.a * factor.b, value.b * factor.a
            intermediates = [ac, bd, ad, bc, ac + bd, ad + bc, ad + bc + bd]
            def fits(width):
                return all(-(2 ** (width - 1)) <= x < 2 ** (width - 1)
                           for x in [factor.a, factor.b, *intermediates])
            tier = 64 if fits(64) else 128 if fits(128) else 256
            expected[f"executed_{tier}_bit"] += 1
        assert tiers == expected


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
    assert sum(receipt["execution_tier_counts"].values()) == 2


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
            lambda values, factor: ([PhiElement(-1, 0)], {"executed_64_bit": 1}),
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
