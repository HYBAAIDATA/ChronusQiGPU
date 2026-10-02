"""Chronus client boundary for the canonical Virtual iGPU runtime.

Chronus no longer needs to identify itself with one OpenCL product.  Consumers
submit versioned workloads; the runtime negotiates the physical/cloud adapter.
"""
from __future__ import annotations

import os

from .virtual_igpu.client import VirtualIGPUClient


def virtual_igpu_client_from_env(*, verify_remote: bool = True) -> VirtualIGPUClient:
    endpoint = os.getenv("CHRONUS_VIGPU_ENDPOINT", "").strip()
    if not endpoint:
        raise RuntimeError("CHRONUS_VIGPU_ENDPOINT is required")
    return VirtualIGPUClient(
        endpoint,
        token=os.getenv("CHRONUS_VIGPU_TOKEN") or None,
        timeout=float(os.getenv("CHRONUS_VIGPU_TIMEOUT", "30")),
        verify_remote=verify_remote,
    )


__all__ = ["VirtualIGPUClient", "virtual_igpu_client_from_env"]