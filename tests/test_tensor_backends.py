"""Backend protocol, registry, and deterministic routing behaviour."""

from __future__ import annotations

import numpy as np
import pytest

from tensor.backends import BackendRegistry
from tensor.backends.chronus_backend import ChronusBackend
from tensor.backends.numpy_backend import NumpyBackend
from tensor.contracts import (
    ExactnessMode,
    Precision,
    TensorOperationSpec,
    TensorRequest,
    TensorShape,
)
from tensor.errors import TensorBackendUnavailableError, TensorValidationError
from tensor.router import default_registry, route


def _matmul_spec(dtype=Precision.FLOAT64):
    return TensorOperationSpec(
        name="matmul",
        input_shapes=(TensorShape((2, 2)), TensorShape((2, 2))),
        output_shape=TensorShape((2, 2)),
        dtype=dtype,
        exactness_mode=ExactnessMode.EXACT,
        op_count=16,
    )


def test_numpy_backend_is_always_available_and_deterministic():
    backend = NumpyBackend()
    assert backend.is_available() is True
    assert backend.backend_class == "reference"
    a = np.array([[1.0, 2.0], [3.0, 4.0]])
    b = np.array([[1.0, 0.0], [0.0, 1.0]])
    op = _matmul_spec()
    result_1 = backend.execute(op, (a, b), deterministic=True)
    result_2 = backend.execute(op, (a, b), deterministic=True)
    np.testing.assert_array_equal(result_1, result_2)
    np.testing.assert_array_equal(result_1, a)


def test_numpy_backend_rejects_unsupported_operation():
    backend = NumpyBackend()
    op = TensorOperationSpec(
        name="not-a-real-op",
        input_shapes=(TensorShape((2,)),),
        output_shape=TensorShape((2,)),
        dtype=Precision.FLOAT64,
        exactness_mode=ExactnessMode.EXACT,
        op_count=1,
    )
    assert backend.supports(op) is False
    with pytest.raises(TensorValidationError):
        backend.execute(op, (np.zeros(2),), deterministic=True)


def test_numpy_backend_rejects_shape_mismatch():
    backend = NumpyBackend()
    op = _matmul_spec()
    with pytest.raises(TensorValidationError):
        backend.execute(op, (np.zeros((3, 3)), np.zeros((2, 2))), deterministic=True)


def test_chronus_backend_reports_unavailable_honestly_without_hardware():
    backend = ChronusBackend()
    # In this sandbox there is no OpenCL device; this must be False, never
    # fabricated as True, and must never raise.
    assert backend.is_available() is False
    assert backend.backend_class == "hardware"
    assert backend.capabilities()["status"] == "hardware-evidence-required"


def test_chronus_backend_execute_fails_closed_when_unavailable():
    backend = ChronusBackend()
    op = _matmul_spec()
    with pytest.raises(TensorBackendUnavailableError):
        backend.execute(op, (np.eye(2), np.eye(2)), deterministic=True)


def test_registry_reports_health_without_fabricating_success():
    registry = default_registry()
    report = registry.health_report()
    assert report["numpy-cpu"]["available"] is True
    assert report["chronus-opencl"]["available"] is False
    assert report["chronus-opencl"]["error"] is None  # honestly unavailable, not broken


def test_registry_get_unknown_backend_fails_closed():
    registry = BackendRegistry()
    with pytest.raises(TensorBackendUnavailableError):
        registry.get("does-not-exist")


def test_route_uses_numpy_by_default():
    request = TensorRequest(operation=_matmul_spec())
    decision = route(request, request.operation)
    assert decision.backend.name == "numpy-cpu"
    assert decision.fallback_used is False


def test_route_fails_closed_when_explicit_backend_is_unavailable():
    request = TensorRequest(operation=_matmul_spec(), backend_required="chronus-opencl")
    with pytest.raises(TensorBackendUnavailableError, match="explicitly required"):
        route(request, request.operation)


def test_route_rejects_unsupported_explicit_backend():
    request = TensorRequest(operation=_matmul_spec(), backend_required="numpy-cpu")
    unsupported_op = TensorOperationSpec(
        name="not-supported",
        input_shapes=(TensorShape((2,)),),
        output_shape=TensorShape((2,)),
        dtype=Precision.FLOAT64,
        exactness_mode=ExactnessMode.EXACT,
        op_count=1,
    )
    with pytest.raises(TensorBackendUnavailableError, match="does not support"):
        route(request, unsupported_op)


def test_route_does_not_fallback_silently_without_policy_opt_in():
    registry = BackendRegistry()
    registry.register("chronus-opencl", ChronusBackend, priority=10)
    registry.register("numpy-cpu", NumpyBackend, priority=20)
    request = TensorRequest(operation=_matmul_spec(), allow_fallback=False)
    with pytest.raises(TensorBackendUnavailableError, match="fallback is not permitted"):
        route(request, request.operation, registry)


def test_route_records_fallback_when_policy_explicitly_allows_it():
    registry = BackendRegistry()
    registry.register("chronus-opencl", ChronusBackend, priority=10)
    registry.register("numpy-cpu", NumpyBackend, priority=20)
    request = TensorRequest(operation=_matmul_spec(), allow_fallback=True)
    decision = route(request, request.operation, registry)
    assert decision.backend.name == "numpy-cpu"
    assert decision.fallback_used is True
    assert "fell back" in decision.fallback_reason
