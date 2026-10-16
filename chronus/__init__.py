"""Chronus — HYBA's software-defined quantum-from-maths GPU.

Chronus is one substrate- and hardware-agnostic execution product. In native
mode Chronus is the GPU execution surface itself and requires no host GPU. In
host-augmentation mode it binds into a certified iGPU/GPU/accelerator to extend
or scale that host. CPU, GPU, cloud and future hardware are execution substrates,
not Chronus's product identity.

TURING remains the independent VQC authority, THESEUS owns durable custody and
OVID owns representation transforms. Device-specific claims remain evidence-
bound and are never inferred from the Chronus product name.
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
    "ChronusDevice": ("chronus.domain", "ChronusDevice"),
    "ChronusDeviceType": ("chronus.domain", "ChronusDeviceType"),
    "ChronusBackend": ("chronus.domain", "ChronusBackend"),
    "ChronusExecutionPolicy": ("chronus.domain", "ChronusExecutionPolicy"),
    "ChronusDeviceTopology": ("chronus.domain", "ChronusDeviceTopology"),
    "ChronusCapabilities": ("chronus.domain", "ChronusCapabilities"),
    "ChronusMemory": ("chronus.domain", "ChronusMemory"),
    "ChronusScheduler": ("chronus.domain", "ChronusScheduler"),
    "ChronusExecutionContext": ("chronus.domain", "ChronusExecutionContext"),
    "ChronusRuntime": ("chronus.domain", "ChronusRuntime"),
    "OneIGPU": ("chronus.one_igpu", "OneIGPU"),
    "OneIGPUResult": ("chronus.one_igpu", "OneIGPUResult"),
    "chronus_devices": ("chronus.detect", "chronus_devices"),
    "to_chronus_device": ("chronus.detect", "to_chronus_device"),
    "PhiElement": ("chronus.family_algebra", "PhiElement"),
    "FibonacciOrbit": ("chronus.family_algebra", "FibonacciOrbit"),
    "FamilyCertificate": ("chronus.family_algebra", "FamilyCertificate"),
    "triple_identity": ("chronus.family_algebra", "triple_identity"),
    "M32Manifold": ("chronus.manifold", "M32Manifold"),
    "build_m32": ("chronus.manifold", "build_m32"),
    "fibonacci_sphere": ("chronus.manifold", "fibonacci_sphere"),
    "StructuredHamiltonian": ("chronus.igpu.spec", "StructuredHamiltonian"),
    "GroundState": ("chronus.igpu.spec", "GroundState"),
    "NativePolicy": ("chronus.igpu.spec", "NativePolicy"),
    "compute_native_receipt": ("chronus.igpu.spec", "compute_native_receipt"),
    "verify_native_receipt": ("chronus.igpu.spec", "verify_native_receipt"),
    "ResidentConfig": ("chronus.igpu.resident_hendrix", "ResidentConfig"),
    "ResidentRuntime": ("chronus.igpu.resident_hendrix", "ResidentRuntime"),
    "projection_contract": ("chronus.reference_contract", "projection_contract"),
    "preimage_at": ("chronus.reference_contract", "preimage_at"),
    "preimage_ordinal": ("chronus.reference_contract", "preimage_ordinal"),
    "NonceLease": ("chronus.reference_contract", "NonceLease"),
    "PrimeDB": ("chronus.mla1517.mining.primedb", "PrimeDB"),
    "verify_evidence": ("chronus.evidence", "verify_evidence"),
    "ChronusMode": ("chronus.production", "ChronusMode"),
    "ChronusProductionReport": ("chronus.production", "ChronusProductionReport"),
    "ChronusProductionRuntime": ("chronus.production", "ChronusProductionRuntime"),
    "verify_startup_report": ("chronus.production", "verify_startup_report"),
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
    "ChronusProductMode": ("chronus.virtual_igpu.abi", "ProductMode"),
    "chronus_execution_policy_for_product_mode": (
        "chronus.virtual_igpu.abi",
        "execution_policy_for_product_mode",
    ),
    "ChronusProductionEvidence": ("chronus.readiness", "CoreProductionEvidence"),
    "ChronusEvidenceRef": ("chronus.readiness", "EvidenceRef"),
    "ChronusAcceleratorCertification": ("chronus.readiness", "AcceleratorCertification"),
    "chronus_production_readiness": ("chronus.readiness", "production_readiness"),
    "CONSORTIUM_AXES": ("chronus.m5_ultra", "CONSORTIUM_AXES"),
    "CONSORTIUM_STRATEGIES": ("chronus.m5_ultra", "CONSORTIUM_STRATEGIES"),
    "ELEVATION_STRATEGIES_10PAD": ("chronus.m5_ultra", "ELEVATION_STRATEGIES_10PAD"),
    "ElevationStrategy": ("chronus.m5_ultra", "ElevationStrategy"),
    "FabricChannel": ("chronus.m5_ultra", "FabricChannel"),
    "HamiltonianTerm": ("chronus.m5_ultra", "HamiltonianTerm"),
    "InstitutionalAxis": ("chronus.m5_ultra", "InstitutionalAxis"),
    "LINK_BANDWIDTHS_BPS": ("chronus.m5_ultra", "LINK_BANDWIDTHS_BPS"),
    "MemoryTier": ("chronus.m5_ultra", "MemoryTier"),
    "MESH10_EDGES": ("chronus.m5_ultra", "MESH10_EDGES"),
    "Pad": ("chronus.m5_ultra", "Pad"),
    "PadElevationError": ("chronus.m5_ultra", "PadElevationError"),
    "PadFabric": ("chronus.m5_ultra", "PadFabric"),
    "PadLink": ("chronus.m5_ultra", "PadLink"),
    "PadSpec": ("chronus.m5_ultra", "PadSpec"),
    "TOPOLOGIES": ("chronus.m5_ultra", "TOPOLOGIES"),
    "consortium_fabric": ("chronus.m5_ultra", "consortium_fabric"),
    "Axis": ("chronus.consortium_push", "Axis"),
    "CONSORTIUM_INSTITUTIONS": ("chronus.consortium_push", "CONSORTIUM_INSTITUTIONS"),
    "PushLedger": ("chronus.consortium_push", "PushLedger"),
    "PushProposal": ("chronus.consortium_push", "PushProposal"),
    "PushReceipt": ("chronus.consortium_push", "PushReceipt"),
    "PushVerdict": ("chronus.consortium_push", "PushVerdict"),
    "PushableFabric": ("chronus.consortium_push", "PushableFabric"),
    "TruthClass": ("chronus.consortium_push", "TruthClass"),
    "admit": ("chronus.consortium_push", "admit"),
    "diagnose": ("chronus.consortium_push", "diagnose"),
    "measurement_evidence": ("chronus.consortium_push", "measurement_evidence"),
    "push_cycle": ("chronus.consortium_push", "push_cycle"),
    "verify_ledger": ("chronus.consortium_push", "verify_ledger"),
    "elevate_pads": ("chronus.m5_ultra", "elevate_pads"),
    "m5_ultra_expectation_values": ("chronus.m5_ultra", "m5_ultra_expectation_values"),
    "m5_ultra_fabric": ("chronus.m5_ultra", "m5_ultra_fabric"),
    "pad_edges": ("chronus.m5_ultra", "pad_edges"),
    "quantum_formulation_map": ("chronus.m5_ultra", "quantum_formulation_map"),
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
