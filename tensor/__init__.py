"""``tensor`` — the canonical, backend-neutral logical Tensor layer.

Layering (see ``docs/TENSOR_ARCHITECTURE.md`` for the full policy):

* ``tensor`` (this package) is the logical layer: typed contracts, backend
  protocol/registry, deterministic router, and production runtime behaviour
  (timing, cancellation, memory preflight, telemetry).
* ``gpu``/``chronus`` are execution backends only. ``gpu.tensor`` is a
  deprecated thin re-export of this package.
* ``kellogg`` (and the in-tree VQC package,
  ``turing_universal_quantum_computer``) remain the exact mathematical
  substrates; this package bridges to them lazily instead of re-implementing
  them (``tensor.kellogg_bridge``).
* Mining is a consumer/advisory use case only: ``tensor.advisor`` re-exports
  the existing, independently-tested permutation-only advisory boundary in
  ``hyba.hybrid.tensor_advisor``.

Public API re-exported here is intentionally small; deeper surfaces
(backends, router internals, kellogg bridges, the advisor, the capability
manifest) are imported from their own submodules.
"""

from __future__ import annotations

from .contracts import (
    BackendIdentity,
    DEFAULT_MAX_TENSOR_BYTES,
    DependencyScope,
    ExactnessMode,
    MAX_TENSOR_ELEMENTS,
    MemoryBudget,
    ModelIdentity,
    Precision,
    ProvenanceRecord,
    ResidualBounds,
    TensorMeasurement,
    TensorOperationSpec,
    TensorOpKind,
    TensorRequest,
    TensorResult,
    TensorShape,
    TruthClass,
    estimate_bytes,
)
from .api import TensorRuntime, default_runtime
from .benchmarks import BenchmarkReport, BenchmarkRow, run_benchmarks
from .dependency import DependencyCone, InputCone, dependency_cone
from .engine import execute
from .errors import (
    TensorBackendUnavailableError,
    TensorCancelledError,
    TensorError,
    TensorExactnessError,
    TensorMemoryError,
    TensorTimeoutError,
    TensorValidationError,
    TensorVerificationError,
)
from .receipts import ExecutionReceipt
from .router import RouteDecision, default_registry, route
from .runtime import CancellationToken, Deadline, preflight_memory, telemetry_record, timed_execute
from .verification import VerificationVerdict

__all__ = [
    "BackendIdentity",
    "BenchmarkReport",
    "BenchmarkRow",
    "CancellationToken",
    "DEFAULT_MAX_TENSOR_BYTES",
    "Deadline",
    "DependencyCone",
    "DependencyScope",
    "ExactnessMode",
    "MAX_TENSOR_ELEMENTS",
    "MemoryBudget",
    "ModelIdentity",
    "Precision",
    "ProvenanceRecord",
    "ResidualBounds",
    "RouteDecision",
    "TensorBackendUnavailableError",
    "TensorCancelledError",
    "TensorError",
    "TensorExactnessError",
    "InputCone",
    "ExecutionReceipt",
    "TensorMeasurement",
    "TensorMemoryError",
    "TensorOperationSpec",
    "TensorOpKind",
    "TensorRequest",
    "TensorResult",
    "TensorRuntime",
    "TensorShape",
    "TensorTimeoutError",
    "TensorValidationError",
    "TensorVerificationError",
    "TruthClass",
    "VerificationVerdict",
    "default_registry",
    "default_runtime",
    "dependency_cone",
    "estimate_bytes",
    "execute",
    "preflight_memory",
    "route",
    "run_benchmarks",
    "telemetry_record",
    "timed_execute",
]

__version__ = "0.1.0"
