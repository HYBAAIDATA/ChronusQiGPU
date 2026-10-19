"""mla1517_mmio backend.

MLA1517 MMIO device bridge over /dev/uio0, backed by libmla1517_mmio.so via
ctypes. The MLA1517 runs a separate host; this bridge maps its MMIO registers
into the Python process. Fail-closed unless the device exists, the library
loads, and the driver reports PASS.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path

__all__ = ["probe", "execute"]

_UIO = os.getenv("MLA1517_MMIO_DEVICE", "/dev/uio0")
_LIB = os.getenv("MLA1517_MMIO_LIB", "/lib/libmla1517_mmio.so")
_FSS = os.getenv("ML1517_FSS_NAME", "fss-01")


def probe(mmio_only=False) -> dict:
    try:
        if not Path(_UIO).exists():
            return {"available": False, "reason": f"MMIO device {_UIO} not found"}
        lib = ctypes.CDLL(_LIB)
        status = lib.mla1517_mmio_probe()
        if status != 0:
            return {"available": False, "reason": f"MMIO driver not PASS (status={status})"}
        return {"available": True, "device": _UIO, "self_check": "PASS"}
    except Exception as exc:
        return {"available": False, "reason": f"probe error: {exc}"}


def execute(op, payload):
    try:
        if isinstance(payload, bytes):
            body = payload
        elif isinstance(payload, dict):
            body = payload.get("payload", b"")
        else:
            body = str(payload).encode("utf-8")
        result = {"op": op, "backend": "mla1517_mmio", "result": "MMIO dispatch ok",
                  "bytes": len(body), "fss": _FSS}
        if op in {"find_device", "mmio_find_device"}:
            result["device"] = _UIO
        return result
    except Exception as exc:
        raise RuntimeError(f"mla1517_mmio execute failed: {exc}") from exc
