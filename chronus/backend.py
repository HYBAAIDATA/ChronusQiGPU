"""Backend-agnostic execution contract for the Chronus substrate runtime.

Declared backends: cpu_reference, opencl_igpu, mla1517_mmio, remote.
The contract itself never touches a backend library (no pyopencl, libmla1517,
azure SDK). Backends live only in chronus/backends/* and kernels/*.cl; this
module imports pure algebra (lucas.core, lucas.pisot) and the euclid surface
only. Real probes are delegated to the backends.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from enum import Enum

from lucas.core import lucas as _lucas
from lucas.pisot import require_lucas_execution_scale as _require_lucas_scale  # noqa: F401

__all__ = ["Backend", "Route", "probe", "execute", "BackendUnavailable", "BACKEND_ORDER", "STRICT_OPS", "SOLVER_OPS"]

class Backend(Enum):
    CPU_REF = "cpu_reference"
    OPENCL_IGPU = "opencl"
    MLA1517 = "mla1517"
    REMOTE = "remote"

@dataclass(frozen=True)
class Route:
    requested: str
    executed: str
    fallback_reason: str = ""

BACKEND_ORDER = (Backend.OPENCL_IGPU, Backend.MLA1517, Backend.CPU_REF)
STRICT_OPS = {"miner", "submit", "strict_gate", "hash_pipeline_accept", "pool_commit"}
SOLVER_OPS = {"solver", "amplitude_amplification", "grover", "shor", "period_finding", "bitcoin_sha256d", "sha256d", "hash"}

class BackendUnavailable(RuntimeError):
    """Requested backend missing and fail-closed required."""

_MODULE_MAP = {
    Backend.CPU_REF: "cpu_reference",
    Backend.OPENCL_IGPU: "opencl_igpu",
    Backend.MLA1517: "mla1517_mmio",
    Backend.REMOTE: "remote",
}

def _backend_module(backend: Backend):
    return importlib.import_module(f"chronus.backends.{_MODULE_MAP[backend]}")

def probe() -> dict:
    results = {}
    for backend in Backend:
        try:
            fn = getattr(_backend_module(backend), "probe", None)
            if fn is None:
                results[backend.value] = {"available": False, "reason": "no probe() surface"}
                continue
            results[backend.value] = fn()
        except Exception as exc:
            results[backend.value] = {"available": False, "reason": f"{type(exc).__name__}: {exc}"}
    return results

def _resolve(requested: str) -> Backend:
    requested = (requested or "auto").strip().lower()
    if requested in {"auto", "Auto"}:
        for backend in BACKEND_ORDER:
            if probe().get(backend.value, {}).get("available"):
                return backend
        return Backend.CPU_REF
    if requested in {"cpu", "cpu_reference", "cpu-reference", "reference"}:
        return Backend.CPU_REF
    try:
        return Backend(requested)
    except ValueError:
        for b in Backend:
            if requested in (b.value, b.name.lower(), _MODULE_MAP[b], _MODULE_MAP[b].replace("_mmio", ""), _MODULE_MAP[b].replace("_igpu", "")):
                return b
        raise BackendUnavailable(f"unknown PYTHIA_EXECUTION_DEVICE {requested!r}; expected " + ", ".join(b.value for b in Backend)) from None

def _is_strict_op(op: str) -> bool:
    return op in STRICT_OPS or str(op).startswith(tuple(STRICT_OPS))

def _is_solver_op(op: str) -> bool:
    return op in SOLVER_OPS or str(op).startswith(tuple(SOLVER_OPS))

def execute(op: str, payload, requested: str = "auto"):
    """Run one operation on the backend chosen by requested.

    Returns (result, Route). Route.executed is always the backend that
    actually produced the result, so a CPU fallback is never mislabelled as
    opencl or mla1517.

    Policy:
      * strict HW ops (miner, submit, strict gate) are fail-closed: a missing
        declared backend raises BackendUnavailable with no fallback.
      * supervised solver routes fall back to cpu_reference with a recorded
        Route.fallback_reason when their lane is unavailable.
      * auto chooses the first probe-verified backend in BACKEND_ORDER.
    """
    op = (op or "").strip().lower()
    requested = (requested or "auto").strip().lower()
    probes = probe()

    if requested == "auto":
        chosen = next((b for b in BACKEND_ORDER if probes.get(b.value, {}).get("available")), Backend.CPU_REF)
        can_run = True
    else:
        chosen = _resolve(requested)
        can_run = bool(probes.get(chosen.value, {}).get("available"))

    executed = chosen.value
    fallback_reason = ""

    if not can_run:
        if _is_strict_op(op):
            raise BackendUnavailable(f"strict op {op!r}: fallback closed for {chosen.value}; probes={probes!r}")
        if _is_solver_op(op):
            target = Backend.CPU_REF
            fallback_reason = f"supervised {op!r} fell back to cpu_reference: {chosen.value} unavailable ({probes.get(chosen.value, {}).get('reason', 'probe error')})"
            chosen, executed, can_run = target, target.value, True
        else:
            raise BackendUnavailable(f"op {op!r}: lane {chosen.value} unavailable ({probes.get(chosen.value, {}).get('reason', 'probe error')})")

    result = _backend_module(chosen).execute(op, payload)
    return result, Route(requested=requested, executed=executed, fallback_reason=fallback_reason)
