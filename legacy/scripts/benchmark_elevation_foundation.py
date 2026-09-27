"""Elevation-foundation benchmark harness.

Measures the four areas touched by the elevation-foundation work:

1. ``hashing``    - consensus SHA-256d through the real mining contracts:
                    the workflow's inline ``hashlib`` check, the
                    ``BitcoinHasher`` CPU backend, and the ``BitcoinHasher``
                    ``opencl:gpu`` backend.
2. ``fold``       - the T_phi folded-state engine (``turing_core``) and the
                    ``ExactFoldedStateEngine`` fold-domain query path.
3. ``provenance`` - the hash-chained TOE audit ledger.
4. ``lifecycle``  - the six-phase agentic mining workflow.

Honesty contract for every value emitted here:

* ``truth_class: "measured"`` - read from a live timer or counter in this
  process during this invocation.
* ``truth_class: "derived"`` - arithmetic over measured values only.
* ``truth_class: "not_computable"`` - the metric was requested but its
  inputs are not measurable on this host. It is reported as ``null`` with
  the missing inputs named. It is never substituted with an estimate.
* Every suite reports every individual run.
* Local hashing only. No socket, no pool, no live submission.

Reproduce (one artifact per suite invocation):

    python -m scripts.benchmark_elevation_foundation --suites hashing --runs 3
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

HARNESS_VERSION = "1.0.0"

TRUTH_MEASURED = "measured"
TRUTH_DERIVED = "derived"
TRUTH_NOT_COMPUTABLE = "not_computable"

# Bitcoin genesis block header: fixed public vector, 80 bytes.
GENESIS_HEADER = bytes.fromhex(
    "01000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a"
    "29ab5f49"
    "ffff001d"
    "1dac2b7c"
)
GENESIS_NONCE = 0x7C2BAC1D
GENESIS_DIGEST_LE_HEX = (
    "6fe28c0ab6f1b372c1a6a246ae63f74f931e8365e15a089c68d6190000000000"
)
GENESIS_DISPLAY_BE_HEX = (
    "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
)
GENESIS_NBITS = 0x1D00FFFF


def _psutil():
    """Return psutil or None; the harness degrades honestly without it."""
    try:
        import psutil

        return psutil
    except Exception:
        return None


def _run_capture(cmd: List[str]) -> Optional[str]:
    """Stripped stdout of ``cmd``, or None when the tool is unavailable."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    text = proc.stdout.strip()
    return text or None


def _probe_opencl() -> Dict[str, Any]:
    """Enumerate the OpenCL devices actually present on this host."""
    info: Dict[str, Any] = {
        "pyopencl": False,
        "pyopencl_version": None,
        "devices": [],
        "error": None,
    }
    try:
        import pyopencl as cl
    except Exception as exc:
        info["error"] = f"pyopencl import failed: {exc}"
        return info
    info["pyopencl"] = True
    info["pyopencl_version"] = getattr(cl, "VERSION_TEXT", None)
    try:
        for plat in cl.get_platforms():
            for dev in plat.get_devices():
                info["devices"].append(
                    {
                        "name": dev.name.strip(),
                        "type": cl.device_type.to_string(dev.type),
                        "global_mem_mib": round(dev.global_mem_size / (1024 * 1024), 1),
                        "max_compute_units": int(dev.max_compute_units),
                        "driver_version": dev.driver_version.strip(),
                    }
                )
    except Exception as exc:
        info["error"] = f"OpenCL enumeration failed: {exc}"
    return info


def capture_environment() -> Dict[str, Any]:
    """Everything needed to reproduce this invocation's numbers."""
    psutil = _psutil()
    env: Dict[str, Any] = {
        "harness_version": HARNESS_VERSION,
        "os": platform.platform(),
        "machine": platform.machine(),
        "cpu": platform.processor(),
        "python": sys.version,
        "python_executable": sys.executable,
        "argv": list(sys.argv),
        "command": "python -m scripts.benchmark_elevation_foundation " + " ".join(sys.argv[1:]),
        "cwd": os.getcwd(),
        "git_head": _run_capture(["git", "rev-parse", "HEAD"]),
        "git_branch": _run_capture(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "git_worktree_dirty": bool(_run_capture(["git", "status", "--porcelain"])),
        "rustc": _run_capture(["rustc", "--version"]),
        "cargo": _run_capture(["cargo", "--version"]),
        "opencl": _probe_opencl(),
        "truth_class": TRUTH_MEASURED,
    }
    if psutil is not None:
        env["ram_gb"] = round(psutil.virtual_memory().total / (1024**3), 2)
        env["cpu_count_logical"] = psutil.cpu_count()
    else:
        env["ram_gb"] = None
        env["cpu_count_logical"] = os.cpu_count()
    return env


def probe_power_measurement() -> Dict[str, Any]:
    """Report whether watts are measurable here. Never guesses a number."""
    result: Dict[str, Any] = {
        "power_watts": None,
        "measurable": False,
        "method": None,
        "reason": None,
        "truth_class": TRUTH_NOT_COMPUTABLE,
    }
    psutil = _psutil()
    if psutil is not None and hasattr(psutil, "sensors_battery"):
        try:
            battery = psutil.sensors_battery()
        except Exception as exc:
            battery = None
            result["reason"] = f"battery probe failed: {exc}"
        if battery is not None:
            result["battery_percent"] = battery.percent
            result["power_plugged"] = battery.power_plugged
            result["method"] = "psutil.sensors_battery (percent only, not watts)"
    if Path("/sys/class/powercap").is_dir():
        result["intel_rapl_powercap"] = True
    result["reason"] = result["reason"] or (
        "no watt-resolving sensor on this host: Windows 10 exposes no Intel RAPL "
        "powercap, and no per-device power API is available for the Intel UHD 620"
    )
    return result


def compute_cuop(
    ops_per_second: Optional[float],
    power_watts: Optional[float],
    usd_per_kwh: Optional[float],
    capex_usd_per_hour: Optional[float],
) -> Dict[str, Any]:
    """Completed Useful Operations per Watt per Dollar - or an honest null.

    ``CUOP = ops_per_second / (power_watts * usd_per_hour)`` where
    ``usd_per_hour = (power_watts / 1000) * usd_per_kwh + capex_usd_per_hour``.

    Every input must be measured or explicitly supplied. Missing inputs are
    named; none is ever estimated.
    """
    missing: List[str] = []
    if ops_per_second is None:
        missing.append("ops_per_second")
    if power_watts is None:
        missing.append("power_watts")
    if usd_per_kwh is None:
        missing.append("usd_per_kwh")
    if capex_usd_per_hour is None:
        missing.append("capex_usd_per_hour")
    out: Dict[str, Any] = {
        "cuop": None,
        "formula": "ops_per_second / (power_watts * usd_per_hour)",
        "missing_inputs": missing,
    }
    if missing:
        out["truth_class"] = TRUTH_NOT_COMPUTABLE
        return out
    usd_per_hour = (power_watts / 1000.0) * usd_per_kwh + capex_usd_per_hour
    out["usd_per_hour"] = usd_per_hour
    if usd_per_hour <= 0:
        out["truth_class"] = TRUTH_NOT_COMPUTABLE
        out["missing_inputs"] = ["usd_per_hour > 0"]
        return out
    out["cuop"] = ops_per_second / (power_watts * usd_per_hour)
    out["truth_class"] = TRUTH_DERIVED
    return out


def _stats(runs: List[float]) -> Dict[str, Any]:
    """Median/min/max over every run. No run is discarded."""
    return {
        "runs": [round(r, 6) for r in runs],
        "n_runs": len(runs),
        "median": round(statistics.median(runs), 6),
        "min": round(min(runs), 6),
        "max": round(max(runs), 6),
        "truth_class": TRUTH_MEASURED,
    }
