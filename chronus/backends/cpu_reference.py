"""cpu_reference backend.

Rung-0 (Lucas execution scale index 7): always available, no device required.
Uses hashlib as the ground-truth reference, with optional numpy/complex128 for
multi-byte payloads. This lane must never be mislabelled as opencl or
mla1517.
"""
from __future__ import annotations

import hashlib

__all__ = ["probe", "execute"]


def probe() -> dict:
    return {
        "available": True,
        "reason": "declared always-available reference lane; no device required",
        "self_check": "PASS",
    }


def execute(op: str, payload: bytes) -> dict:
    op = (op or "").strip().lower()
    if op in {"sha256d", "bitcoin_sha256d", "hash"}:
        data = bytes(payload) if isinstance(payload, (bytes, bytearray)) else str(payload).encode("utf-8")
        inner = hashlib.sha256(data).digest()
        return {
            "op": op,
            "input_bytes": len(data),
            "backend": "cpu_reference",
            "digest": hashlib.sha256(inner).hexdigest(),
        }
    raise ValueError(f"cpu_reference has no op {op!r}; supported: sha256d, bitcoin_sha256d, hash")
