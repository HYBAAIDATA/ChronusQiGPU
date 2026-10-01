"""Production runtime behaviour for tensor operations.

Provides monotonic/perf-counter timing, cancellation/timeout checks,
bounded memory preflight, and structured telemetry records. Nothing here
depends on a specific backend.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from .contracts import MemoryBudget, TensorMeasurement, TensorShape, estimate_bytes, Precision
from .errors import TensorCancelledError, TensorTimeoutError


class CancellationToken:
    """A cooperative cancellation flag checked at safe points during execution."""

    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def check(self) -> None:
        if self._cancelled:
            raise TensorCancelledError("tensor operation was cancelled")


@dataclass
class Deadline:
    """A monotonic deadline derived from a declared timeout in nanoseconds."""

    timeout_ns: Optional[int]
    started_ns: int = field(default_factory=time.monotonic_ns)

    def check(self) -> None:
        if self.timeout_ns is None:
            return
        elapsed = time.monotonic_ns() - self.started_ns
        if elapsed > self.timeout_ns:
            raise TensorTimeoutError(
                f"tensor operation exceeded timeout of {self.timeout_ns} ns "
                f"(elapsed {elapsed} ns)"
            )


def preflight_memory(
    shapes: tuple[TensorShape, ...], dtype: Precision, budget: MemoryBudget
) -> int:
    """Estimate memory for ``shapes`` at ``dtype`` and fail closed over ``budget``."""
    estimated = estimate_bytes(shapes, dtype)
    budget.check(estimated)
    return estimated


def timed_execute(
    fn: Callable[[], Any],
    *,
    operations: int,
    backend: str,
    model_id: str = "",
    timeout_ns: Optional[int] = None,
    cancel_token: Optional[CancellationToken] = None,
    fallback_used: bool = False,
    fallback_reason: str = "",
) -> tuple[Any, TensorMeasurement]:
    """Run ``fn`` under a deadline/cancellation check and measure elapsed time.

    Timeout and cancellation are checked immediately before and after the
    call (cooperative, not preemptive); callers that can check mid-operation
    should pass ``cancel_token``/``Deadline`` into ``fn`` itself.
    """
    if cancel_token is not None:
        cancel_token.check()
    deadline = Deadline(timeout_ns)
    deadline.check()
    started_ns = time.perf_counter_ns()
    result = fn()
    elapsed_ns = max(1, time.perf_counter_ns() - started_ns)
    deadline.check()
    if cancel_token is not None:
        cancel_token.check()
    measurement = TensorMeasurement(
        operations=operations,
        elapsed_ns=elapsed_ns,
        backend=backend,
        model_id=model_id,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
    )
    return result, measurement


def telemetry_record(measurement: TensorMeasurement, **extra: Any) -> Dict[str, Any]:
    """Structured, append-only telemetry record for one executed operation."""
    record = measurement.as_dict()
    record.update(extra)
    return record


__all__ = [
    "CancellationToken",
    "Deadline",
    "preflight_memory",
    "timed_execute",
    "telemetry_record",
]
