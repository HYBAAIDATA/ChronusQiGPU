"""Driver capture — whatever the backend reported, dated when the OS tells us.

Invariants:
    DRV1: the driver version is captured (empty string means "not reported").
    DRV2: the driver date is captured when available, else listed unknown.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .clinfo import OpenCLDevice


@dataclass
class DriverInfo:
    name: str
    version: str
    date: str
    vendor: str
    backend: str
    date_unknown: bool

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "date": self.date,
            "vendor": self.vendor,
            "backend": self.backend,
            "date_unknown": self.date_unknown,
        }


def capture_driver_info(device: OpenCLDevice, driver_date: Optional[str] = None) -> DriverInfo:
    """The census carries one version string per backend; no separate OS query."""
    return DriverInfo(
        name=device.backend or device.vendor,
        version=device.driver_version,
        date=driver_date or "",
        vendor=device.vendor,
        backend=device.backend,
        date_unknown=driver_date is None,
    )
