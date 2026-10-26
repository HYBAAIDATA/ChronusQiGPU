"""Isolated Engineering Cohorts & 120-Slot Reference Fleet Allocation Model.

Implements Section 4 of the Native Quantum Fleet Elevation Mandate:
- Defines bounded engineering cohorts (`VERIFIER`, `BENCHMARK`, `SHADOW`, `CANARY`, `PRODUCTION`),
  each pinned to an immutable `(artifact_sha256, policy_id, telemetry_schema)`.
- Enforces `CohortBoundaryGuard`: discovery or learning cohorts may propose candidate
  parameters, schedules, or kernels, but are fail-closed forbidden from mutating
  production safety policy, exactness rules, tenant budgets, custody ownership,
  or final proof authority.
- Implements the 12-worker / 3-failure-domain / 120-slot `ReferenceFleetAllocation`
  scheduling and admission model:
  - 60 production commitment slots (50%): 24 interactive, 18 batch, 12 exact-quantum/scientific,
    6 tenant-burst, 0 default mining entitlement (`mining_default_slots=0`, `implicit_live_pool_authority=False`).
  - 48 protected recovery reserve slots (40%), never sold as idle capacity.
  - 6 isolated preemptible elevation slots (5%).
  - 6 worker-local verification/control overhead slots (5%).
  - Per failure domain (40 slots): 20 production / 16 reserve / 2 elevation / 2 local control.
  - Single-domain loss simulation: 80 surviving slots; 60 production + 4 control + 4 optional
    elevation = 68 used, leaving 12 unallocated buffer slots.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
from typing import Any, Mapping


COHORT_SCHEMA = "chronus.fleet.cohorts/v1"


class CohortKind(str, Enum):
    VERIFIER = "verifier"
    BENCHMARK = "benchmark"
    SHADOW = "shadow"
    CANARY = "canary"
    PRODUCTION = "production"


IMMUTABLE_GOVERNANCE_SURFACES = frozenset(
    {
        "production_safety_policy",
        "exactness_rules",
        "tenant_budgets",
        "custody_ownership",
        "final_proof_authority",
        "al_haras_policy",
    }
)

ALLOWED_PROPOSAL_SURFACES = frozenset(
    {
        "candidate_schedule",
        "candidate_tile_parameters",
        "candidate_kernel_variant",
        "cache_sizing_hint",
    }
)


@dataclass(frozen=True, kw_only=True)
class CohortIdentity:
    """Immutable identity for a fleet cohort."""

    cohort_kind: CohortKind
    artifact_sha256: str
    policy_id: str
    telemetry_schema: str
    can_mutate_production_custody: bool
    preemptible: bool

    def __post_init__(self) -> None:
        if len(self.artifact_sha256) != 64:
            raise ValueError("artifact_sha256 must be a 64-character hex SHA-256 digest")
        if not self.policy_id.strip():
            raise ValueError("policy_id must be non-empty")
        if not self.telemetry_schema.strip():
            raise ValueError("telemetry_schema must be non-empty")
        if self.cohort_kind in {CohortKind.VERIFIER, CohortKind.BENCHMARK, CohortKind.SHADOW}:
            if self.can_mutate_production_custody:
                raise PermissionError(
                    f"Cohort {self.cohort_kind.value!r} is strictly forbidden from mutating production custody"
                )

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["cohort_kind"] = self.cohort_kind.value
        return data


class CohortBoundaryGuard:
    """Enforces that discovery/learning proposals never alter protected governance or proof surfaces."""

    @staticmethod
    def validate_proposal(
        *,
        proposer_cohort: CohortIdentity,
        target_surface: str,
        proposed_changes: Mapping[str, Any],
    ) -> dict[str, Any]:
        if target_surface in IMMUTABLE_GOVERNANCE_SURFACES:
            raise PermissionError(
                f"Cohort {proposer_cohort.cohort_kind.value!r} attempted to mutate protected surface "
                f"{target_surface!r}; discovery/learning cannot alter safety policy, exactness rules, "
                "tenant budgets, custody ownership, or proof authority"
            )
        if target_surface not in ALLOWED_PROPOSAL_SURFACES:
            raise PermissionError(f"Unknown or unapproved proposal surface: {target_surface!r}")
        for forbidden_key in IMMUTABLE_GOVERNANCE_SURFACES:
            if forbidden_key in proposed_changes:
                raise PermissionError(
                    f"Proposal payload embeds forbidden governance key {forbidden_key!r}"
                )
        raw = json.dumps(
            {
                "cohort": proposer_cohort.as_dict(),
                "target_surface": target_surface,
                "proposed_changes": dict(proposed_changes),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return {
            "admissible_as_candidate_proposal": True,
            "auto_promoted_to_production": False,
            "requires_owner_approval_and_verifier_gate": True,
            "target_surface": target_surface,
            "proposal_digest": hashlib.sha256(raw).hexdigest(),
        }


@dataclass(frozen=True, kw_only=True)
class DomainSlotLayout:
    """Per-failure-domain normalized slot allocation."""

    domain_id: str
    worker_count: int
    slots_per_worker: int
    total_domain_slots: int
    production_slots: int
    recovery_reserve_slots: int
    elevation_preemptible_slots: int
    local_control_verification_slots: int

    def __post_init__(self) -> None:
        if self.worker_count * self.slots_per_worker != self.total_domain_slots:
            raise ValueError("worker_count * slots_per_worker must equal total_domain_slots")
        allocated = (
            self.production_slots
            + self.recovery_reserve_slots
            + self.elevation_preemptible_slots
            + self.local_control_verification_slots
        )
        if allocated != self.total_domain_slots:
            raise ValueError(f"Domain {self.domain_id} slot sum {allocated} != {self.total_domain_slots}")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, kw_only=True)
class ReferenceFleetAllocation:
    """Reference 12-worker / 3-failure-domain / 120-slot scheduling and admission model.

    Explicitly labeled as a scheduling and admission model, not a physical hardware
    inventory or availability certificate.
    """

    total_workers: int = 12
    failure_domains: int = 3
    workers_per_domain: int = 4
    slots_per_worker: int = 10
    total_modeled_slots: int = 120

    # Global slot partition (60 / 48 / 6 / 6 = 120)
    production_commitment_slots: int = 60
    protected_recovery_reserve_slots: int = 48
    isolated_elevation_slots: int = 6
    worker_local_control_slots: int = 6

    # Production commitment breakdown (24 + 18 + 12 + 6 + 0 = 60)
    interactive_slots: int = 24
    batch_slots: int = 18
    exact_quantum_scientific_slots: int = 12
    tenant_burst_slots: int = 6
    mining_default_slots: int = 0

    # Governance truth flags
    recovery_reserve_sold_as_idle: bool = False
    implicit_live_pool_authority: bool = False
    model_classification: str = "scheduling_and_admission_model"
    deployed_hardware_inventory_claimed: bool = False
    availability_certificate_claimed: bool = False

    def __post_init__(self) -> None:
        if self.total_workers != self.failure_domains * self.workers_per_domain:
            raise ValueError("total_workers must equal failure_domains * workers_per_domain")
        if self.total_modeled_slots != self.total_workers * self.slots_per_worker:
            raise ValueError("total_modeled_slots must equal total_workers * slots_per_worker")
        if (
            self.production_commitment_slots
            + self.protected_recovery_reserve_slots
            + self.isolated_elevation_slots
            + self.worker_local_control_slots
            != self.total_modeled_slots
        ):
            raise ValueError("Global slot categories must sum to total_modeled_slots (120)")
        if (
            self.interactive_slots
            + self.batch_slots
            + self.exact_quantum_scientific_slots
            + self.tenant_burst_slots
            + self.mining_default_slots
            != self.production_commitment_slots
        ):
            raise ValueError("Production class breakdown must sum to production_commitment_slots (60)")
        if self.mining_default_slots != 0 or self.implicit_live_pool_authority:
            raise ValueError("Default mining entitlement must be 0 with no implicit live-pool authority")
        if self.recovery_reserve_sold_as_idle:
            raise ValueError("Protected recovery reserve must never be sold as idle capacity")

    def domain_layouts(self) -> tuple[DomainSlotLayout, ...]:
        return tuple(
            DomainSlotLayout(
                domain_id=f"domain-{i + 1}",
                worker_count=self.workers_per_domain,
                slots_per_worker=self.slots_per_worker,
                total_domain_slots=self.workers_per_domain * self.slots_per_worker,
                production_slots=self.production_commitment_slots // self.failure_domains,
                recovery_reserve_slots=self.protected_recovery_reserve_slots // self.failure_domains,
                elevation_preemptible_slots=self.isolated_elevation_slots // self.failure_domains,
                local_control_verification_slots=self.worker_local_control_slots // self.failure_domains,
            )
            for i in range(self.failure_domains)
        )

    def simulate_domain_loss(
        self,
        *,
        lost_domains: int = 1,
        retain_optional_elevation: bool = True,
    ) -> dict[str, Any]:
        """Simulate loss of `lost_domains` failure domains and verify fail-over math."""
        if not 0 <= lost_domains < self.failure_domains:
            raise ValueError(f"lost_domains must be in [0, {self.failure_domains - 1}]")
        surviving_domains = self.failure_domains - lost_domains
        surviving_workers = surviving_domains * self.workers_per_domain
        surviving_slots = surviving_workers * self.slots_per_worker

        required_production = self.production_commitment_slots
        required_local_control = surviving_domains * (
            self.worker_local_control_slots // self.failure_domains
        )
        optional_elevation = (
            surviving_domains * (self.isolated_elevation_slots // self.failure_domains)
            if retain_optional_elevation
            else 0
        )
        used_slots = required_production + required_local_control + optional_elevation
        unallocated_slots = surviving_slots - used_slots
        production_preserved = unallocated_slots >= 0

        return {
            "lost_domains": lost_domains,
            "surviving_domains": surviving_domains,
            "surviving_workers": surviving_workers,
            "surviving_modeled_slots": surviving_slots,
            "production_slots_maintained": required_production,
            "surviving_local_control_slots": required_local_control,
            "optional_elevation_slots_active": optional_elevation,
            "total_used_slots": used_slots,
            "unallocated_headroom_slots": unallocated_slots,
            "production_commitments_fully_preserved": production_preserved,
            "elevation_preemptible_if_needed": True,
            "model_classification": self.model_classification,
            "availability_certificate_claimed": False,
        }

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["per_domain_layouts"] = [d.as_dict() for d in self.domain_layouts()]
        data["single_domain_loss_simulation"] = self.simulate_domain_loss(lost_domains=1)
        return data


def default_cohort_registry(artifact_sha256: str | None = None) -> dict[CohortKind, CohortIdentity]:
    """Build the default 5-cohort registry with immutable hashes and custody rules."""
    digest = artifact_sha256 or hashlib.sha256(b"chronus.native-quantum-fleet.release-v1").hexdigest()
    return {
        CohortKind.VERIFIER: CohortIdentity(
            cohort_kind=CohortKind.VERIFIER,
            artifact_sha256=digest,
            policy_id="chronus.policy.verifier/v1",
            telemetry_schema="chronus.telemetry.verifier/v1",
            can_mutate_production_custody=False,
            preemptible=True,
        ),
        CohortKind.BENCHMARK: CohortIdentity(
            cohort_kind=CohortKind.BENCHMARK,
            artifact_sha256=digest,
            policy_id="chronus.policy.benchmark/v1",
            telemetry_schema="chronus.telemetry.benchmark/v1",
            can_mutate_production_custody=False,
            preemptible=True,
        ),
        CohortKind.SHADOW: CohortIdentity(
            cohort_kind=CohortKind.SHADOW,
            artifact_sha256=digest,
            policy_id="chronus.policy.shadow/v1",
            telemetry_schema="chronus.telemetry.shadow/v1",
            can_mutate_production_custody=False,
            preemptible=True,
        ),
        CohortKind.CANARY: CohortIdentity(
            cohort_kind=CohortKind.CANARY,
            artifact_sha256=digest,
            policy_id="chronus.policy.canary/v1",
            telemetry_schema="chronus.telemetry.canary/v1",
            can_mutate_production_custody=True,
            preemptible=True,
        ),
        CohortKind.PRODUCTION: CohortIdentity(
            cohort_kind=CohortKind.PRODUCTION,
            artifact_sha256=digest,
            policy_id="chronus.policy.production/v1",
            telemetry_schema="chronus.telemetry.production/v1",
            can_mutate_production_custody=True,
            preemptible=False,
        ),
    }


__all__ = [
    "ALLOWED_PROPOSAL_SURFACES",
    "COHORT_SCHEMA",
    "IMMUTABLE_GOVERNANCE_SURFACES",
    "CohortBoundaryGuard",
    "CohortIdentity",
    "CohortKind",
    "DomainSlotLayout",
    "ReferenceFleetAllocation",
    "default_cohort_registry",
]
