"""System baseline — the census + fingerprints + host identity, self-sealed.

Invariants:
    BL1: every baseline has at least one platform.
    BL2: every baseline has at least one device.
    BL3: every baseline is attested (sha256 self-seal of its canonical JSON —
         stronger attestation lives in measurement.attestation for artifacts).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .._common import canonical_json, kernel_label, os_label, python_label
from .clinfo import OpenCLDevice, OpenCLPlatform, enumerate_devices
from .driver import DriverInfo, capture_driver_info
from .fingerprint import DeviceFingerprint, compute_fingerprint


@dataclass
class SystemBaseline:
    platforms: List[OpenCLPlatform]
    devices: List[OpenCLDevice]
    fingerprints: List[DeviceFingerprint]
    drivers: List[DriverInfo]
    os: str
    kernel: str
    python_version: str
    attestation: str = ""
    enumeration_errors: Dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "platforms": [p.as_dict() for p in self.platforms],
            "devices": [d.as_dict() for d in self.devices],
            "fingerprints": [f.as_dict() for f in self.fingerprints],
            "drivers": [d.as_dict() for d in self.drivers],
            "os": self.os,
            "kernel": self.kernel,
            "python_version": self.python_version,
            "attestation": self.attestation,
            "enumeration_errors": dict(self.enumeration_errors),
        }


def _seal(baseline: "SystemBaseline") -> str:
    payload = baseline.as_dict()
    payload["attestation"] = ""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def capture_baseline() -> SystemBaseline:
    """Enumerate, fingerprint, seal. Raises honestly when nothing is visible."""
    platforms = enumerate_devices()
    if not platforms:
        raise RuntimeError("no devices enumerated by any backend")
    devices = [d for platform in platforms for d in platform.devices]
    if not devices:
        raise RuntimeError("platforms enumerated with no devices")
    from ...detect import detect_all

    report = detect_all()
    baseline = SystemBaseline(
        platforms=platforms,
        devices=devices,
        fingerprints=[compute_fingerprint(d) for d in devices],
        drivers=[capture_driver_info(d) for d in devices],
        os=os_label(),
        kernel=kernel_label(),
        python_version=python_label(),
        enumeration_errors=dict(report.errors),
    )
    baseline.attestation = _seal(baseline)
    return baseline
