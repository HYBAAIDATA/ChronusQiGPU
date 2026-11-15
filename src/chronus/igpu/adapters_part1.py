"""IGPU adapters - Tier 6 cloud adapter declarations for the Chronus elevation.

This module implements:

    PHASE 5 - Cloud Adapters (External, 4-8 weeks)
        Deliverable: adapters report unavailable until configured; never simulate.
        Metric: >= 1 adapter with live conformance test.
        Gate: cloud manifest + credentials; hardware-rooted attestation external.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from chronus.core.enums import (
    AdapterBackend,
    AdapterRole,
    AdapterStatus,
    EvidenceClass,
    CapacityLabel,
    TrustClass,
    MemoryTier,
)
from chronus.core.dataclasses import CapabilityManifest, EffectiveCapacity
from chronus.core.constants import LUCAS_LADDER_RUNGS

from .abi import AdapterRole as RoleEnum

__all__ = ["ADAPTER_TABLE", "TypedUnavailableAdapter", "promote_adapter"]


# ---------------------------------------------------------------------------
# Tier 6.1 - Full adapter table (section 2.3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdapterSpec:
    """A row in the adapter table (section 2.3)."""

    backend: AdapterBackend
    status: AdapterStatus
    gate: str
    role: AdapterRole
    trust_class: TrustClass


ADAPTER_TABLE: tuple[AdapterSpec, ...] = (
    AdapterSpec(
        backend=AdapterBackend.CPU_SOFTWARE,
        status=AdapterStatus.FUNCTIONAL,
        gate="mvp_baseline",
        role=RoleEnum.GENERAL,
        trust_class=TrustClass.SOFTWARE_EMULATED,
    ),
    AdapterSpec(
        backend=AdapterBackend.OPENCL_INTEL_UHD,
        status=AdapterStatus.OPTIONAL,
        gate="integrated_optional",
        role=RoleEnum.GENERAL,
        trust_class=TrustClass.RUNTIME_SIGNED,
    ),
    AdapterSpec(
        backend=AdapterBackend.CUDA_NVIDIA,
        status=AdapterStatus.TYPED_UNAVAILABLE,
        gate="real_kernel_plus_evidence_test",
        role=RoleEnum.TENSOR_COMPUTE,
        trust_class=TrustClass.TYPED_UNAVAILABLE,
    ),
    AdapterSpec(
        backend=AdapterBackend.ROCM_AMD,
        status=AdapterStatus.TYPED_UNAVAILABLE,
        gate="real_kernel_plus_evidence_test",
        role=RoleEnum.TENSOR_COMPUTE,
        trust_class=TrustClass.TYPED_UNAVAILABLE,
    ),
    AdapterSpec(
        backend=AdapterBackend.ONEAPI_INTEL,
        status=AdapterStatus.TYPED_UNAVAILABLE,
        gate="real_kernel_plus_evidence_test",
        role=RoleEnum.TENSOR_COMPUTE,
        trust_class=TrustClass.TYPED_UNAVAILABLE,
    ),
    AdapterSpec(
        backend=AdapterBackend.METAL_APPLE,
        status=AdapterStatus.TYPED_UNAVAILABLE,
        gate="real_kernel_plus_evidence_test",
        role=RoleEnum.TENSOR_COMPUTE,
        trust_class=TrustClass.TYPED_UNAVAILABLE,
    ),
    AdapterSpec(
        backend=AdapterBackend.AZURE_GPU,
        status=AdapterStatus.TYPED_UNAVAILABLE,
        gate="cloud_manifest_plus_credentials",
        role=RoleEnum.AI_TRAINING,
        trust_class=TrustClass.TYPED_UNAVAILABLE,
    ),
    AdapterSpec(
        backend=AdapterBackend.GCP_GPU,
        status=AdapterStatus.TYPED_UNAVAILABLE,
        gate="cloud_manifest_plus_credentials",
        role=RoleEnum.AI_TRAINING,
        trust_class=TrustClass.TYPED_UNAVAILABLE,
    ),
)
