"""Chronus client boundary for the canonical Virtual iGPU runtime.

Chronus no longer needs to identify itself with one OpenCL product.  Consumers
submit versioned workloads; the runtime negotiates the physical/cloud adapter.
"""
from __future__ import annotations

import os

from .virtual_igpu.abi import DeliveryMode
from .virtual_igpu.client import ChronusClient


def virtual_igpu_client_from_env(*, verify_remote: bool = True) -> ChronusClient:
    endpoint = os.getenv("CHRONUS_VIGPU_ENDPOINT", "").strip()
    if not endpoint:
        raise RuntimeError("CHRONUS_VIGPU_ENDPOINT is required")
    client = ChronusClient(
        delivery_mode=DeliveryMode.REMOTE_SERVICE.value,
        endpoint=endpoint,
        auth_token=os.getenv("CHRONUS_VIGPU_TOKEN") or None,
        timeout_s=float(os.getenv("CHRONUS_VIGPU_TIMEOUT", "30")),
    )
    if verify_remote:
        client.health()
    return client


__all__ = ["ChronusClient", "virtual_igpu_client_from_env"]
