"""Aggregated GPU report — one JSON truth surface for every vendor."""

from __future__ import annotations

from typing import Any, Dict

from hyba.dispatch import rank_devices


def _opencl_section() -> Dict[str, Any]:
    try:
        import pyopencl as cl
    except Exception as exc:
        return {"importable": False, "error": f"{type(exc).__name__}: {exc}"}
    try:
        devices = rank_devices(cl)
    except Exception as exc:
        return {"importable": True, "error": f"{type(exc).__name__}: {exc}"}
    return {"importable": True, "devices": [d.as_dict() for d in devices]}


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
    }


def _punch_section() -> Dict[str, Any]:
    from hyba.punch import UnifiedPunchHost

    host = UnifiedPunchHost()
    info: Dict[str, Any] = {
        "use_opencl": bool(getattr(host, "use_opencl", False)),
        "device_info": getattr(host, "device_info", None),
        "gpu_error": getattr(host, "gpu_error", None),
        "kernel_path": str(getattr(host, "kernel_path", "")),
    }
    try:
        info["backend"] = host.backend
    except Exception as exc:
        info["backend_error"] = f"{type(exc).__name__}: {exc}"
    return info


def _tensor_section() -> Dict[str, Any]:
    from chronus import tensor_compute

    result = tensor_compute.probe().as_dict()
    runtime = getattr(tensor_compute, "_RUNTIME", None)
    evidence = getattr(runtime, "last_evidence", None)
    # No tensor is executed merely to make a report look healthy.
    result["last_execution_evidence"] = (
        evidence.as_dict() if evidence is not None else "Unavailable"
    )
    return result


def report() -> Dict[str, Any]:
    """Collect observed OpenCL/vendor/hasher/punch/tensor facts; never crash."""
    out: Dict[str, Any] = {}
    for key, fn in (
        ("opencl", _opencl_section),
        ("vendors", _vendor_section),
        ("hasher", _hasher_section),
        ("punch", _punch_section),
        ("tensor", _tensor_section),
    ):
        try:
            out[key] = fn()
        except Exception as exc:
            out[key] = {"error": f"{type(exc).__name__}: {exc}"}
    return out


def main() -> int:
    """Print the aggregated GPU report as JSON."""
    import json

    print(json.dumps(report(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())