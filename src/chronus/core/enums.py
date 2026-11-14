"""ENUM types for the Chronus elevation roadmap (Tier 0).

All ENUM types follow the repository convention of str-enums for
machine-readable equality checks.
"""

from __future__ import annotations

from enum import Enum


class CapacityLabel(str, Enum):
    """How a capacity number may be used.

    EFFECTIVE_CAPACITY  measured on live hardware, test-verified.
    DESIGN_ENVELOPE     architecture exists; physical instantiation external.
    ROADMAP_TARGET      aspirational; not currently claimed.
    """

    EFFECTIVE_CAPACITY = "effective_capacity"
    DESIGN_ENVELOPE = "design_envelope"
    ROADMAP_TARGET = "roadmap_target"


class TrustClass(str, Enum):
    """How much external authority a piece of work carries.

    HARDWARE_ROOTED     external gate; not yet achieved.
    RUNTIME_SIGNED      current boundary.
    SOFTWARE_EMULATED   CPU fallback baseline.
    TYPED_UNAVAILABLE   adapter stub; must never silently succeed.
    """

    HARDWARE_ROOTED = "hardware_rooted"
    RUNTIME_SIGNED = "runtime_signed"
    SOFTWARE_EMULATED = "software_emulated"
    TYPED_UNAVAILABLE = "typed_unavailable"


class EvidenceClass(str, Enum):
    """Evidentiary status of a claim about the system."""

    MEASURED = "measured"
    PROJECTED = "projected"
    THEORETICAL = "theoretical"


class AdapterBackend(str, Enum):
    """Backend device family the scheduler can route work to."""

    CPU_SOFTWARE = "cpu_software"
    OPENCL_INTEL_UHD = "opencl_intel_uhd"
    CUDA_NVIDIA = "cuda_nvidia"
    ROCM_AMD = "rocm_amd"
    ONEAPI_INTEL = "oneapi_intel"
    METAL_APPLE = "metal_apple"
    AZURE_GPU = "azure_gpu"
    GCP_GPU = "gcp_gpu"


class AdapterRole(str, Enum):
    """Semantic role a device plays in the fleet."""

    GENERAL = "general"
    DATA_INGEST = "data_ingest"
    TENSOR_COMPUTE = "tensor_compute"
    VERIFICATION = "verification"
    PHOTONIC = "photonic"
    AI_TRAINING = "ai_training"


class AdapterStatus(str, Enum):
    """Operational status of a concrete adapter instance."""

    FUNCTIONAL = "functional"
    OPTIONAL = "optional"
    TYPED_UNAVAILABLE = "typed_unavailable"


class MemoryTier(str, Enum):
    """Memory tiering (§2.5)."""

    TIER_0_ON_DEVICE_HBM = "tier_0_on_device_hbm"
    TIER_1_DRAM_POOL = "tier_1_dram_pool"
    TIER_2_REMOTE_CLOUD = "tier_2_remote_cloud"
    TIER_3_QUANTUM_RAM = "tier_3_quantum_ram"


class Axiom(str, Enum):
    """The eight Universal Principle Map axioms enforced by the governance layer."""

    A1_REPRESENTATION_TRUTH = "A1_REPRESENTATION_TRUTH"
    A2_EVIDENCE_SEPARATION = "A2_EVIDENCE_SEPARATION"
    A3_VALIDITY_AUTHORITY = "A3_VALIDITY_AUTHORITY"
    A4_FINITE_RESOURCE_ACCOUNTING = "A4_FINITE_RESOURCE_ACCOUNTING"
    A5_IMMUTABLE_REFERENCE_CONSTANTS = "A5_IMMUTABLE_REFERENCE_CONSTANTS"
    A6_DETERMINISTIC_PROVENANCE = "A6_DETERMINISTIC_PROVENANCE"
    A7_COMPLETE_FALLBACK = "A7_COMPLETE_FALLBACK"
    A8_MEASUREMENT_BEFORE_PROMOTION = "A8_MEASUREMENT_BEFORE_PROMOTION"
