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

# ---------------------------------------------------------------------------
# Tier 6.2 - TypedUnavailableAdapter (Axiom 7: complete fallback)
# ---------------------------------------------------------------------------


class TypedUnavailableError(RuntimeError):
    """Raised when a typed-unavailable adapter is asked to execute work."""


class TypedUnavailableAdapter:
    """An adapter known to be functional but that has not passed conformance.

    Axiom 7: execute NEVER silently succeeds. It raises
    TypedUnavailableError so the fleet scheduler can log and handle the
    failure explicitly.
    """

    __slots__ = ("backend", "gate")

    def __init__(self, backend: AdapterBackend, gate: str) -> None:
        self.backend = backend
        self.gate = gate
        self._capability_manifest = self._build_capability()

    def _build_capability(self) -> CapabilityManifest:
        return CapabilityManifest(
            adapter_id=f"typed_unavailable:{self.backend.value}",
            product=self.backend.value,
            backend=self.backend,
            status=AdapterStatus.TYPED_UNAVAILABLE,
            role=self._role_for_backend(),
            core_count=0,
            memory_bytes=0,
            memory_tier=MemoryTier.TIER_0_ON_DEVICE_HBM,
            bandwidth_mbps=0.0,
            spmd_lanes=0,
            trust_class=TrustClass.TYPED_UNAVAILABLE,
            evidence_class=EvidenceClass.PROJECTED,
            projection=None,
        )

    def _role_for_backend(self) -> AdapterRole:
        for spec in ADAPTER_TABLE:
            if spec.backend == self.backend:
                return spec.role
        return RoleEnum.GENERAL

    def execute(self, work_item: dict) -> dict:
        """Raise TypedUnavailableError rather than simulating or faking success."""
        raise TypedUnavailableError(
            backend=str(self.backend),
            gate=self.gate,
            reason="kernel not implemented",
            message=(
                "Conformance test required before promotion (Axiom 8). "
                "This adapter must not be executed."
            ),
        )

    def capability(self) -> CapabilityManifest:
        return self._capability_manifest


def promote_adapter(backend: AdapterBackend, kernel: dict) -> bool:
    """Promote an adapter from TYPED_UNAVAILABLE to FUNCTIONAL.

    Axiom 8: measurement before promotion. The kernel must pass a conformance
    test before it can be routed for real work.
    """
    from chronus.evidence import run_conformance_test

    conformance = run_conformance_test(backend, kernel)
    if not conformance.passed:
        from chronus.governance import elevation_preflight
        from chronus.core.dataclasses import ElevationAction

        action = ElevationAction(
            action_id=f"promote:{backend.value}",
            name="promote_adapter",
            context={"backend": str(backend), "failures": conformance.failures},
        )
        elevation_preflight(action)
        return False

    # Axiom 6: record evidence digest chain
    from chronus.evidence import EvidenceRecord

    evidence = EvidenceRecord(
        layer=str(backend),
        item_id=backend.value,
        input_digest="kernel_manifest",
        config_digest=conformance.digest_chain(),
        output_digest="conformance_passed",
        trust_class=TrustClass.RUNTIME_SIGNED,
    )
    return True
