"""Hermes acceleration plane — migrated into HYBA Substrate.

All scheduling / backend selection / CUDA source status lives here.
Does not invent GPU speedups without measurement.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def schedule(op: str, n_elements: int, prefer: Optional[str] = None) -> Dict[str, Any]:
    """Return a Hermes schedule card for an op."""
    from pulvini.folding_engine.backends.router import hermes_schedule

    return hermes_schedule(op, n_elements, prefer=prefer) if prefer else hermes_schedule(op, n_elements)


def batch_plan(ops: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    from pulvini.folding_engine.backends.router import hermes_batch_plan

    return hermes_batch_plan(ops)


def probe() -> Dict[str, Any]:
    from pulvini.folding_engine.backend_router import probe_backends

    return probe_backends()


def cuda_status() -> Dict[str, Any]:
    from pulvini.folding_engine.kernels import compile_status, list_cuda_sources

    return {"sources": list_cuda_sources(), "compile": compile_status()}


def claims_authorized() -> bool:
    """True only if a real CUDA path is available (never fabricate)."""
    try:
        from pulvini.folding_engine.next_push.cuda_wallclock_runner import _detect_gpu

        g = _detect_gpu()
        return bool(g.get("cuda_available"))
    except Exception:
        return False


def describe() -> Dict[str, Any]:
    return {
        "plane": "Hermes",
        "platform": "HYBA Substrate",
        "role": "acceleration_and_schedule",
        "claims_authorized": claims_authorized(),
        "backends": probe(),
        "cuda": cuda_status(),
    }
