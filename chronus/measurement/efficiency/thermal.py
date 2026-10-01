"""Thermal state — real temperature sensors where the OS exposes them.

Sources tried: Linux ``/sys/class/thermal/thermal_zone*/temp`` then
``hwmon`` names. Absent → ``available=False`` with the sources listed.

Invariants:
    TH1: temperatures are read from sensors or declared unknown.
"""

from __future__ import annotations

import glob
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ThermalMeasurement:
    celsius: Dict[str, float]
    available: bool
    sources_tried: List[str] = field(default_factory=list)
    reason: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "celsius": dict(self.celsius),
            "available": self.available,
            "sources_tried": list(self.sources_tried),
            "reason": self.reason,
        }


def measure_thermal() -> ThermalMeasurement:
    zones = glob.glob("/sys/class/thermal/thermal_zone*/temp")
    readings: Dict[str, float] = {}
    tried = ["sysfs_thermal_zones(absent)"]
    if zones:
        tried = ["sysfs_thermal_zones"]
        for i, path in enumerate(zones):
            try:
                with open(path, encoding="ascii") as fh:
                    readings[f"zone{i}"] = int(fh.read().strip()) / 1000.0
            except (OSError, ValueError):
                continue
    hwmon = glob.glob("/sys/class/hwmon/hwmon*/temp*_input")
    if hwmon:
        tried.append("hwmon")
        for i, path in enumerate(hwmon[:8]):
            try:
                with open(path, encoding="ascii") as fh:
                    readings[f"hwmon{i}"] = int(fh.read().strip()) / 1000.0
            except (OSError, ValueError):
                continue
    if not readings:
        return ThermalMeasurement(
            celsius={},
            available=False,
            sources_tried=tried,
            reason="no thermal sensor surface on this host",
        )
    return ThermalMeasurement(celsius=readings, available=True, sources_tried=tried)
