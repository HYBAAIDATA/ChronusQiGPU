"""Device enumeration — the real census, not a clinfo scrape.

``chronus.detect.detect_all()`` already enumerates every backend this host can
see (CUDA, Metal, OpenCL, the Chronus contract device) and records what each
backend could not report in ``errors``. Fields a backend never observed stay
``None`` and the property name lands in ``properties_unknown``.

Invariants:
    SYS1: every enumerated device has a name.
    SYS2: unknown properties are listed in ``properties_unknown``, not guessed.
    SYS3: the enumeration is reproducible across runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ...detect import detect_all


@dataclass
class OpenCLDevice:
    name: str
    vendor: str
    version: str
    driver_version: str
    device_type: str  # GPU, CPU, ACCELERATOR
    device_class: str  # integrated, discrete
    backend: str = ""
    max_compute_units: Optional[int] = None
    max_clock_mhz: Optional[int] = None
    global_memory_bytes: Optional[int] = None
    local_memory_bytes: Optional[int] = None
    max_work_group_size: Optional[int] = None
    extensions: List[str] = field(default_factory=list)
    properties_unknown: List[str] = field(default_factory=list)
    pci_ids: List[str] = field(default_factory=list)
    host_unified_memory: Optional[bool] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "vendor": self.vendor,
            "version": self.version,
            "driver_version": self.driver_version,
            "device_type": self.device_type,
            "device_class": self.device_class,
            "backend": self.backend,
            "max_compute_units": self.max_compute_units,
            "max_clock_mhz": self.max_clock_mhz,
            "global_memory_bytes": self.global_memory_bytes,
            "local_memory_bytes": self.local_memory_bytes,
            "max_work_group_size": self.max_work_group_size,
            "extensions": list(self.extensions),
            "properties_unknown": list(self.properties_unknown),
            "pci_ids": list(self.pci_ids),
            "host_unified_memory": self.host_unified_memory,
        }


@dataclass
class OpenCLPlatform:
    name: str
    vendor: str
    version: str
    devices: List[OpenCLDevice] = field(default_factory=list)
    extensions: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "vendor": self.vendor,
            "version": self.version,
            "extensions": list(self.extensions),
            "devices": [d.as_dict() for d in self.devices],
        }


def _from_detected(detected: Any) -> OpenCLDevice:
    unknown = []
    for prop in (
        "max_compute_units",
        "max_clock_mhz",
        "global_memory_bytes",
        "local_memory_bytes",
        "max_work_group_size",
    ):
        if getattr(detected, prop, None) is None:
            unknown.append(prop)
    if not getattr(detected, "pci_ids", ()):
        unknown.append("pci_ids")
    return OpenCLDevice(
        name=detected.name,
        vendor=detected.vendor,
        version=detected.version,
        driver_version=detected.driver_version,
        device_type="GPU" if detected.is_gpu else "CPU",
        device_class="integrated" if detected.is_integrated else "discrete",
        backend=detected.backend,
        extensions=[],
        properties_unknown=unknown,
        pci_ids=list(getattr(detected, "pci_ids", ()) or ()),
        host_unified_memory=detected.host_unified_memory,
    )


def enumerate_devices() -> List[OpenCLPlatform]:
    """Group the real census into platform records, one per backend."""
    report = detect_all()
    platforms: Dict[str, OpenCLPlatform] = {}
    for detected in report.devices:
        platform_name = detected.platform or detected.backend or "unknown"
        key = f"{detected.backend}:{platform_name}"
        platform = platforms.setdefault(
            key,
            OpenCLPlatform(
                name=platform_name,
                vendor=detected.vendor,
                version=detected.version,
                devices=[],
            ),
        )
        platform.devices.append(_from_detected(detected))
    return list(platforms.values())
