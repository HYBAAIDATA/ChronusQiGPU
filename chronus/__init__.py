"""Chronus — HYBA's canonical iGPU offering.

Turing is the computation substrate. Chronus is the hardware-facing offering
that binds Turing computation to measured device discovery, resident execution,
state memory, kernel dispatch, telemetry, routing and attestation.
"""

from .device import CLAIM_BOUNDARY, DEVICE_ID, Chronus, open_device
from .engine import (
    ChronusOpenCLEngine,
    ChronusOpenCLUnavailable,
    ResidentChronusEnsemble,
    ResidentChronusState,
)
from .fabric import ChronusFabric, RouteDecision
from .phi_gpu import (
    PHI_GPU_CORES,
    EnergyComparison,
    EnergyModel,
    GeodesicScheduler,
    HybridGPU,
    KernelLaunchConfig,
    KernelResult,
    KernelTask,
    PhiGPU,
    PhiGPUError,
    RouteDecisionRecord,
    phi_log_distance,
)

__all__ = [
    "Chronus",
    "ChronusFabric",
    "ChronusOpenCLEngine",
    "ChronusOpenCLUnavailable",
    "EnergyComparison",
    "EnergyModel",
    "GeodesicScheduler",
    "HybridGPU",
    "KernelLaunchConfig",
    "KernelResult",
    "KernelTask",
    "PHI_GPU_CORES",
    "PhiGPU",
    "PhiGPUError",
    "ResidentChronusEnsemble",
    "ResidentChronusState",
    "RouteDecision",
    "RouteDecisionRecord",
    "open_device",
    "phi_log_distance",
    "CLAIM_BOUNDARY",
    "DEVICE_ID",
]
