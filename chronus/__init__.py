"""Chronus — HYBA's software-defined heterogeneous execution product.

Chronus is the heterogeneous execution and acceleration plane (Virtual iGPU):
measured device discovery, resident execution, state memory, kernel dispatch,
telemetry, routing and attestation. TURING remains the independent VQC
authority, THESEUS owns durable custody and OVID owns representation transforms.

CHRONUS has two owner-approved product modes: standalone software execution,
which requires no physical GPU, and accelerator-enhanced execution, which binds
to a certified device when present. Hardware probing stays lazy: importing
:mod:`chronus` never requires OpenCL, CUDA, Metal or a physical accelerator.
"""
from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .detect import DetectedDevice, DetectionReport
    from .device import Chronus
    from .engine import ChronusOpenCLEngine, ChronusOpenCLUnavailable, ResidentChronusEnsemble, ResidentChronusState
    from .fabric import ChronusFabric, RouteDecision
    from .phi_gpu import (
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
    from .telemetry import ChronusTelemetry
    from .tensor_compute import ChronusTensorRuntime, ChronusTensorUnavailable, TensorDeviceProbe

_EXPORTS = {
    "ChronusSubstrateMiningBridge": (
        "chronus.mining_bridge",
        "ChronusSubstrateMiningBridge",
    ),
    "SubstrateOrderingEvidence": (
        "chronus.mining_bridge",
        "SubstrateOrderingEvidence",
    ),
    "BufferAttestation": ("chronus.gpu_capabilities", "BufferAttestation"),
    "BufferIntegrityGate": ("chronus.gpu_capabilities", "BufferIntegrityGate"),
    "ChronusTensorPipeline": ("chronus.gpu_capabilities", "ChronusTensorPipeline"),
    "GPUCapabilityError": ("chronus.gpu_capabilities", "GPUCapabilityError"),
    "GPUDeviceTopology": ("chronus.gpu_capabilities", "GPUDeviceTopology"),
    "GPUMemoryHierarchyProfile": ("chronus.gpu_capabilities", "GPUMemoryHierarchyProfile"),
    "GPUMemoryLevel": ("chronus.gpu_capabilities", "GPUMemoryLevel"),
    "TensorExecutionEvidence": ("chronus.gpu_capabilities", "TensorExecutionEvidence"),
    "TensorInvariantReport": ("chronus.gpu_capabilities", "TensorInvariantReport"),
    "TensorInvariantVerifier": ("chronus.gpu_capabilities", "TensorInvariantVerifier"),
    "TopologyLink": ("chronus.gpu_capabilities", "TopologyLink"),
    "gpu_capability_status": ("chronus.gpu_capabilities", "gpu_capability_status"),
    "memory_hierarchy_from_topology": (
        "chronus.gpu_capabilities",
        "memory_hierarchy_from_topology",
    ),
    "probe_opencl_topology": ("chronus.gpu_capabilities", "probe_opencl_topology"),
    "reference_gpu_topology": ("chronus.gpu_capabilities", "reference_gpu_topology"),
    "CLAIM_BOUNDARY": ("chronus.device", "CLAIM_BOUNDARY"),
    "DEVICE_ID": ("chronus.device", "DEVICE_ID"),
    "Chronus": ("chronus.device", "Chronus"),
    "ChronusFabric": ("chronus.fabric", "ChronusFabric"),
    "ChronusOpenCLEngine": ("chronus.engine", "ChronusOpenCLEngine"),
    "ChronusOpenCLUnavailable": ("chronus.engine", "ChronusOpenCLUnavailable"),
    "ChronusTelemetry": ("chronus.telemetry", "ChronusTelemetry"),
    "DetectedDevice": ("chronus.detect", "DetectedDevice"),
    "DetectionReport": ("chronus.detect", "DetectionReport"),
    "EnergyComparison": ("chronus.phi_gpu", "EnergyComparison"),
    "EnergyModel": ("chronus.phi_gpu", "EnergyModel"),
    "GeodesicScheduler": ("chronus.phi_gpu", "GeodesicScheduler"),
    "HybridGPU": ("chronus.phi_gpu", "HybridGPU"),
    "KernelLaunchConfig": ("chronus.phi_gpu", "KernelLaunchConfig"),
    "KernelResult": ("chronus.phi_gpu", "KernelResult"),
    "KernelTask": ("chronus.phi_gpu", "KernelTask"),
    "PHI_GPU_CORES": ("chronus.phi_gpu", "PHI_GPU_CORES"),
    "PhiGPU": ("chronus.phi_gpu", "PhiGPU"),
    "PhiGPUError": ("chronus.phi_gpu", "PhiGPUError"),
    "ResidentChronusEnsemble": ("chronus.engine", "ResidentChronusEnsemble"),
    "ResidentChronusState": ("chronus.engine", "ResidentChronusState"),
    "RouteDecision": ("chronus.fabric", "RouteDecision"),
    "RouteDecisionRecord": ("chronus.phi_gpu", "RouteDecisionRecord"),
    "attach_to_host": ("chronus.telemetry", "attach_to_host"),
    "detect_all": ("chronus.detect", "detect_all"),
    "get_telemetry": ("chronus.telemetry", "get_telemetry"),
    "open_device": ("chronus.device", "open_device"),
    "ChronusTensorRuntime": ("chronus.tensor_compute", "ChronusTensorRuntime"),
    "ChronusTensorUnavailable": ("chronus.tensor_compute", "ChronusTensorUnavailable"),
    "TensorDeviceProbe": ("chronus.tensor_compute", "TensorDeviceProbe"),
    "get_tensor_runtime": ("chronus.tensor_compute", "get_tensor_runtime"),
    "probe_tensor": ("chronus.tensor_compute", "probe_tensor"),
    "ChronusProductionEvidence": ("chronus.readiness", "CoreProductionEvidence"),
    "ChronusEvidenceRef": ("chronus.readiness", "EvidenceRef"),
    "ChronusAcceleratorCertification": ("chronus.readiness", "AcceleratorCertification"),
    "chronus_production_readiness": ("chronus.readiness", "production_readiness"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
