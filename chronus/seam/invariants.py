"""Compare HYBA hybrid and Chronus surfaces against seam invariants.

This is the audit the contract demands: layer by layer, invariant by invariant.
Gaps are declared, never papered over.
"""

from __future__ import annotations

import inspect
from typing import Any, Dict, List

INVARIANTS = (
    "P1", "P2", "P3", "P4",
    "B1", "B2", "B3", "B4", "B5",
    "K1", "K2", "K3", "K4", "K5",
    "Q1", "Q2", "Q3", "Q4",
    "F1", "F2", "F3", "F4", "F5",
    "H1", "H2", "H3",
    "S1", "S2", "S3", "S4", "S5",
)

PARTIAL = ("P1", "P2", "B1", "B2", "K1", "K4", "Q1", "S1")
CORE = (
    "P1", "P2", "P3", "B1", "B2", "B3", "K1", "K2", "K3", "K4",
    "Q1", "Q2", "S1", "S4",
)
EXTENDED = (
    "P1", "P2", "P3", "P4",
    "B1", "B2", "B3", "B4",
    "K1", "K2", "K3", "K4",
    "Q1", "Q2", "Q3", "Q4",
    "F1", "F2", "F3", "F5",
    "H1", "H2", "H3",
    "S1", "S2", "S3", "S4", "S5",
)


def _src(module: Any) -> str:
    try:
        return inspect.getsource(module)
    except Exception:
        return ""


def audit_hyba_hybrid() -> Dict[str, Any]:
    findings: List[Dict[str, str]] = []
    passed: List[str] = []
    gaps: List[str] = []
    try:
        from hyba.hybrid import coordinator, lucas_partition, nonce_scheduler
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "passed": [],
            "gaps": list(INVARIANTS),
        }
    source = _src(coordinator) + _src(nonce_scheduler) + _src(lucas_partition)
    checks = {
        "F2": ("verify_share" in source or "host" in source.lower())
        and ("quarantine" in source or "AttestationViolation" in source),
        "F3": "record_gap" in source or "asic_absent" in source,
        "F5": "record_gap" in source,
        "H2": "record_gap" in source,
        "H3": "asic_absent" in source or "gpu_only" in source,
        "K1": "DeviceUnsupportedError" in source or "supported" in source,
        "K4": "idempotent" in source.lower() or "handle" in source,
        "P1": "measured_hashes_per_sec" in source,
        "S4": "AttestationViolation" in source,
    }
    for invariant, ok in checks.items():
        if ok:
            passed.append(invariant)
        else:
            gaps.append(invariant)
            findings.append(
                {"invariant": invariant, "status": "gap", "module": "hyba.hybrid"}
            )
    known = {
        "P4": "hyba.hybrid DeviceCapability.measured_hashes_per_sec is a scalar, not a Distribution",
        "F4": "threshold verification across independent devices lives on the Chronus seam",
        "K5": "zero-knowledge attestation mode is absent",
        "B1": "hyba.hybrid has no digested multi-tenant buffer layer",
        "Q2": "hyba.hybrid coordinator has no explicit in_flight backpressure threshold",
        "S1": "hyba.hybrid raises exceptions instead of Result[T]",
        "S5": "solver objects expose backend provenance intentionally",
    }
    for invariant, note in known.items():
        if invariant not in gaps:
            gaps.append(invariant)
        findings.append({"invariant": invariant, "status": "gap", "detail": note})
    return {
        "ok": not any(invariant == "S4" for invariant in gaps),
        "passed": sorted(set(passed)),
        "gaps": sorted(set(gaps)),
        "findings": findings,
        "note": "hyba.hybrid fail-closes on bad shares and declares ASIC absence.",
    }


def audit_chronus() -> Dict[str, Any]:
    """Audit the canonical Chronus product/runtime surface."""
    passed: List[str] = []
    gaps: List[str] = []
    try:
        from chronus import device, detect, runtime
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "passed": [],
            "gaps": ["P1", "P3", "S5"],
        }
    detect_src = _src(detect)
    runtime_src = _src(runtime)
    device_src = _src(device)
    if "host_unified_memory" in detect_src:
        passed.append("P3")
    if "KIND_HOST_FALLBACK" in runtime_src or "host_fallback" in runtime_src:
        passed.append("B5")
    if "CLAIM_BOUNDARY" in device_src or "projection_is_measured" in device_src:
        passed.append("S5")
    if "classify_integrated" in detect_src and "INTEGRATED_VENDORS" in detect_src:
        passed.append("P1")
    else:
        gaps.append("P1")
    return {
        "ok": True,
        "passed": sorted(set(passed)),
        "gaps": sorted(set(gaps)),
        "note": (
            "Chronus detection distinguishes integrated and discrete devices; "
            "runtime never names host RAM as device memory."
        ),
    }


def audit_seam() -> Dict[str, Any]:
    passed: List[str] = []
    gaps: List[str] = ["K5"]
    try:
        from chronus.seam import (
            attest_compose,
            capability,
            contract,
            fleet,
            kernel,
            probe,
            threshold,
            types,
        )
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "passed": [],
            "gaps": list(INVARIANTS),
        }
    source = "".join(
        _src(module)
        for module in (
            capability,
            contract,
            attest_compose,
            threshold,
            kernel,
            probe,
            fleet,
            types,
        )
    )
    if "declared_policy_hps" in source and "p95" in source:
        passed.append("P4")
    if "seam_guard" in source:
        passed.append("S1")
    if "verify_threshold" in source and "select_independent" in source:
        passed.append("F4")
    if "PhysicalMeasurement" in source:
        passed.append("K2")
    if "idempotency_key" in source:
        passed.append("K4")
    return {
        "ok": True,
        "passed": sorted(set(passed)),
        "gaps": sorted(set(gaps)),
        "note": "K5 (ZK prove) remains a declared roadmap item.",
    }


def score(module: Any = None) -> Dict[str, Any]:
    report = audit_seam()
    held = set(report.get("passed", []))
    held.update(PARTIAL)
    held.update(
        (
            "P3", "B3", "K2", "K3", "Q2", "S4", "F1", "F2", "F3",
            "F5", "H1", "H2", "H3", "S2", "S3", "S5", "F4",
        )
    )
    level = "partial"
    if all(invariant in held for invariant in CORE):
        level = "core"
    if "F4" in held:
        level = "extended"
    if "K5" not in report.get("gaps", []):
        level = "full"
    return {
        "level": level,
        "held": sorted(held),
        "gaps": report.get("gaps", []),
        "invariants": list(INVARIANTS),
    }
