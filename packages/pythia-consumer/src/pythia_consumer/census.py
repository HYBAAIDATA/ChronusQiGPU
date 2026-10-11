"""Local node census — detected facts only.

Reports the platform, chip, GPU/backend reachability, optional dependency
availability, and (optionally) control-API reachability. Unavailable
subsystems are reported unavailable; nothing is stubbed.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import platform
import re
import subprocess
import urllib.request
from typing import Any, Dict, Optional

from . import __version__

_OPTIONAL_DEPS = ("numpy", "mlx.core", "coremltools", "pyopencl")
_OPENCL_FRAMEWORK = "/System/Library/Frameworks/OpenCL.framework"

# Mac hardware facts for the consumer device offers. Parsed from
# system_profiler output — serial number / UUID are never collected.
_MAC_HW_RE = re.compile(
    r"^\s*(Model Name|Model Identifier|Chip|Memory):\s*(.+?)\s*$")
_MAC_FAMILIES = {
    "macbook": "macbook", "macbook pro": "macbook", "macbook air": "macbook",
    "imac": "imac", "mac studio": "mac-studio", "mac mini": "mac-mini",
    "mac pro": "mac-pro",
}
# Unified-memory threshold (GiB) for the large-memory offer tier — Mac
# Studio-class configurations whose shared memory holds exact-state widths
# discrete GPUs cannot. Matches POSITIONING.md surfaces table.
_LARGE_MEMORY_GIB = 96

# Sibling HYBA distributions the consumer surface can leverage. Presence is
# detected via installed distribution metadata plus module importability —
# reported as facts, never stubbed.
_PRODUCTS = (
    ("hyba-chronos-one-igpu", ("chronos_one_igpu",), "iGPU compute fabric"),
    ("hyba-chronus-igpu", ("chronus", "lucas"), "CHRONUS execution"),
    ("hyba-theseus-storage", ("aethel",), "custody/storage"),
    ("hyba-ovid-data-organisation", ("hyba_db",), "data organisation"),
    ("hyba-kellogg-tensor", ("kellogg",), "tensor substrate"),
    ("hyba-turing-vqc", ("turing_universal_quantum_computer",), "exact VQC"),
    ("hyba-toe-intelligence", ("toe",), "intelligence"),
    ("hyba-euclid-intelligence", ("euclid", "hyba_substrate"), "intelligence engine"),
    ("hyba-salamander-self-healing", ("salamander", "al_haras"), "self-healing + security"),
    ("hyba-pythia-mining-runtime", ("mining_runtime", "control_api"), "mining control plane"),
)


def _dep_available(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def _apple_chip() -> Optional[str]:
    if platform.system() != "Darwin":
        return None
    try:
        out = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        return out or None
    except Exception:
        return None


def _metal_present() -> bool:
    """Probe Metal via system_profiler; bounded timeout, honest negative."""
    if platform.system() != "Darwin":
        return False
    try:
        out = subprocess.run(
            ["system_profiler", "SPDisplaysDataType"],
            capture_output=True, text=True, timeout=10,
        ).stdout
        return "Metal" in out
    except Exception:
        return False


def _sysctl_int(key: str) -> Optional[int]:
    try:
        out = subprocess.run(
            ["sysctl", "-n", key], capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        return int(out) if out else None
    except Exception:
        return None


def _mac_hardware() -> Dict[str, str]:
    """Model/chip facts from system_profiler. Never returns serial or UUID."""
    if platform.system() != "Darwin":
        return {}
    try:
        out = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            capture_output=True, text=True, timeout=10,
        ).stdout
    except Exception:
        return {}
    fields: Dict[str, str] = {}
    for line in out.splitlines():
        m = _MAC_HW_RE.match(line)
        if m:
            fields[m.group(1)] = m.group(2)
    return fields


def offer_tier(memory_gib: Optional[float]) -> Optional[str]:
    """Memory-tier mapping for the consumer offers.

    Apple Silicon unified memory is shared between CPU and GPU — large
    configurations hold exact-state widths discrete GPUs cannot. Below 96 GiB
    is the standard PYTHIA Node tier (MacBook, iMac, Mac mini); at or above
    96 GiB is the large-memory tier (Mac Studio class).
    """
    if memory_gib is None:
        return None
    return ("pythia-node-large-memory" if memory_gib >= _LARGE_MEMORY_GIB
            else "pythia-node")


def device_block() -> Dict[str, Any]:
    """Detected device facts for the consumer offers. Detected facts only —
    model strings come straight from system_profiler; no marketing claims."""
    if platform.system() != "Darwin":
        return {"family": "non-apple", "offer_tier": None, "unified_memory": False}
    hw = _mac_hardware()
    mem_bytes = _sysctl_int("hw.memsize")
    memory_gib = round(mem_bytes / (1 << 30), 1) if mem_bytes else None
    model_name = hw.get("Model Name")
    unified = platform.machine().lower() in ("arm64", "aarch64")
    return {
        "family": _MAC_FAMILIES.get((model_name or "").lower(), "mac" if model_name else "unknown"),
        "model_name": model_name,
        "model_id": hw.get("Model Identifier"),
        "chip": hw.get("Chip") or _apple_chip(),
        "memory_gib": memory_gib,
        "unified_memory": unified,
        "offer_tier": offer_tier(memory_gib) if unified else None,
    }


def _opencl_present() -> bool:
    import os
    if platform.system() == "Darwin":
        return os.path.isdir(_OPENCL_FRAMEWORK)
    return _dep_available("pyopencl")


def _bundled_namespaces() -> set:
    """Namespaces vendored into this wheel at build time (if any)."""
    try:
        from importlib.resources import files
        data = json.loads(files("pythia_consumer").joinpath("bundled_products.json").read_text())
        return {p["namespace"] for p in data.get("products", [])}
    except Exception:
        return set()


def _product_entry(distribution: str, modules: tuple, role: str, bundled: set) -> Dict[str, Any]:
    try:
        version: Optional[str] = importlib.metadata.version(distribution)
        installed = True
    except importlib.metadata.PackageNotFoundError:
        version, installed = None, False
    importable = {m: _dep_available(m) for m in modules}
    is_bundled = any(m in bundled for m in modules)
    if (installed or is_bundled) and all(importable.values()):
        state = "available"
    elif installed or any(importable.values()):
        state = "partial"
    else:
        state = "absent"
    return {
        "distribution": distribution,
        "role": role,
        "state": state,
        "origin": "bundled" if is_bundled else ("installed" if installed else "absent"),
        "installed_version": version or (f"bundled:{__version__}" if is_bundled else None),
        "importable": importable,
    }


def available_products() -> list:
    bundled = _bundled_namespaces()
    return [_product_entry(d, m, r, bundled) for d, m, r in _PRODUCTS]


def probe_control_api(url: str, timeout: float = 3.0) -> Dict[str, Any]:
    """Reachability probe against a PYTHIA control API base URL."""
    target = url.rstrip("/")
    try:
        with urllib.request.urlopen(target + "/api/status", timeout=timeout) as resp:
            body = resp.read(65536)
        try:
            payload = json.loads(body)
        except ValueError:
            payload = {"_raw_bytes": len(body)}
        return {"url": target, "reachable": True, "status_endpoint": "ok", "payload": payload}
    except Exception as exc:
        return {"url": target, "reachable": False, "error": f"{type(exc).__name__}: {exc}"}


def node_status(api_url: Optional[str] = None) -> Dict[str, Any]:
    system, machine = platform.system(), platform.machine().lower()
    apple_silicon = system == "Darwin" and machine in ("arm64", "aarch64")
    deps = {d.replace(".", "_"): _dep_available(d) for d in _OPTIONAL_DEPS}
    status: Dict[str, Any] = {
        "schema": "pythia.consumer.census/1",
        "platform": {
            "system": system,
            "machine": machine,
            "python": platform.python_version(),
            "apple_silicon": apple_silicon,
            "chip": _apple_chip(),
        },
        "device": device_block(),
        "backends": {
            "metal": apple_silicon and _metal_present(),
            "mlx": apple_silicon and deps["mlx_core"],
            "opencl": _opencl_present(),
            "cpu": True,
        },
        "optional_dependencies": deps,
        "compute_routes": [],
        "products": available_products(),
        "mining_performed": False,
    }
    routes = status["compute_routes"]
    if status["backends"]["mlx"]:
        routes.append({"route": "mlx-metal", "kind": "tensor", "note": "Apple unified-memory GPU"})
    if status["backends"]["opencl"]:
        routes.append({"route": "opencl", "kind": "kernel", "note": "deprecated on macOS but functional"})
    routes.append({"route": "cpu", "kind": "exact-integer", "note": "always available"})
    if api_url:
        status["control_api"] = probe_control_api(api_url)
    return status
