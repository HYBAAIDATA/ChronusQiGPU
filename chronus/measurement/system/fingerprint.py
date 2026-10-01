"""Stable device fingerprint over the fields that actually identify hardware.

Invariants:
    FP1: every fingerprint has a digest.
    FP2: the fingerprint is stable across runs on the same hardware.
    FP3: the fingerprint changes when the driver changes (driver_version is in
         the digest input).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List

from .clinfo import OpenCLDevice


@dataclass
class DeviceFingerprint:
    pci_id: str
    vendor_id: str
    device_id: str
    driver_version: str
    cl_version: str
    digest: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "pci_id": self.pci_id,
            "vendor_id": self.vendor_id,
            "device_id": self.device_id,
            "driver_version": self.driver_version,
            "cl_version": self.cl_version,
            "digest": self.digest,
        }


def compute_fingerprint(device: OpenCLDevice) -> DeviceFingerprint:
    """sha256 over stable identifiers; PCI ids included when the census saw them."""
    components: List[str] = [
        device.name,
        device.vendor,
        device.version,
        device.driver_version,
        device.device_type,
        device.device_class,
        device.backend,
    ]
    pci_id = ""
    vendor_id = ""
    device_id = ""
    if device.pci_ids:
        pci_id = device.pci_ids[0]
        components.append(pci_id)
        if ":" in pci_id:
            vendor_id, device_id = pci_id.split(":", 1)
    digest = hashlib.sha256("|".join(components).encode("utf-8")).hexdigest()
    return DeviceFingerprint(
        pci_id=pci_id,
        vendor_id=vendor_id,
        device_id=device_id,
        driver_version=device.driver_version,
        cl_version=device.version,
        digest=digest,
    )
