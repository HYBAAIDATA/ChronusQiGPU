"""Unified GPU dispatcher — one entry point for every vendor backend.

Apple/NVIDIA/HPE posture: enumerate every OpenCL device, identify each
against the vendor catalog, rank HYBA-alias first / GPU second / name
third, and bind explicitly. Forcing a backend the kernels do not
implement (``metal``/``cuda``/``rocm``/``vulkan`` direct dispatch) fails
explicitly — only ``opencl`` executes on-device today, ``cpu`` is the
explicit fallback. Telemetry always reports the device that ran.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from hyba.catalog import DeviceSpec, find_spec
from hyba.device import aliases as hyba_aliases
from hyba.device import require_hyba
from hyba.identify import identify


@dataclass
class RankedDevice:
    """One enumerated device with catalog identity and rank key."""

    index: int
    name: str
    vendor: str
    type_bits: int
    is_gpu: bool
    family: Optional[str]
    dispatch: str
    backends: Tuple[str, ...] = ()
    known: bool = False
    hyba_alias: Optional[str] = None
    rank: Tuple[int, int, str] = field(default_factory=lambda: (1, 1, ""))

    def as_dict(self) -> Dict[str, Any]:
        """JSON-safe ranked-device record."""
        return {
            "index": self.index,
            "name": self.name,
            "vendor": self.vendor,
            "type_bits": self.type_bits,
            "is_gpu": self.is_gpu,
            "family": self.family,
            "dispatch": self.dispatch,
            "backends": list(self.backends),
            "known": self.known,
            "hyba_alias": self.hyba_alias,
            "rank": list(self.rank),
        }


def rank_devices(cl: Any) -> List[RankedDevice]:
    """Enumerate + identify + rank every OpenCL device."""
    try:
        gpu_bit = int(cl.device_type.GPU)
    except Exception:
        gpu_bit = 4
    wanted = tuple(a.lower() for a in hyba_aliases())
    out: List[RankedDevice] = []
    idx = 0
    for plat in cl.get_platforms():
        for dev in plat.get_devices():
            name = str(getattr(dev, "name", "") or "").strip()
            vendor = str(getattr(dev, "vendor", "") or "").strip()
            type_bits = int(getattr(dev, "type", 0) or 0)
            is_gpu = bool(type_bits & gpu_bit)
            name_l = name.lower()
            alias = next((a for a in wanted if a and a in name_l), None)
            ident = identify(name, vendor)
            spec: Optional[DeviceSpec] = find_spec(name, vendor)
            rank = (0 if alias else 1, 0 if is_gpu else 1, name_l)
            out.append(
                RankedDevice(
                    idx,
                    name,
                    vendor,
                    type_bits,
                    is_gpu,
                    spec.family if spec else None,
                    spec.dispatch if spec else "cpu",
                    tuple(spec.backends) if spec else (),
                    ident.known,
                    alias,
                    rank,
                )
            )
            idx += 1
    out.sort(key=lambda d: d.rank)
    return out


def select(cl: Any, want_gpu_only: bool = False) -> Any:
    """Best-ranked device; strict HYBA mode refuses non-alias devices."""
    devices = [d for p in cl.get_platforms() for d in p.get_devices()]
    if want_gpu_only:
        devices = [d for d in devices if d.type & cl.device_type.GPU]
    if not devices:
        raise RuntimeError("no requested OpenCL device")
    wanted = tuple(a.lower() for a in hyba_aliases())
    ranked = sorted(
        devices,
        key=lambda d: (
            0 if any(a and a in str(getattr(d, "name", "")).lower() for a in wanted) else 1,
            0 if d.type & cl.device_type.GPU else 1,
            str(getattr(d, "name", "")).lower(),
        ),
    )
    best = ranked[0]
    best_name = str(getattr(best, "name", "")).lower()
    if any(a and a in best_name for a in wanted):
        return best
    if require_hyba():
        names = [str(getattr(d, "name", "")).strip() for d in devices]
        raise RuntimeError(
            "HYBA_REQUIRE_HYBA set but no HYBA-alias OpenCL device "
            f"enumerated (aliases={list(wanted)}); found: {names}"
        )
    return best


__all__ = ["RankedDevice", "rank_devices", "select"]
