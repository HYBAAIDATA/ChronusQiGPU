from types import SimpleNamespace

import numpy as np

import chronus.native_tensor as native_tensor
import tensor.backends.chronus_native_backend as native_backend
from tensor.contracts import (
    ExactnessMode,
    Precision,
    TensorOperationSpec,
    TensorRequest,
    TensorShape,
)
from tensor.router import default_registry, route


def _spec(dtype=Precision.FLOAT32):
    return TensorOperationSpec(
        name="matmul",
        input_shapes=(TensorShape((2, 3)), TensorShape((3, 2))),
        output_shape=TensorShape((2, 2)),
        dtype=dtype,
        exactness_mode=ExactnessMode.EXACT,
        op_count=24,
    )


class _Probe:
    def __init__(self, backend):
        self.backend = backend

    def as_dict(self):
        return {
            "backend": self.backend,
            "available": True,
            "device_id": f"{self.backend}:test:gpu",
            "device_name": "test-gpu",
            "platform_name": self.backend.upper(),
            "reason": "",
            "opencl_required": False,
        }


class _Runtime:
    def __init__(self, backend):
        self.device_id = f"{backend}:test:gpu"

    def execute(self, operation, inputs, input_shapes, output_shape):
        del input_shapes, output_shape
        if operation != "matmul":
            raise AssertionError(operation)
        return np.asarray(inputs[0], dtype=np.float32) @ np.asarray(
            inputs[1], dtype=np.float32
        )


def _fake_native_module():
    return SimpleNamespace(
        probe_cuda=lambda: _Probe("cuda"),
        probe_metal=lambda: _Probe("metal"),
        get_cuda_runtime=lambda: _Runtime("cuda"),
        get_metal_runtime=lambda: _Runtime("metal"),
    )


def test_cuda_backend_executes_without_opencl(monkeypatch):
    module = _fake_native_module()
    monkeypatch.setattr(native_backend, "import_module", lambda name: module)
    backend = native_backend.create_cuda()
    spec = _spec()
    a = np.arange(6, dtype=np.float32).reshape(2, 3)
    b = np.arange(6, dtype=np.float32).reshape(3, 2)

    assert backend.is_available() is True
    assert backend.supports(spec)
    assert backend.capabilities()["opencl_required"] is False
    np.testing.assert_array_equal(
        backend.execute(spec, (a, b), deterministic=True),
        a @ b,
    )
    assert backend.device_id == "cuda:test:gpu"


def test_metal_backend_executes_without_opencl(monkeypatch):
    module = _fake_native_module()
    monkeypatch.setattr(native_backend, "import_module", lambda name: module)
    backend = native_backend.create_metal()
    spec = _spec()
    a = np.arange(6, dtype=np.float32).reshape(2, 3)
    b = np.arange(6, dtype=np.float32).reshape(3, 2)

    assert backend.is_available() is True
    assert backend.supports(spec)
    assert backend.capabilities()["opencl_required"] is False
    np.testing.assert_array_equal(
        backend.execute(spec, (a, b), deterministic=True),
        a @ b,
    )
    assert backend.device_id == "metal:test:gpu"


def test_native_backends_reject_uncertified_float64(monkeypatch):
    module = _fake_native_module()
    monkeypatch.setattr(native_backend, "import_module", lambda name: module)
    assert native_backend.create_cuda().supports(_spec(Precision.FLOAT64)) is False
    assert native_backend.create_metal().supports(_spec(Precision.FLOAT64)) is False


def test_default_registry_exposes_native_paths_without_reordering_opencl():
    names = default_registry().names()
    assert names[:2] == ("numpy-cpu", "chronus-opencl")
    assert "chronus-cuda" in names
    assert "chronus-metal" in names


def test_explicit_cuda_route_does_not_substitute_opencl(monkeypatch):
    module = _fake_native_module()
    monkeypatch.setattr(native_backend, "import_module", lambda name: module)
    request = TensorRequest(operation=_spec(), backend_required="chronus-cuda")
    decision = route(request, request.operation)
    assert decision.backend.name == "chronus-cuda"
    assert decision.fallback_used is False


def test_cuda_probe_fails_closed_when_runtime_missing(monkeypatch):
    def missing():
        raise ImportError("cupy intentionally absent")

    monkeypatch.setattr(native_tensor, "_load_cupy", missing)
    report = native_tensor.probe_cuda()
    assert report.available is False
    assert report.device_id == "unavailable"
    assert "cupy intentionally absent" in report.reason


def test_cuda_runtime_builds_exact_declared_kernel_set(monkeypatch):
    built = []

    class Device:
        def use(self):
            return None

    class RuntimeApi:
        @staticmethod
        def getDeviceCount():
            return 1

        @staticmethod
        def getDeviceProperties(index):
            assert index == 0
            return {
                "name": b"test-cuda",
                "multiProcessorCount": 32,
                "totalGlobalMem": 1024,
            }

    class Cuda:
        runtime = RuntimeApi()

        @staticmethod
        def Device(index):
            assert index == 0
            return Device()

    class FakeCp:
        cuda = Cuda()

        @staticmethod
        def RawKernel(source, name, options=()):
            assert "tensor_kron_1d_f32" in source
            assert "tensor_kron_2d_f32" in source
            assert options == ("--std=c++11",)
            built.append(name)
            return object()

    monkeypatch.setattr(native_tensor, "_load_cupy", lambda: FakeCp())
    runtime = native_tensor.ChronusCudaTensorRuntime()
    assert set(built) == set(runtime._KERNEL_NAMES)
    assert "tensor_kron_f32" not in built
    assert "tensor_kron_1d_f32" in built
    assert "tensor_kron_2d_f32" in built


def test_metal_probe_requires_darwin(monkeypatch):
    monkeypatch.setattr(native_tensor.platform, "system", lambda: "Linux")
    report = native_tensor.probe_metal()
    assert report.available is False
    assert report.device_id == "unavailable"
    assert "Darwin" in report.reason
