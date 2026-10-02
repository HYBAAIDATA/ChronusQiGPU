#!/usr/bin/env python3
"""Fail-explicit PYTHIA release preflight.

This script performs no mining, network connection, share submission, or secret
printing.  It separates application, device, and live-pool prerequisites and
reports PASS/BLOCKED/FAIL as machine-readable JSON.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

REQUIRED_MODULES = (
    "chronus.mla1517.mining.coordinator",
    "control_api",
    "system_fabric",
)
LIVE_REQUIRED_ENV = (
    "MLA1517_STRATUM_USER",
    "MLA1517_STRATUM_PASSWORD",
)
LIVE_GATES = (
    "HYBA_ENABLE_LIVE_SHARE_SUBMIT",
    "HYBA_LIVE_SHARE_APPROVAL_ID",
    "HYBA_AUTONOMOUS_EXTERNAL_ACTIONS",
)
TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Check:
    name: str
    state: str
    detail: str


def _truthy(value: str | None) -> bool:
    return bool(value and value.strip().lower() in TRUE_VALUES)


def _application_checks(
    *,
    importer: Callable[[str], object],
    runtime_config: Path,
    modules: Sequence[str],
) -> list[Check]:
    checks: list[Check] = []
    checks.append(
        Check(
            "python_version",
            "PASS" if sys.version_info >= (3, 10) else "FAIL",
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        )
    )
    for module in modules:
        try:
            importer(module)
        except Exception as exc:  # exact import defect is evidence
            checks.append(Check(f"import:{module}", "FAIL", f"{type(exc).__name__}: {exc}"))
        else:
            checks.append(Check(f"import:{module}", "PASS", "importable"))
    parent = runtime_config.expanduser().resolve().parent
    if not parent.exists():
        checks.append(Check("runtime_config_parent", "BLOCKED", f"missing directory: {parent}"))
    elif not os.access(parent, os.W_OK):
        checks.append(Check("runtime_config_parent", "BLOCKED", f"not writable: {parent}"))
    else:
        checks.append(Check("runtime_config_parent", "PASS", f"writable: {parent}"))
    return checks


def _default_opencl_probe() -> tuple[int, str]:
    try:
        import pyopencl as cl  # type: ignore
    except Exception as exc:
        return 0, f"pyopencl unavailable: {type(exc).__name__}: {exc}"
    try:
        devices = [device for platform in cl.get_platforms() for device in platform.get_devices()]
    except Exception as exc:
        return 0, f"OpenCL enumeration failed: {type(exc).__name__}: {exc}"
    return len(devices), f"{len(devices)} OpenCL device(s)"


def _device_checks(
    env: Mapping[str, str], opencl_probe: Callable[[], tuple[int, str]]
) -> list[Check]:
    backend = env.get("MLA1517_GPU_BACKEND", "").strip().lower()
    if backend != "opencl":
        return [
            Check(
                "device_backend",
                "BLOCKED",
                "set MLA1517_GPU_BACKEND=opencl for the production device gate",
            )
        ]
    count, detail = opencl_probe()
    return [
        Check("device_backend", "PASS", "opencl"),
        Check("opencl_devices", "PASS" if count > 0 else "BLOCKED", detail),
    ]


def _live_checks(env: Mapping[str, str]) -> list[Check]:
    checks: list[Check] = []
    for name in LIVE_REQUIRED_ENV:
        checks.append(Check(f"env:{name}", "PASS" if env.get(name) else "BLOCKED", "configured" if env.get(name) else "missing"))
    endpoint = env.get("MLA1517_BRAIINS_ENDPOINT") or env.get("MLA1517_STRATUM_ENDPOINT")
    checks.append(Check("pool_endpoint", "PASS" if endpoint else "BLOCKED", "configured" if endpoint else "missing"))
    for name in LIVE_GATES:
        present = bool(env.get(name)) if name.endswith("APPROVAL_ID") else _truthy(env.get(name))
        checks.append(Check(f"gate:{name}", "PASS" if present else "BLOCKED", "armed" if present else "not armed"))
    return checks


def evaluate(
    profile: str,
    *,
    env: Mapping[str, str] | None = None,
    importer: Callable[[str], object] = importlib.import_module,
    opencl_probe: Callable[[], tuple[int, str]] = _default_opencl_probe,
    modules: Sequence[str] = REQUIRED_MODULES,
) -> dict[str, object]:
    if profile not in {"application", "device", "live"}:
        raise ValueError(f"unknown profile: {profile}")
    env = dict(os.environ if env is None else env)
    runtime_config = Path(env.get("PYTHIA_RUNTIME_CONFIG", "data/runtime_config.json"))
    checks = _application_checks(importer=importer, runtime_config=runtime_config, modules=modules)
    if profile in {"device", "live"}:
        checks.extend(_device_checks(env, opencl_probe))
    if profile == "live":
        checks.extend(_live_checks(env))
    states = {check.state for check in checks}
    overall = "FAIL" if "FAIL" in states else "BLOCKED" if "BLOCKED" in states else "PASS"
    return {
        "schema": "pythia.production_preflight/1",
        "profile": profile,
        "state": overall,
        "side_effects": "none",
        "checks": [asdict(check) for check in checks],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("application", "device", "live"), default="application")
    parser.add_argument("--strict", action="store_true", help="exit non-zero on BLOCKED as well as FAIL")
    parser.add_argument("--output", type=Path, help="optional JSON evidence file")
    args = parser.parse_args(argv)
    report = evaluate(args.profile)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    if report["state"] == "FAIL":
        return 1
    if args.strict and report["state"] == "BLOCKED":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
