"""HYBA diagnostics — observed facts only, no throughput projections."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict


def _collect(report: Dict[str, Any], name: str, fn: Callable[[], Dict[str, Any]]) -> None:
    try:
        report[name] = fn()
    except Exception as exc:  # diagnostics must not crash
        report[name] = {"error": f"{type(exc).__name__}: {exc}"}


def _kernel_path() -> Dict[str, Any]:
    from hyba.punch import UnifiedPunchHost

    path = Path(UnifiedPunchHost().kernel_path)
    root = Path(__file__).resolve().parent.parent
    canonical = root / "kernels"
    mirror = root / "igpu" / "kernels"
    dupes: Dict[str, Any] = {}
    if mirror.is_dir():
        # Byte-identity assertion: a mirrored kernel that diverged silently
        # is worse than a missing mirror — report it, never hide it.
        import hashlib

        for k in sorted(mirror.glob("*.cl")):
            canon = canonical / k.name
            if not canon.is_file():
                dupes[k.name] = "no_canonical"
            else:
                same = hashlib.md5(k.read_bytes()).digest() == hashlib.md5(
                    canon.read_bytes()
                ).digest()
                dupes[k.name] = "identical" if same else "DIVERGED"
    return {
        "resolved": str(path),
        "exists": path.is_file(),
        "canonical_dir": str(canonical),
        "mirror_dir": str(mirror),
        "mirror_dir_exists": mirror.is_dir(),
        "mirror_kernels": sorted(x.name for x in mirror.glob("*.cl"))
        if mirror.is_dir()
        else [],
        "mirror_byte_check": dupes,
    }


def _opencl() -> Dict[str, Any]:
    try:
        import pyopencl as cl
    except Exception as exc:
        return {"importable": False, "error": f"{type(exc).__name__}: {exc}"}
    out: Dict[str, Any] = {"importable": True, "platforms": []}
    try:
        platforms = cl.get_platforms()
    except Exception as exc:
        out["platform_error"] = f"{type(exc).__name__}: {exc}"
        return out
    for platform in platforms:
        devices = []
        for dev in platform.get_devices():
            dtype = int(dev.type)
            kinds = [
                name.lower()
                for name in ("DEFAULT", "CPU", "GPU", "ACCELERATOR", "CUSTOM")
                if getattr(cl.device_type, name, 0) & dtype
            ]
            devices.append(
                {
                    "name": dev.name,
                    "kinds": kinds,
                    "vendor": getattr(dev, "vendor", None),
                    "compute_units": getattr(dev, "max_compute_units", None),
                }
            )
        out["platforms"].append({"platform": platform.name, "devices": devices})
    return out


def _hyba_alias() -> Dict[str, Any]:
    from hyba.device import aliases

    report = _opencl()
    if not report.get("importable"):
        return {"found": False, "reason": "opencl_unavailable"}
    if not report.get("platforms"):
        return {
            "found": False,
            "reason": "no_devices",
            "platform_error": report.get("platform_error"),
        }
    hits = []
    for plat in report["platforms"]:
        for dev in plat["devices"]:
            for alias in aliases():
                if alias.lower() in str(dev["name"]).lower():
                    hits.append(
                        {
                            "platform": plat["platform"],
                            "device": dev["name"],
                            "alias": alias,
                        }
                    )
    return {"found": bool(hits), "matches": hits}


def _punch_host() -> Dict[str, Any]:
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


def _hasher() -> Dict[str, Any]:
    from hyba.hasher import BitcoinHasher

    hasher = BitcoinHasher()
    return {
        "backend": hasher.backend,
        "device": hasher.device,
        "fallback_reason": hasher.fallback_reason,
        "launch_config": getattr(hasher, "launch_config", None),
    }


def _super_gpu() -> Dict[str, Any]:
    """The composed substrate view: inventory + capability map + routes."""
    from hyba.inventory import ClusterInventory
    from hyba.virtual_gpu import SuperGPU

    inventory = ClusterInventory.collect()
    composed = SuperGPU.compose(inventory)
    return {
        "composed": composed.as_dict(),
        "routes": {
            op: composed.route(op).as_dict()
            for op in (
                "sha256d_grind",
                "m32_grind",
                "unified_punch",
                "unified_resident_state",
                "lucas_pisot_scale",
            )
        },
    }


def diagnose() -> Dict[str, Any]:
    """Collect observed-fact sections (kernel, OpenCL, alias, host, hasher, super-gpu)."""
    report: Dict[str, Any] = {}
    _collect(report, "kernel_path", _kernel_path)
    _collect(report, "opencl", _opencl)
    _collect(report, "hyba_alias", _hyba_alias)
    _collect(report, "punch_host", _punch_host)
    _collect(report, "hasher", _hasher)
    _collect(report, "super_gpu", _super_gpu)
    return report


def main() -> int:
    import json

    print(json.dumps(diagnose(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
