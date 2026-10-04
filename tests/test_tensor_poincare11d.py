"""Production boundary tests for Tensor transport of canonical 11-D state."""

from __future__ import annotations

import numpy as np
import pytest

from tensor.contracts import Precision
from tensor.errors import TensorValidationError
from tensor.poincare11d import (
    PoincareRole,
    prepare_poincare11d_transport,
)
from toe import poincare_golden_11d as canonical
from millennium import poincare_golden_11d as compatibility


def _state() -> np.ndarray:
    return np.array([1.0 + i / 13.0 for i in range(11)], dtype=np.float64)


def test_authoritative_state_remains_float64_and_bit_exact():
    state = _state()
    transport = prepare_poincare11d_transport(state, role="structural")
    assert transport.data.dtype == np.float64
    assert np.array_equal(transport.data, state)
    assert transport.authoritative is True
    assert transport.lossy is False
    assert transport.backend_required == "numpy-cpu"
    assert transport.measured_max_abs_error == 0.0


@pytest.mark.parametrize("role", ["structural", "certifying"])
def test_authoritative_roles_reject_float32(role):
    with pytest.raises(TensorValidationError, match="cannot be downcast"):
        prepare_poincare11d_transport(
            _state(),
            role=role,
            precision=Precision.FLOAT32,
            allow_lossy=True,
            max_abs_error=1.0,
        )


@pytest.mark.parametrize("backend", ["chronus-opencl", "chronus-cuda", "chronus-metal"])
def test_float64_rejects_uncertified_chronus_backends(backend):
    with pytest.raises(TensorValidationError, match="numerically certified"):
        prepare_poincare11d_transport(
            _state(), role="structural", backend_required=backend
        )


def test_non_authoritative_float32_requires_explicit_residual_policy():
    with pytest.raises(TensorValidationError, match="allow_lossy"):
        prepare_poincare11d_transport(
            _state(), role="decorative", precision="float32", max_abs_error=1.0
        )
    with pytest.raises(TensorValidationError, match="max_abs_error"):
        prepare_poincare11d_transport(
            _state(), role="decorative", precision="float32", allow_lossy=True
        )


def test_non_authoritative_float32_records_measured_residual():
    transport = prepare_poincare11d_transport(
        _state(),
        role=PoincareRole.PARAMETRIC,
        precision=Precision.FLOAT32,
        backend_required="chronus-opencl",
        allow_lossy=True,
        max_abs_error=1e-6,
    )
    assert transport.data.dtype == np.float32
    assert transport.authoritative is False
    assert transport.lossy is True
    assert 0.0 < transport.measured_max_abs_error <= 1e-6
    assert transport.vector_count == 1
    assert transport.as_dict()["truth_class"] == "measured"


def test_float32_fails_when_measured_residual_exceeds_bound():
    state = _state()
    with pytest.raises(TensorValidationError, match="exceeds declared bound"):
        prepare_poincare11d_transport(
            state,
            role="parametric",
            precision="float32",
            allow_lossy=True,
            max_abs_error=0.0,
        )


@pytest.mark.parametrize(
    "bad",
    [np.zeros(10), np.zeros((2, 10)), np.full(11, np.nan), np.full(11, np.inf)],
)
def test_invalid_or_nonfinite_inputs_fail_closed(bad):
    with pytest.raises(TensorValidationError):
        prepare_poincare11d_transport(bad, role="structural")


def test_batched_transport_is_flat_contiguous_and_counted():
    batch = np.vstack([_state(), _state() * 2.0])[:, ::-1][:, ::-1]
    transport = prepare_poincare11d_transport(batch, role="certifying")
    assert transport.data.shape == (22,)
    assert transport.data.flags.c_contiguous
    assert transport.vector_count == 2


def test_millennium_namespace_is_the_canonical_fail_closed_surface():
    assert compatibility.to_gpu_input is canonical.to_gpu_input
    assert compatibility.fold_poincare_11d_vector is canonical.fold_poincare_11d_vector
    with pytest.raises(ValueError, match="role"):
        compatibility.to_gpu_input(_state())
    payload = compatibility.to_gpu_input(
        _state(), role="decorative", allow_lossy=True
    )
    assert payload.dtype == np.float32
