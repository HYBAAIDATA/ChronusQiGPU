"""Bind measured work to the baseline device that actually executed it.

The Chronus contract device and physical execution devices intentionally coexist
in the census. This module prevents a measurement artifact from confusing the
logical contract identity with the OpenCL/CUDA/Metal device that produced work.
"""
from __future__ import annotations

from typing import Any, Dict


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _field(value: Any, name: str, default: Any = "") -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _execution_backend(backend: str) -> str:
    """Reduce Chronus backend labels to the physical census backend name."""
    value = _norm(backend)
    if value.startswith("chronus-"):
        value = value[len("chronus-") :]
    return value.split(":", 1)[0]


def bind_execution_device(
    baseline: Any,
    *,
    workload: str,
    backend: str,
    device_id: str,
) -> Dict[str, Any]:
    """Return an evidence record for the device that executed ``workload``.

    Matching first requires device-identity evidence. If runtime and census use
    different device naming schemes, a second match is permitted only when the
    declared physical backend maps to exactly one censused device. That method
    is reported explicitly as ``baseline_unique_backend_match`` rather than
    masquerading as a name match.

    A logical ``chronus`` contract record is never substituted for an
    OpenCL/CUDA/Metal execution device. ``baseline`` may be the live
    ``SystemBaseline`` or its attested dictionary.
    """
    backend_norm = _norm(backend)
    device_norm = _norm(device_id)
    physical_backend = _execution_backend(backend)
    devices = list(_field(baseline, "devices", ()) or ())
    fingerprints = list(_field(baseline, "fingerprints", ()) or ())

    best_index = -1
    best_score = 0
    for index, device in enumerate(devices):
        name = _norm(_field(device, "name", ""))
        candidate_backend = _norm(_field(device, "backend", ""))

        if candidate_backend == "chronus" and physical_backend != "chronus":
            continue

        score = 0
        if name and device_norm and (
            name == device_norm or name in device_norm or device_norm in name
        ):
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
    method = "baseline_device_identity_match" if matched else "unmatched"

    # Some native APIs expose a logical runtime device string while the system
    # census exposes the chipset model. Backend identity is sufficient only if
    # the census proves there is exactly one physical candidate for that API.
    if not matched and device_norm and device_norm != "unavailable" and physical_backend:
        backend_candidates = [
            index
            for index, device in enumerate(devices)
            if _norm(_field(device, "backend", "")) == physical_backend
        ]
        if len(backend_candidates) == 1:
            best_index = backend_candidates[0]
            matched = True
            method = "baseline_unique_backend_match"

    fingerprint = ""
    matched_device = ""
    matched_backend = ""
    if matched:
        device = devices[best_index]
        matched_device = str(_field(device, "name", "") or "")
        matched_backend = str(_field(device, "backend", "") or "")
        if best_index < len(fingerprints):
            fingerprint = str(_field(fingerprints[best_index], "digest", "") or "")

    return {
        "workload": str(workload),
        "backend": str(backend or ""),
        "device_id": str(device_id or ""),
        "matched": bool(matched and fingerprint),
        "device_fingerprint": fingerprint,
        "matched_device": matched_device,
        "matched_backend": matched_backend,
        "method": method if matched and fingerprint else "unmatched",
    }
