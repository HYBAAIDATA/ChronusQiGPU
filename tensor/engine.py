"""Execution engine: validate, route, run, measure, and attest one request."""

from __future__ import annotations

import hashlib
from typing import Optional, Sequence

from .backends import BackendRegistry
from .contracts import (
    BackendIdentity,
    ModelIdentity,
    ProvenanceRecord,
    TensorRequest,
    TensorResult,
    TruthClass,
)
from .router import default_registry, route
from .runtime import CancellationToken, timed_execute


def _digest(value: object) -> str:
    return hashlib.sha256(repr(value).encode("utf-8")).hexdigest()


def execute(
    request: TensorRequest,
    inputs: Sequence[object],
    *,
    model: Optional[ModelIdentity] = None,
    registry: Optional[BackendRegistry] = None,
    cancel_token: Optional[CancellationToken] = None,
) -> TensorResult:
    """Validate, route, execute, and attest ``request`` over ``inputs``.

    ``request`` has already validated its own shapes/dtype/memory/residual
    policy in ``__post_init__``; this function adds backend routing,
    bounded timing, cancellation checks, and provenance.
    """
    registry = registry if registry is not None else default_registry()
    model = model if model is not None else ModelIdentity(model_id="tensor-engine")

    decision = route(request, request.operation, registry)

    def _run():
        return decision.backend.execute(
            request.operation, tuple(inputs), deterministic=request.deterministic
        )

    data, measurement = timed_execute(
        _run,
        operations=request.operation.op_count,
        backend=decision.backend.name,
        model_id=model.model_id,
        timeout_ns=request.timeout_ns,
        cancel_token=cancel_token,
        fallback_used=decision.fallback_used,
        fallback_reason=decision.fallback_reason,
    )

    backend_identity = BackendIdentity(
        name=decision.backend.name,
        backend_class=decision.backend.backend_class,
        device_id=decision.backend.device_id,
    )
    provenance = ProvenanceRecord(
        operation=request.operation.name,
        backend=backend_identity,
        model=model,
        input_digest=_digest(inputs),
        output_digest=_digest(data),
    )
    return TensorResult(
        request=request,
        data=data,
        measurement=measurement,
        provenance=provenance,
        truth_class=TruthClass.MEASURED,
    )


__all__ = ["execute"]
