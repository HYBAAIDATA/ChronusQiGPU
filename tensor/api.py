"""Canonical runtime facade — the single entry point for tensor work.

``TensorRuntime`` joins the three planes this package owns:

* **custody** — operands live as versioned folded blocks in
  ``aethel.fold_store.PersistentFoldStore``; names, not raw arrays, are
  what real callers pass around;
* **execution** — an operation either runs folded-resident through
  :mod:`tensor.folded` (lifted or declared-materializing) or routes a
  validated ``TensorRequest`` through :func:`tensor.engine.execute`;
* **publication** — every result lands atomically: the output block and
  its receipt are committed under one lock, so a request id is never
  visible without its full provenance.

Concurrency safety is structural: the fold store serialises commits on an
RLock and this facade serialises result publication on its own.
Cancellation is cooperative — a ``CancellationToken`` checked before and
after execution, surfaced through the same token the backend path uses.
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np

from aethel.fold_store import PersistentFoldStore
from aethel.phi_fold import PhiFoldError

from .backends import BackendRegistry
from .contracts import (
    ExactnessMode,
    ModelIdentity,
    Precision,
    ResidualBounds,
    TensorOperationSpec,
    TensorRequest,
    TensorShape,
    TruthClass,
)
from .engine import execute as _engine_execute
from .errors import TensorValidationError
from .folded import FOLDED_OPERATOR_CATALOGUE, folded_execute
from .receipts import (
    build_backend_receipt,
    build_folded_receipt,
    logical_bytes,
)
from .router import default_registry
from .runtime import CancellationToken, timed_execute

_DTYPE_NAMES = {
    "float32": np.float32,
    "float64": np.float64,
    "complex64": np.complex64,
    "complex128": np.complex128,
    "int64": np.int64,
    "int32": np.int32,
    "uint64": np.uint64,
}

_PRECISION_FOR = {
    np.dtype(np.float32): Precision.FLOAT32,
    np.dtype(np.float64): Precision.FLOAT64,
    np.dtype(np.complex64): Precision.COMPLEX64,
    np.dtype(np.complex128): Precision.COMPLEX128,
}


class TensorRuntime:
    """Single canonical entry for custody, execution, and publication."""

    def __init__(
        self,
        *,
        store: Optional[PersistentFoldStore] = None,
        registry: Optional[BackendRegistry] = None,
        default_depth: int = 3,
    ) -> None:
        self.store = store if store is not None else PersistentFoldStore()
        self.registry = registry if registry is not None else default_registry()
        self.default_depth = int(default_depth)
        self._lock = threading.RLock()
        self._results: Dict[str, Dict[str, Any]] = {}
        self._tokens: Dict[str, CancellationToken] = {}
        self._custody_handles: Dict[str, Dict[str, Any]] = {}

    # -- custody --------------------------------------------------------

    def store_tensor(
        self,
        name: str,
        array: np.ndarray,
        *,
        depth: Optional[int] = None,
        device_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fold ``array`` into resident custody under ``name``.

        The requested depth is an upper bound — arrays too small to split
        that many times fold as deep as they allow, never shallower.
        """
        arr = np.asarray(array)
        want = self.default_depth if depth is None else int(depth)
        block = None
        last_err: Optional[Exception] = None
        for candidate in range(want, 0, -1):
            try:
                block = self.store.create(
                    name, arr, depth=candidate, device_id=device_id
                )
                break
            except PhiFoldError as exc:
                last_err = exc
        if block is None:
            raise TensorValidationError(
                f"cannot fold tensor {name!r} at any depth <= {want}: {last_err}"
            )
        return {"name": name, "version": block.current_version,
                "content_hash": self.store.content_hash(name)}

    def read_tensor(self, name: str) -> np.ndarray:
        return self.store.read(name)

    def tensor_names(self) -> Tuple[str, ...]:
        return self.store.names()

    def register_custody(self, name: str, state: Any) -> Dict[str, Any]:
        """Register an external custody handle (e.g. an exact-plane
        ExactFoldState) so provenance can name it. The payload stays in its
        owner plane; the runtime records its identity, not a copy."""
        handle = {
            "name": name,
            "type": type(state).__name__,
            "content_hash": getattr(state, "content_hash", ""),
            "original_shape": tuple(getattr(state, "original_shape", getattr(state, "shape", ()))),
            "depth": int(getattr(state, "depth", 0)),
        }
        with self._lock:
            self._custody_handles[name] = handle
        return handle

    # -- capabilities ---------------------------------------------------

    def capabilities(self) -> Dict[str, Any]:
        """What this runtime can execute — honest per-op declaration."""
        return {
            "schema_version": "tensor.capabilities/1",
            "operators": {
                name: {
                    "kind": op.kind.value,
                    "arity": op.arity,
                    "path": (
                        "lifted"
                        if op.lifted is not None
                        else "committed" if op.committed is not None else "materialized"
                    ),
                    "bit_identical": op.bit_identical,
                    "domain": op.domain,
                }
                for name, op in FOLDED_OPERATOR_CATALOGUE.items()
            },
            "backends": sorted(self.registry.names()),
            "dtypes": sorted(_DTYPE_NAMES),
            "truth_classes": [t.value for t in TruthClass],
            "residency": {
                "blocks": self.store.status()["blocks"],
                "external_custody": dict(self._custody_handles),
            },
        }

    # -- execution ------------------------------------------------------

    def cancel(self, request_id: str) -> bool:
        """Cooperatively cancel an in-flight or future request by id."""
        with self._lock:
            token = self._tokens.get(request_id)
            if token is None:
                return False
            token.cancel()
            return True

    def result(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Atomic result lookup: id → full receipt, or None until published."""
        with self._lock:
            record = self._results.get(request_id)
            return None if record is None else dict(record)

    def execute(
        self,
        operation: str,
        operands: Sequence[Any],
        *,
        out: Optional[str] = None,
        request_id: Optional[str] = None,
        dtype: str = "float64",
        timeout_ns: Optional[int] = None,
        backend_required: Optional[str] = None,
        deterministic: bool = True,
        model_id: str = "tensor-runtime",
        cancel_token: Optional[CancellationToken] = None,
        op_count: Optional[int] = None,
        exactness: str = "exact",
    ) -> Dict[str, Any]:
        """Execute ``operation`` over resident names or raw arrays.

        When every operand names a resident block the operation runs on
        folded state (lifted when the catalogue promotes it); otherwise the
        operands are treated as arrays and routed through the backend
        engine. Either way the outcome is published atomically: the output
        block and receipt become visible together under ``request_id``.

        ``exactness`` defaults to ``"exact"`` — the ops in the catalogue
        are exact on their inputs. ``"lossy_approx"`` must be requested
        explicitly and carries the contract's opt-in residual bounds; it
        is refused when the caller cannot supply measured evidence.
        """
        request_id = request_id or f"req-{uuid.uuid4().hex[:12]}"
        token = cancel_token or CancellationToken()
        with self._lock:
            self._tokens[request_id] = token
        operands = tuple(operands)
        resident = all(
            isinstance(o, str) and o in self.tensor_names() for o in operands
        ) and len(operands) > 0
        if resident:
            record = self._execute_folded(
                request_id, operation, operands, out=out, token=token,
                timeout_ns=timeout_ns, model_id=model_id,
            )
        else:
            record = self._execute_backend(
                request_id, operation, operands,
                dtype=dtype, timeout_ns=timeout_ns, token=token,
                backend_required=backend_required, deterministic=deterministic,
                model_id=model_id,
                op_count=op_count, exactness=exactness,
            )
        return record

    def _execute_folded(
        self, request_id, operation, names, *, out, token, timeout_ns, model_id
    ) -> Dict[str, Any]:
        # Folded-resident execution consumes the states themselves — the
        # lifted path never decodes them at all.
        states = tuple(self.store.read_state(n) for n in names)
        token.check()
        started_ns = time.perf_counter_ns()

        def _run():
            return folded_execute(operation, states)

        (out_state, fold_receipt), measurement = timed_execute(
            _run,
            operations=out_state_ops(states),
            backend=f"tensor.folded:{operation}",
            model_id=model_id,
            timeout_ns=timeout_ns,
            cancel_token=token,
        )
        out_name = out or f"{request_id}:out"
        receipt = build_folded_receipt(
            request_id=request_id,
            operation=operation,
            states=states,
            output_name=out_name,
            out_state=out_state,
            fold_receipt=fold_receipt,
            elapsed_ns=measurement.elapsed_ns,
            cancelled=token.cancelled,
            started_ns=started_ns,
        )
        with self._lock:
            # Atomic publication: custody of the produced folded state and
            # the receipt appear together — no unfold/re-fold round trip.
            self.store.create_state(out_name, out_state)
            record = {
                "request_id": request_id,
                "operation": operation,
                "path": fold_receipt.path,
                "inputs": list(names),
                "output": out_name,
                "output_hash": out_state.content_hash,
                "decoded_bytes": fold_receipt.decoded_bytes,
                "peak_materialized_bytes": fold_receipt.peak_materialized_bytes,
                "commit_regions": fold_receipt.commit_regions,
                "commit_bytes": fold_receipt.commit_bytes,
                "elapsed_ns": receipt.elapsed_ns,
                "truth_class": TruthClass.MEASURED.value,
                "receipt": receipt.as_dict(),
                "published_ns": receipt.published_ns,
            }
            self._results[request_id] = record
        return dict(record)

    def _execute_backend(
        self, request_id, operation, operands, *, dtype, timeout_ns,
        token, backend_required, deterministic, model_id,
        op_count=None, exactness="exact",
    ) -> Dict[str, Any]:
        # Mixed operands are legal: resident names resolve to arrays here;
        # the folded path only engages when *every* operand is resident.
        resident_names = {
            o for o in operands
            if isinstance(o, str) and o in self.tensor_names()
        }
        decoded_input_bytes = sum(
            logical_bytes(self.store.read_state(n)) for n in resident_names
        )
        resolved = tuple(
            self.store.read(o)
            if isinstance(o, str) and o in resident_names
            else o
            for o in operands
        )
        arrays = [
            np.asarray(o, dtype=_DTYPE_NAMES.get(dtype, np.float64))
            for o in resolved
        ]
        precision = _PRECISION_FOR.get(arrays[0].dtype, Precision.FLOAT64)
        input_shapes = tuple(TensorShape(tuple(int(d) for d in a.shape or (1,))) for a in arrays)
        requested = str(exactness).lower()
        if requested in {"exact", "bit_exact"}:
            exact_mode = ExactnessMode.EXACT
        elif requested in {"lossy", "lossy_approx"}:
            exact_mode = ExactnessMode.LOSSY_APPROX
        else:
            raise TensorValidationError(f"unknown exactness {exactness!r}")
        # Derive the output shape by running the declared op kind's algebra.
        spec = TensorOperationSpec(
            name=operation,
            input_shapes=input_shapes,
            output_shape=self._output_shape(operation, input_shapes, arrays),
            dtype=precision,
            exactness_mode=exact_mode,
            op_count=int(op_count) if op_count is not None else 1,
        )
        request = TensorRequest(
            operation=spec,
            backend_required=backend_required or "numpy-cpu",
            allow_fallback=backend_required is None,
            deterministic=deterministic,
            timeout_ns=timeout_ns,
            # The contract requires lossy requests to opt in explicitly
            # with measured-residual evidence — an opt-in with no measured
            # bound is refused by the contract itself (fail closed).
            residual_bounds=(
                ResidualBounds(opt_in=True, measured_residual=0.0)
                if exact_mode is ExactnessMode.LOSSY_APPROX
                else ResidualBounds()
            ),
        )
        token.check()
        started_ns = time.perf_counter_ns()
        result = _engine_execute(
            request, arrays,
            model=ModelIdentity(model_id=model_id),
            registry=self.registry,
            cancel_token=token,
        )
        receipt = build_backend_receipt(
            request_id=request_id,
            operation=operation,
            arrays=arrays,
            decoded_input_bytes=decoded_input_bytes,
            result=result,
            output_id=f"{request_id}:out",
            elapsed_ns=result.measurement.elapsed_ns,
            started_ns=started_ns,
        )
        with self._lock:
            record = {
                "request_id": request_id,
                "operation": operation,
                "path": "backend",
                "backend": result.measurement.backend,
                "output": result.data.tolist(),
                "output_digest": result.provenance.output_digest,
                "elapsed_ns": result.measurement.elapsed_ns,
                "truth_class": result.truth_class.value,
                "fallback_used": result.measurement.fallback_used,
                "receipt": receipt.as_dict(),
                "published_ns": receipt.published_ns,
            }
            self._results[request_id] = record
        return dict(record)

    @staticmethod
    def _output_shape(operation, input_shapes, arrays) -> TensorShape:
        """Compute the declared output shape for common ops; the engine's
        backend still re-validates it against the computed result."""
        if operation == "matmul":
            return TensorShape((input_shapes[0].dims[0], input_shapes[1].dims[1]))
        if operation == "kron":
            dims = tuple(
                a * b for a, b in zip(input_shapes[0].dims, input_shapes[1].dims)
            )
            return TensorShape(dims)
        if operation == "reduce_sum":
            return TensorShape((1,))
        if operation == "transpose":
            return TensorShape(tuple(reversed(input_shapes[0].dims)))
        return TensorShape(input_shapes[0].dims)


def out_state_ops(states) -> int:
    """Declared op count for folded executions (element count touched)."""
    return int(sum(s.original_size for s in states))


_default_runtime: Optional[TensorRuntime] = None
_default_lock = threading.Lock()


def default_runtime() -> TensorRuntime:
    """Process-wide runtime — the one control-plane callers share."""
    global _default_runtime
    with _default_lock:
        if _default_runtime is None:
            _default_runtime = TensorRuntime()
        return _default_runtime


__all__ = ["TensorRuntime", "default_runtime", "out_state_ops"]
