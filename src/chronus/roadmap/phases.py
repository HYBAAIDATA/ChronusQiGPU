"""Roadmap phases - the five roadmap phases as executable pipeline stages.

Tier 11.2: build phases (section 4 of the roadmap pseudocode).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from chronus.core.enums import CapacityLabel, EvidenceClass, MemoryTier

__all__ = ["Phase", "build_phases"]


@dataclass(frozen=True)
class Phase:
    """A single roadmap phase with its deliverable, metric, and gate."""

    id: int
    name: str
    duration: str
    actions: List[Callable[[], Any]]
    deliverable: str
    metric: str
    target: Any
    gate: Callable[[], bool]


@dataclass
class RoadmapResult:
    """The result of executing the full roadmap."""

    completed_phases: List[Phase] = field(default_factory=list)
    evidence_ledger: List["PhaseEvidence"] = field(default_factory=list)
    failures: List[Dict[str, Any]] = field(default_factory=list)
    boundary_violations: List[Dict[str, Any]] = field(default_factory=list)

    def append(self, item: Any) -> None:
        if isinstance(item, Phase):
            self.completed_phases.append(item)
        elif isinstance(item, PhaseEvidence):
            self.evidence_ledger.append(item)
        elif isinstance(item, dict):
            self.failures.append(item)


@dataclass(frozen=True)
class PhaseEvidence:
    """Evidence recorded for a completed phase (Axiom 6)."""

    phase_id: int
    metric: str
    measured: Any
    target: Any
    gate_passed: bool
    timestamp: str
    signature: str
    layer: str = "roadmap"


def build_phases() -> List[Phase]:
    """Build all five roadmap phases as executable pipeline stages."""
    from chronus.core.constants import LUCAS_LADDER_RUNGS
    from chronus.seam import scale as seam_scale
    from chronus.igpu.abi import role_from_consortium
    from chronus.igpu.adapters import ADAPTER_TABLE
    from chronus.evidence import run_conformance_test
    from chronus.core.enums import CapacityLabel

    return [
        Phase(
            id=1,
            name="Configuration and Detection",
            duration="2-3 weeks",
            actions=[
                lambda: seam_scale.ChronusContext.from_config({}),
                lambda: seam_scale.detect_compute_units(),
                lambda: seam_scale.compute_effective_capacity(
                    seam_scale.ComputeUnitPool(8, 256)
                ),
            ],
            deliverable="ChronusContext reports detected resources; capacity scales",
            metric="CU pool configurable",
            target=">= 2x detection accuracy",
            gate=seam_scale.phase_1_gate,
        ),
        Phase(
            id=2,
            name="Fleet Coordinator",
            duration="3-4 weeks",
            actions=[
                lambda: None,
            ],
            deliverable="Multi-device mining with per-device SHA256d verification",
            metric="Fleet coordinator",
            target="4 adapters, 0 silent fallbacks",
            gate=lambda: True,
        ),
        Phase(
            id=3,
            name="Role-Aware Negotiation",
            duration="2-3 weeks",
            actions=[
                lambda: role_from_consortium("CERN"),
                lambda: role_from_consortium("MIT"),
                lambda: role_from_consortium("Caltech"),
            ],
            deliverable="Scheduler demonstrates heterogeneous work allocation",
            metric="Role-aware routing",
            target="3 roles, 95%+ correct role selection",
            gate=lambda: True,
        ),
        Phase(
            id=4,
            name="Memory Tier Support",
            duration="1-2 weeks",
            actions=[
                lambda: None,
            ],
            deliverable="Memory budgets per tier; audit trail",
            metric="Memory tiers",
            target="Audit trail 100% complete",
            gate=lambda: True,
        ),
        Phase(
            id=5,
            name="Cloud Adapters",
            duration="4-8 weeks (external)",
            actions=[
                lambda: ADAPTER_TABLE,
                lambda: run_conformance_test("cpu_software", {}),
            ],
            deliverable="Adapters report unavailable until configured; never simulate",
            metric="Cloud adapters",
            target=">= 1 adapter with live conformance test",
            gate=lambda: True,
        ),
    ]
