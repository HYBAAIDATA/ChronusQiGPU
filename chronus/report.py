"""Aggregated GPU report — one JSON truth surface for every vendor.

Observation only: collects observed OpenCL/vendor/hasher/punch/tensor facts
and never crashes. This module never promotes a build and never proves
execution — for release promotion use
``chronus.readiness.production_readiness()``.

Blocking: each section enumerates hardware and may construct OpenCL
contexts/programs (vendor probes up to ~10-15 s each, hasher/punch OpenCL
init + self-checks). Callers that poll frequently must cache at the caller
(see ``control_api._GPU_CACHE_TTL_S``); do not call :func:`report` in a
tight loop. Every section records ``elapsed_ms`` so slowness is visible.
"""

from __future__ import annotations

import time
from typing import Any, Dict

from hyba.dispatch import rank_devices

REPORT_SCHEMA = "chronus-report-v1"

__all__ = ["REPORT_SCHEMA", "report", "report_document", "main"]


def _opencl_section() -> Dict[str, Any]:
    try:
        import pyopencl as cl
    except Exception as exc:
        return {"importable": False, "error": f"{type(exc).__name__}: {exc}"}
    try:
        devices = rank_devices(cl)
    except Exception as exc:
        return {"importable": True, "error": f"{type(exc).__name__}: {exc}"}
    records = [d.as_dict() for d in devices]
    return {
        "importable": True,
        "devices": records,
        "count": len(records),
        "gpu_count": sum(1 for item in records if item.get("is_gpu")),
    }


def _vendor_section() -> Dict[str, Any]:
    from hyba.vendors import probe_summary

    return probe_summary()


def _hasher_section() -> Dict[str, Any]:
    from hyba.hasher import BitcoinHasher

    hasher = BitcoinHasher()
    return {
        "backend": hasher.backend,
        "device": hasher.device,
        "fallback_reason": hasher.fallback_reason,
        "gold_device_run": getattr(hasher, "_gold_device_run", "UNKNOWN"),
    }


def _punch_section() -> Dict[str, Any]:
    from hyba.punch import UnifiedPunchHost

    host = UnifiedPunchHost()
    info: Dict[str, Any] = {
        "use_opencl": bool(getattr(host, "use_opencl", False)),
        "device_info": getattr(host, "device_info", None),
        "gpu_error": getattr(host, "gpu_error", None),
        "kernel_path": str(getattr(host, "kernel_path", "")),
        "last_dispatch_backend": str(getattr(host, "last_dispatch_backend", "none")),
    }
    last_kernel_ms = getattr(host, "last_kernel_ms", None)
    if last_kernel_ms is not None:
        info["last_kernel_ms"] = last_kernel_ms
    try:
        info["backend"] = host.backend
    except Exception as exc:
        info["backend_error"] = f"{type(exc).__name__}: {exc}"
    return info


def _tensor_section() -> Dict[str, Any]:
    import sys

    mod = sys.modules.get("chronus.tensor_compute")
    if mod is None:
        import chronus.tensor_compute as mod

    result = mod.probe().as_dict()
    runtime = getattr(mod, "_RUNTIME", None)
    evidence = getattr(runtime, "last_evidence", None)
    # No tensor is executed merely to make a report look healthy.
    result["last_execution_evidence"] = (
        evidence.as_dict() if evidence is not None else "Unavailable"
    )
    return result


def report() -> Dict[str, Any]:
    """Collect observed OpenCL/vendor/hasher/punch/tensor facts; never crash.

    Observation only — the result never certifies production readiness.
    Blocking: each section may enumerate devices and build OpenCL programs;
    callers that poll must cache (see ``control_api``). Every section gains
    an ``elapsed_ms`` field so latency is auditable. Top-level keys stay
    exactly ``{opencl, vendors, hasher, punch, tensor}`` for backward
    compatibility; use :func:`report_document` for a stamped envelope.
    """
    out: Dict[str, Any] = {}
    for key, fn in (
        ("opencl", _opencl_section),
        ("vendors", _vendor_section),
        ("hasher", _hasher_section),
        ("punch", _punch_section),
        ("tensor", _tensor_section),
    ):
        started_ns = time.perf_counter_ns()
        try:
            section = fn()
            if not isinstance(section, dict):
                section = {"value": section}
        except Exception as exc:
            section = {"error": f"{type(exc).__name__}: {exc}"}
        elapsed_ms = (time.perf_counter_ns() - started_ns) // 1_000_000
        section["elapsed_ms"] = int(elapsed_ms)
        out[key] = section
    return out


def report_document() -> Dict[str, Any]:
    """Stamped envelope around :func:`report` for evidence chains.

    Adds ``schema`` (``REPORT_SCHEMA``) and ``generated_at`` (RFC3339 UTC)
    without changing the five canonical section keys.
    """
    from datetime import datetime, timezone

    doc = report()
    doc["schema"] = REPORT_SCHEMA
    doc["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return doc


def main() -> int:
    """Print the aggregated GPU report as JSON.

    Observation only — exit code is always 0 when the report itself was
    produced, even with no GPU present. For release promotion use
    ``chronus.readiness:main`` (``pythia-gpu-readiness``), never this entry
    point.
    """
    import json

    print(json.dumps(report(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
