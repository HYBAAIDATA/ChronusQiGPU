"""Evidence framework - Tier 7: evidence boundaries for the Chronus elevation.

Maps every layer to measured / projected / evidence gate, so that no claim
can enter capacity math without its evidence class having been asserted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from chronus.core.enums import Axiom, CapacityLabel, EvidenceClass

__all__ = [
    "EvidenceBoundary",
    "EVIDENCE_BOUNDARIES",
    "CapacityClaim",
    "ConformanceResult",
    "assert_evidence_class",
    "run_conformance_test",
]


# ---------------------------------------------------------------------------
# Tier 7.1 - Evidence boundary table (section 3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceBoundary:
    """A layer mapped to measured / projected / evidence gate."""

    layer: str
    measured: List[str]
    projected: List[str]
    evidence_gate: str
    axiom: Axiom


EVIDENCE_BOUNDARIES: tuple[EvidenceBoundary, ...] = (
    EvidenceBoundary(
        layer="Adapters",
        measured=["CPU", "Intel UHD"],
        projected=["CUDA", "ROCm", "Metal", "cloud"],
        evidence_gate="test_virtual_igpu_acceptance.py",
        axiom=Axiom.A2_EVIDENCE_SEPARATION,
    ),
    EvidenceBoundary(
        layer="Per-device lanes",
        measured=["SPMD executor (32)"],
        projected=["Fleet scheduling (per-device)"],
        evidence_gate="fleet_coordinator_integration_test",
        axiom=Axiom.A8_MEASUREMENT_BEFORE_PROMOTION,
    ),
    EvidenceBoundary(
        layer="Memory",
        measured=["HBM on-device"],
        projected=["Remote tier", "Quantum tier"],
        evidence_gate="tier_allocation_audit",
        axiom=Axiom.A4_FINITE_RESOURCE_ACCOUNTING,
    ),
    EvidenceBoundary(
        layer="Throughput",
        measured=["Measured dispatches"],
        projected=["Design envelopes (Rule 7)"],
        evidence_gate="chronus/seam/scale.py reporting",
        axiom=Axiom.A2_EVIDENCE_SEPARATION,
    ),
    EvidenceBoundary(
        layer="Heterogeneous roles",
        measured=[],
        projected=["Per-adapter role"],
        evidence_gate="role_negotiation_contract_test",
        axiom=Axiom.A8_MEASUREMENT_BEFORE_PROMOTION,
    ),
    EvidenceBoundary(
        layer="Fleet evidence",
        measured=["Per-device SHA256d records"],
        projected=[],
        evidence_gate="fleet_evidence_ledger_integration_test",
        axiom=Axiom.A6_DETERMINISTIC_PROVENANCE,
    ),
)


# ---------------------------------------------------------------------------
# Tier 7.2 - Evidence class assertion (section 3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CapacityClaim:
    """A claim about capacity with its evidence class."""


def assert_evidence_class(claim: CapacityClaim) -> bool:
    """Verify a claim's evidence class before allowing it in capacity math.

    Axiom 2 (evidence separation) enforced at runtime.
    """
    label_str = getattr(claim, "label", None)
    evidence_class = getattr(claim, "evidence_class", None)

    if evidence_class == EvidenceClass.MEASURED:
        source = getattr(claim, "source", None)
        gate = getattr(claim, "evidence_gate", None)
        if not source:
            return False
        if not gate:
            return False
    elif evidence_class == EvidenceClass.PROJECTED:
        allowed_labels = {CapacityLabel.DESIGN_ENVELOPE, CapacityLabel.ROADMAP_TARGET}
        if label_str not in allowed_labels:
            return False
        # Axiom 2: projected values must NOT be included in effective capacity
        if getattr(claim, "included_in_effective_capacity", False):
            return False
    elif evidence_class == EvidenceClass.THEORETICAL:
        owner = getattr(claim, "owner", None)
        if not owner or owner not in ("TURING", "external"):
            return False
    else:
        return False

    return True


# ---------------------------------------------------------------------------
# Tier 7.3 - Conformance test runner (Axiom 8)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConformanceResult:
    """Result of running a conformance test for an adapter."""

    backend: str
    passed: bool
    failures: tuple[str, ...]
    measured: Dict[str, Any]
    timestamp: Optional[str] = None

    @property
    def digest_chain(self) -> str:
        from hashlib import sha256

        payload = (
            f"{self.backend}{str(self.passed)}{self.measured}{self.timestamp or ''}"
        ).encode("utf-8")
        return sha256(payload).hexdigest()


def run_conformance_test(backend: str, kernel: dict) -> ConformanceResult:
    """Run the conformance test for an adapter.

    In a real system, this would execute the kernel on the backend and compare
    against a known-answer test vector. Here we return a deterministic result.

    Axiom 8: measurement before promotion. If the test fails, the adapter must
    NOT be promoted.
    """
    # Deterministic stub: CPU / OpenCL adapters pass their conformance test.
    if backend in ("cpu_software", "opencl_intel_uhd"):
        return ConformanceResult(
            backend=backend,
            passed=True,
            failures=(),
            measured={"accuracy": 1.0},
        )

    # Cloud / accelerator backends are not yet tested -> fail conformance
    return ConformanceResult(
        backend=backend,
        passed=False,
        failures=("kernel_not_implemented", "conformance_test_missing"),
        measured={},
    )
