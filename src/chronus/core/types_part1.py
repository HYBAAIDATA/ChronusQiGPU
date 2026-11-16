"""Tier 0 — foundational types for the Chronus Elevation roadmap.

This module declares every type the elevation layers reference, including the
labels that make capacity claims machine-checkable (Axiom 1 & 2).
"""

from __future__ import annotations

from dataclasses import dataclass
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


# ---------------------------------------------------------------------------
# Tier 0.5 — Consortium mapping label
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConsortiumProjection:
    """A labelled roadmap target with its honest counterpart.

    Every projection names a label and an evidence class so that Axiom 1
    (representation truth) and Axiom 2 (evidence separation) are type-enforced.
    """

    aspect: str
    projection_value: str
    honest_mapping: str
    label: CapacityLabel
    evidence_class: EvidenceClass

    def is_label(self, label: CapacityLabel) -> bool:
        return self.label == label

    def is_evidence_class(self, evidence: EvidenceClass) -> bool:
        return self.evidence_class == evidence


# ---------------------------------------------------------------------------
# Tier 0.6 — Lucas ladder constants (Axiom 4 & 5: immutable)
# ---------------------------------------------------------------------------


LUCAS_LADDER_RUNGS: tuple[int, ...] = (2, 3, 4, 7, 11, 18, 29, 47, 76, 123, 199)
SPMD_DEFAULT_LANES: int = 32
SPMD_ROADMAP_MAX_LANES: int = 64
CU_POOL_CURRENT_SMS: int = 8
CU_POOL_ROADMAP_MID_SMS: int = 20
CU_POOL_ROADMAP_MAX_SMS: int = 64
