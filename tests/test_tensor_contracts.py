"""Validation, fail-closed behaviour, and unit correctness of tensor contracts."""

from __future__ import annotations

import pytest

from tensor.contracts import (
    BackendIdentity,
    ExactnessMode,
    MemoryBudget,
    ModelIdentity,
    Precision,
    ProvenanceRecord,
    ResidualBounds,
    TensorMeasurement,
    TensorOperationSpec,
    TensorRequest,
    TensorShape,
    estimate_bytes,
)
from tensor.errors import TensorMemoryError, TensorValidationError


def _spec(**overrides):
    defaults = dict(
        name="matmul",
        input_shapes=(TensorShape((2, 2)), TensorShape((2, 2))),
        output_shape=TensorShape((2, 2)),
        dtype=Precision.FLOAT64,
        exactness_mode=ExactnessMode.EXACT,
        op_count=16,
    )
    defaults.update(overrides)
    return TensorOperationSpec(**defaults)


def test_shape_rejects_non_positive_and_empty_dims():
    with pytest.raises(TensorValidationError):
        TensorShape(())
    with pytest.raises(TensorValidationError):
        TensorShape((0, 2))
    with pytest.raises(TensorValidationError):
        TensorShape((-1,))


def test_shape_size_is_product_of_dims():
    assert TensorShape((2, 3, 4)).size == 24


def test_memory_budget_fails_closed_over_estimate():
    budget = MemoryBudget(100)
    budget.check(100)
    with pytest.raises(TensorMemoryError):
        budget.check(101)


def test_estimate_bytes_rejects_exact_rational_dtype():
    with pytest.raises(TensorValidationError, match="exact-rational"):
        estimate_bytes((TensorShape((2, 2)),), Precision.EXACT_RATIONAL)


def test_residual_bounds_requires_opt_in_and_evidence_for_lossy_mode():
    bounds = ResidualBounds(max_residual=1e-6)
    with pytest.raises(TensorValidationError, match="opt-in"):
        bounds.require_for(ExactnessMode.LOSSY_APPROX)

    bounds_no_measurement = ResidualBounds(max_residual=1e-6, opt_in=True)
    with pytest.raises(TensorValidationError, match="measured residual"):
        bounds_no_measurement.require_for(ExactnessMode.LOSSY_APPROX)

    bounds_over_budget = ResidualBounds(max_residual=1e-6, opt_in=True, measured_residual=1e-3)
    with pytest.raises(TensorValidationError, match="exceeds declared bound"):
        bounds_over_budget.require_for(ExactnessMode.LOSSY_APPROX)

    bounds_ok = ResidualBounds(max_residual=1e-6, opt_in=True, measured_residual=1e-9)
    bounds_ok.require_for(ExactnessMode.LOSSY_APPROX)  # does not raise


def test_residual_bounds_not_required_for_exact_mode():
    ResidualBounds().require_for(ExactnessMode.EXACT)  # does not raise even with defaults


def test_backend_identity_rejects_unknown_backend_class():
    with pytest.raises(TensorValidationError):
        BackendIdentity(name="x", backend_class="quantum_hw_magic", device_id="d")


def test_request_rejects_memory_over_budget_before_any_backend_is_touched():
    spec = _spec(
        input_shapes=(TensorShape((1000, 1000)), TensorShape((1000, 1000))),
        output_shape=TensorShape((1000, 1000)),
    )
    with pytest.raises(TensorMemoryError):
        TensorRequest(operation=spec, memory_budget=MemoryBudget(1024))


def test_request_rejects_lossy_mode_without_opt_in():
    spec = _spec(exactness_mode=ExactnessMode.LOSSY_APPROX)
    with pytest.raises(TensorValidationError, match="opt-in"):
        TensorRequest(operation=spec)


def test_request_accepts_lossy_mode_with_full_evidence():
    spec = _spec(exactness_mode=ExactnessMode.LOSSY_APPROX)
    request = TensorRequest(
        operation=spec,
        residual_bounds=ResidualBounds(max_residual=1e-3, opt_in=True, measured_residual=1e-6),
    )
    assert request.operation is spec


def test_tensor_measurement_tflops_uses_only_declared_ops_and_elapsed_time():
    measurement = TensorMeasurement(
        operations=5_000_000_000_000, elapsed_ns=1_000_000_000, backend="numpy-cpu"
    )
    assert measurement.tflops == pytest.approx(5.0)
    record = measurement.as_dict()
    assert record["hashrate_hps"] is None
    assert record["truth_class"] == "measured"
    assert "hashes" not in record


def test_tensor_measurement_rejects_negative_operations_and_nonpositive_elapsed():
    with pytest.raises(TensorValidationError):
        TensorMeasurement(operations=-1, elapsed_ns=1, backend="b")
    with pytest.raises(TensorValidationError):
        TensorMeasurement(operations=1, elapsed_ns=0, backend="b")
    with pytest.raises(TensorValidationError):
        TensorMeasurement(operations=1, elapsed_ns=1, backend="  ")


def test_tensor_measurement_fallback_requires_a_reason():
    with pytest.raises(TensorValidationError, match="reason"):
        TensorMeasurement(operations=1, elapsed_ns=1, backend="b", fallback_used=True)
    # a reason makes it valid
    TensorMeasurement(
        operations=1, elapsed_ns=1, backend="b", fallback_used=True, fallback_reason="x"
    )


def test_model_identity_requires_nonempty_id():
    with pytest.raises(TensorValidationError):
        ModelIdentity(model_id="   ")


def test_provenance_record_requires_all_digests():
    backend = BackendIdentity(name="numpy-cpu", backend_class="reference", device_id="cpu:0")
    model = ModelIdentity(model_id="m")
    with pytest.raises(TensorValidationError):
        ProvenanceRecord(
            operation="matmul", backend=backend, model=model, input_digest="", output_digest="x"
        )
