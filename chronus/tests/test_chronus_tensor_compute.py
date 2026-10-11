from types import SimpleNamespace
import numpy as np
import tensor.backends.chronus_backend as chronus_backend
from tensor.contracts import ExactnessMode, Precision, TensorOperationSpec, TensorShape


def _spec(dtype=Precision.FLOAT32):
    return TensorOperationSpec(name="matmul", input_shapes=(TensorShape((2, 3)), TensorShape((3, 2))),
                               output_shape=TensorShape((2, 2)), dtype=dtype, exactness_mode=ExactnessMode.EXACT, op_count=24)


class _Probe:
    def as_dict(self): return {"available": True, "device_id": "opencl:test:gpu", "device_name": "test-gpu", "platform_name": "test", "reason": ""}


class _Runtime:
    device_id = "opencl:test:gpu"

    def execute(self, operation, inputs, input_shapes, output_shape):
        del input_shapes, output_shape
        if operation != "matmul":
            raise AssertionError(operation)
        return np.asarray(inputs[0], dtype=np.float32) @ np.asarray(inputs[1], dtype=np.float32)


def test_chronus_backend_wires_runtime(monkeypatch):
    module = SimpleNamespace(probe=lambda: _Probe(), get_runtime=lambda: _Runtime())
    monkeypatch.setattr(chronus_backend, "import_module", lambda name: module)
    backend = chronus_backend.ChronusBackend()
    spec = _spec()
    assert backend.is_available() is True and backend.supports(spec)
    a = np.arange(6, dtype=np.float32).reshape(2, 3)
    b = np.arange(6, dtype=np.float32).reshape(3, 2)
    np.testing.assert_array_equal(backend.execute(spec, (a, b), deterministic=True), a @ b)
    assert backend.device_id == "opencl:test:gpu"


def test_chronus_rejects_uncertified_float64(monkeypatch):
    module = SimpleNamespace(probe=lambda: _Probe(), get_runtime=lambda: _Runtime())
    monkeypatch.setattr(chronus_backend, "import_module", lambda name: module)
    assert chronus_backend.ChronusBackend().supports(_spec(Precision.FLOAT64)) is False
