# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""CUDA adapter (stub): the host's NVIDIA GPU, Mode B.

The probe looks for ``cupy`` or ``numba.cuda`` only when the package is
importable; neither is a dependency and neither is installed by Chronus. No
built-in kernel has a CUDA implementation yet, so even on a machine with a
CUDA device the self-test finds no applicable known answer and the route
fails closed. A kernel that adds ``run_cuda`` (and passes its known answers)
is all it takes to make the route usable.
"""

from __future__ import annotations

import importlib.util
from typing import Any

from chronus.fleet.adapters import MODE_B, DeviceAdapter
from chronus.fleet.kernels import ROUTE_CUDA


def _cupy_device() -> tuple[bool, dict[str, Any], str | None, Any]:
    if importlib.util.find_spec("cupy") is None:
        return False, {}, "cupy is not installed", None
    import cupy  # type: ignore[import-not-found]

    count = int(cupy.cuda.runtime.getDeviceCount())
    if count < 1:
        return False, {}, "cupy found no CUDA device", None
    props = cupy.cuda.runtime.getDeviceProperties(0)
    name = props.get("name", b"")
    name = name.decode("utf-8", "replace") if isinstance(name, bytes) else str(name)
    return True, {"engine": "cupy", "name": name, "devices": count}, None, {"engine": "cupy"}


def _numba_device() -> tuple[bool, dict[str, Any], str | None, Any]:
    if importlib.util.find_spec("numba") is None:
        return False, {}, "numba is not installed", None
    from numba import cuda  # type: ignore[import-not-found]

    if not cuda.is_available():
        return False, {}, "numba.cuda reports no usable CUDA device", None
    device = cuda.get_current_device()
    name = device.name.decode("utf-8", "replace") if isinstance(device.name, bytes) else str(device.name)
    return True, {"engine": "numba.cuda", "name": name}, None, {"engine": "numba.cuda"}


class CudaAdapter(DeviceAdapter):
    route = ROUTE_CUDA
    name = "cuda"
    silicon = "gpu"
    mode = MODE_B

    def _detect(self):
        reasons = []
        for detect in (_cupy_device, _numba_device):
            try:
                available, device, reason, ctx = detect()
            except Exception as exc:  # a broken driver is an absent device
                available, device, reason, ctx = False, {}, f"{type(exc).__name__}: {exc}", None
            if available:
                return True, device, None, ctx
            reasons.append(reason)
        return False, {}, "; ".join(r for r in reasons if r) or "no CUDA runtime", None
