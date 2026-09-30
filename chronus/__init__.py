"""Chronus — HYBA's canonical iGPU offering.

Turing is the computation substrate. Chronus is the hardware-facing offering
that binds Turing computation to measured device discovery, resident execution,
state memory, kernel dispatch, telemetry, routing and attestation.
"""

from .device import CLAIM_BOUNDARY, DEVICE_ID, Chronus, open_device
from .fabric import ChronusFabric, RouteDecision

__all__ = [
    "Chronus",
    "ChronusFabric",
    "RouteDecision",
    "open_device",
    "CLAIM_BOUNDARY",
    "DEVICE_ID",
]
