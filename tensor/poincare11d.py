"""Production transport policy for the canonical 11-D Poincare substrate.

The mathematical owner remains :mod:`toe.poincare_golden_11d`.  This module
adds the logical Tensor-layer policy that decides whether a state may cross a
hardware transport boundary.  It does not duplicate the fold, metric, or
certificate mathematics.

Structural and certifying state is authoritative Float64 and host/reference
only until a separately implemented and numerically certified FP64 Chronus
backend exists.  Decorative and parametric state may use Float32 only with an
explicit lossy opt-in and a measured residual bound.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any

import numpy as np

from toe.poincare_golden_11d import to_authoritative_input, to_gpu_input

from .contracts import Precision
from .errors import TensorValidationError


class PoincareRole(str, Enum):
    """Semantic authority carried by an 11-D state."""

    STRUCTURAL = "structural"
    CERTIFYING = "certifying"
    DECORATIVE = "decorative"
    PARAMETRIC = "parametric"

    @property
    def authoritative(self) -> bool:
        return self in {PoincareRole.STRUCTURAL, PoincareRole.CERTIFYING}


_REFERENCE_BACKEND = "numpy-cpu"
_FLOAT32_BACKENDS = frozenset(
    {"numpy-cpu", "chronus-opencl", "chronus-cuda", "chronus-metal"}
)


@dataclass(frozen=True)
class Poincare11DTransport:
    """Validated payload plus the evidence needed to interpret it."""

    data: np.ndarray
    role: PoincareRole
    precision: Precision
    backend_required: str
    authoritative: bool
    lossy: bool
    measured_max_abs_error: float

    def __post_init__(self) -> None:
        if self.data.dtype != np.dtype(self.precision.value):
            raise TensorValidationError("transport dtype disagrees with declared precision")
        if self.data.ndim != 1 or self.data.size % 11:
            raise TensorValidationError("transport must be a flat sequence of 11-D vectors")
        if not self.data.flags.c_contiguous:
            raise TensorValidationError("transport must be C-contiguous")
        if not np.isfinite(self.data).all():
            raise TensorValidationError("transport contains non-finite values")
        if self.authoritative != self.role.authoritative:
            raise TensorValidationError("authority flag disagrees with the semantic role")
        if self.authoritative and (self.precision is not Precision.FLOAT64 or self.lossy):
            raise TensorValidationError("authoritative 11-D state must remain lossless Float64")

    @property
    def vector_count(self) -> int:
        return self.data.size // 11

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role.value,
            "precision": self.precision.value,
            "backend_required": self.backend_required,
            "authoritative": self.authoritative,
            "lossy": self.lossy,
            "measured_max_abs_error": self.measured_max_abs_error,
            "vector_count": self.vector_count,
            "truth_class": "measured",
        }


def _role(value: PoincareRole | str) -> PoincareRole:
    try:
        return value if isinstance(value, PoincareRole) else PoincareRole(value)
    except (TypeError, ValueError):
        raise TensorValidationError(f"unsupported 11-D role {value!r}") from None


def _precision(value: Precision | str) -> Precision:
    try:
        return value if isinstance(value, Precision) else Precision(value)
    except (TypeError, ValueError):
        raise TensorValidationError(f"unsupported 11-D precision {value!r}") from None


def _flat_float64(x: Any) -> np.ndarray:
    arr = np.asarray(x, dtype=np.float64)
    if arr.ndim == 1:
        if arr.shape != (11,):
            raise TensorValidationError(f"expected shape (11,) or (N, 11), got {arr.shape}")
        arr = arr.reshape(1, 11)
    elif arr.ndim != 2 or arr.shape[1] != 11:
        raise TensorValidationError(f"expected shape (11,) or (N, 11), got {arr.shape}")
    if not np.isfinite(arr).all():
        raise TensorValidationError("11-D input contains non-finite values")
    return np.ascontiguousarray(arr.ravel())


def prepare_poincare11d_transport(
    x: Any,
    *,
    role: PoincareRole | str,
    precision: Precision | str = Precision.FLOAT64,
    backend_required: str = _REFERENCE_BACKEND,
    allow_lossy: bool = False,
    max_abs_error: float | None = None,
) -> Poincare11DTransport:
    """Validate and encode an 11-D transport without crossing its authority boundary.

    Float64 is the production default.  No current Chronus backend is accepted
    for Float64 because device extension presence is not numerical
    certification.  Float32 is restricted to non-authoritative roles and
    requires both explicit opt-in and a finite measured-error ceiling.
    """

    semantic_role = _role(role)
    dtype = _precision(precision)
    if not isinstance(backend_required, str) or not backend_required.strip():
        raise TensorValidationError("backend_required must be a non-empty string")

    source = _flat_float64(x)

    if dtype is Precision.FLOAT64:
        if backend_required != _REFERENCE_BACKEND:
            raise TensorValidationError(
                "11-D Float64 is host/reference-only until an FP64 Chronus path is "
                "implemented and numerically certified"
            )
        if semantic_role.authoritative:
            payload = to_authoritative_input(source.reshape(-1, 11), role=semantic_role.value)
        else:
            payload = source
        return Poincare11DTransport(
            data=payload,
            role=semantic_role,
            precision=dtype,
            backend_required=backend_required,
            authoritative=semantic_role.authoritative,
            lossy=False,
            measured_max_abs_error=0.0,
        )

    if dtype is not Precision.FLOAT32:
        raise TensorValidationError("11-D transport currently supports only Float64 or Float32")
    if semantic_role.authoritative:
        raise TensorValidationError(
            f"role={semantic_role.value!r} is authoritative and cannot be downcast to Float32"
        )
    if backend_required not in _FLOAT32_BACKENDS:
        raise TensorValidationError(f"unsupported Float32 tensor backend {backend_required!r}")
    if not allow_lossy:
        raise TensorValidationError("Float32 transport requires allow_lossy=True")
    if max_abs_error is None or not math.isfinite(max_abs_error) or max_abs_error < 0:
        raise TensorValidationError("Float32 transport requires finite max_abs_error >= 0")

    payload = to_gpu_input(
        source.reshape(-1, 11), role=semantic_role.value, allow_lossy=True
    )
    measured = float(np.max(np.abs(payload.astype(np.float64) - source)))
    if measured > max_abs_error:
        raise TensorValidationError(
            f"measured Float32 residual {measured} exceeds declared bound {max_abs_error}"
        )
    return Poincare11DTransport(
        data=payload,
        role=semantic_role,
        precision=dtype,
        backend_required=backend_required,
        authoritative=False,
        lossy=True,
        measured_max_abs_error=measured,
    )


__all__ = ["PoincareRole", "Poincare11DTransport", "prepare_poincare11d_transport"]
