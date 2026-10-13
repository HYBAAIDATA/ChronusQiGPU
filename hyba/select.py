"""HYBA device selection — one ranking over enumerated OpenCL devices.

``select`` prefers the HYBA alias match, then any GPU, then the first
device. With ``require_hyba=True`` it raises instead of substituting.
``hyba.device`` stays dependency-free (name matching only); this module
needs pyopencl to enumerate.
"""

from __future__ import annotations

from typing import Any, Optional

from hyba.device import aliases, require_hyba


def select(cl: Any, want_gpu_only: bool = False, alias_list: Optional[tuple] = None) -> Any:
    """Select the HYBA device, else first GPU, else first enumerated device."""
    devices = [d for p in cl.get_platforms() for d in p.get_devices()]
    if want_gpu_only:
        devices = [d for d in devices if d.type & cl.device_type.GPU]
    if not devices:
        raise RuntimeError("no requested OpenCL device")
    names = [str(getattr(d, "name", "") or "").strip() for d in devices]
    wanted = alias_list if alias_list is not None else aliases()
    strict = require_hyba()
    for dev, name in zip(devices, names):
        lowered = name.lower()
        if any(a and a in lowered for a in wanted):
            return dev
    if strict:
        raise RuntimeError(
            "HYBA_REQUIRE_HYBA set but no HYBA-alias OpenCL device "
            f"enumerated (aliases={list(wanted)}); found: {names}"
        )
    gpu = next((d for d in devices if d.type & cl.device_type.GPU), None)
    return gpu if gpu is not None else devices[0]
