"""Bind measured work to the baseline device that actually executed it.

The Chronus contract device and physical execution devices intentionally coexist
in the census. This module prevents a measurement artifact from confusing the
logical contract identity with the OpenCL/CUDA/Metal device that produced work.
"""
from __future__ import annotations

from typing import Any, Dict


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def bind_execution_device(
    baseline: Any,
    *,
    workload: str,
    backend: str,
    device_id: str,
) -> Dict[str, Any]:
    """Return an evidence record for the device that executed ``workload``.

    Matching is evidence-based: the workload must expose a device identity that
    names a censused device. A logical ``chronus`` contract record is never
    silently substituted for an OpenCL/CUDA/Metal execution device.
    """
    backend_norm = _norm(backend)
    device_norm = _norm(device_id)
    devices = list(getattr(baseline, "devices", ()) or ())
    fingerprints = list(getattr(baseline, "fingerprints", ()) or ())

    best_index = -1
    best_score = 0
    for index, device in enumerate(devices):
        name = _norm(getattr(device, "name", ""))
        candidate_backend = _norm(getattr(device, "backend", ""))

        if candidate_backend == "chronus" and not backend_norm.startswith("chronus"):
            continue

        score = 0
        if name and device_norm and (name == device_norm or name in device_norm or device_norm in name):
            score += 100
        if name and name in backend_norm:
            score += 80
        if candidate_backend and backend_norm:
            if backend_norm == candidate_backend:
                score += 40
            elif backend_norm.startswith(candidate_backend + ":"):
                score += 35
            elif candidate_backend in backend_norm:
                score += 20

        if score > best_score:
            best_index = index
            best_score = score

    matched = best_index >= 0 and best_score >= 80
    fingerprint = ""
    matched_device = ""
    matched_backend = ""
    if matched:
        device = devices[best_index]
        matched_device = str(getattr(device, "name", "") or "")
        matched_backend = str(getattr(device, "backend", "") or "")
        if best_index < len(fingerprints):
            fingerprint = str(getattr(fingerprints[best_index], "digest", "") or "")

    return {
        "workload": str(workload),
        "backend": str(backend or ""),
        "device_id": str(device_id or ""),
        "matched": bool(matched and fingerprint),
        "device_fingerprint": fingerprint,
        "matched_device": matched_device,
        "matched_backend": matched_backend,
        "method": "baseline_device_identity_match" if matched and fingerprint else "unmatched",
    }
