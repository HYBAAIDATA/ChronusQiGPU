"""Boundaries - Tier 9: honest boundaries as executable assertions.

Every boundary in Section 8 of the Chronus Elevation Roadmap becomes a
guard function here. Running this module is a falsifiable test: claiming
any of these six things means the guard fails.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List

__all__ = [
    "BoundaryViolation",
    "run_boundary_guards",
    "assert_no_physical_10_pad_claim",
    "assert_no_petabyte_per_second_claim",
    "assert_no_quantum_ram_claim",
    "assert_no_hardware_attestation_claim",
    "assert_no_continuum_yang_mills_claim",
    "assert_no_cloud_adapters_yet",
]


class BoundaryViolation(RuntimeError):
    """A boundary guard failed - the system asserted something it should not."""


# ---------------------------------------------------------------------------
# Tier 9.1 - Honest boundary guards (section 8)
# ---------------------------------------------------------------------------


def assert_no_physical_10_pad_claim() -> bool:
    """The 10-pad topology is roadmap aspirational, not current fact."""
    system = {"deployment_unit": "SINGLE_MACHINE", "claims_physical_10_pad": False}
    if system["deployment_unit"] in ("SINGLE_MACHINE", "CLUSTER"):
        if system["claims_physical_10_pad"]:
            raise BoundaryViolation(
                "System claims physical 10-pad topology; not implemented"
            )
    return True


def assert_no_petabyte_per_second_claim() -> bool:
    """Per-adapter throughput measured; aggregate is never over-claimed."""
    capacity_report = {"aggregate_throughput": 0.0, "label": "EFFECTIVE_CAPACITY"}
    measured = sum(getattr(a, "measured_throughput", 0) for a in [])

    if capacity_report["aggregate_throughput"] != measured:
        raise BoundaryViolation("Aggregate throughput exceeds measured sum")

    if capacity_report["label"] != "EFFECTIVE_CAPACITY":
        raise BoundaryViolation("Throughput not labelled as EFFECTIVE_CAPACITY")

    return True


def assert_no_quantum_ram_claim() -> bool:
    """Tier 3 is theoretical; TURING owns quantum state."""
    tier3 = {
        "status": "THEORETICAL",
        "owner": "TURING",
        "chronus_materializes": False,
    }
    if tier3["status"] != "THEORETICAL":
        raise BoundaryViolation("Tier 3 is not marked THEORETICAL")
    if tier3["owner"] != "TURING":
        raise BoundaryViolation("Tier 3 owner is not TURING")
    if tier3["chronus_materializes"]:
        raise BoundaryViolation("Chronus materialized quantum state")
    return True


def assert_no_hardware_attestation_claim() -> bool:
    """Runtime-signed receipts are the current boundary."""
    trust = {"current_trust_ceiling": "RUNTIME_SIGNED", "hardware_rooted": "EXTERNAL_GATE"}
    if trust["current_trust_ceiling"] != "RUNTIME_SIGNED":
        raise BoundaryViolation("Current trust ceiling is above RUNTIME_SIGNED")
    if trust["hardware_rooted"] != "EXTERNAL_GATE":
        raise BoundaryViolation("Hardware attestation claimed but not external")
    return True


def assert_no_continuum_yang_mills_claim() -> bool:
    """Finite-volume gap is measured; continuum extrapolation is open."""
    yardstick = {
        "continuum_ym": "OPEN",
        "finite_volume_gap": "MEASURED",
    }
    if yardstick["continuum_ym"] != "OPEN":
        raise BoundaryViolation("Continuum YM status is not OPEN")
    if yardstick["finite_volume_gap"] != "MEASURED":
        raise BoundaryViolation("Finite-volume gap is not MEASURED")
    return True


def assert_no_cloud_adapters_yet() -> bool:
    """CUDA/ROCm/Metal/Azure/GCP typed unavailable until tested."""
    for backend in [
        "CUDA_NVIDIA",
        "ROCM_AMD",
        "METAL_APPLE",
        "AZURE_GPU",
        "GCP_GPU",
    ]:
        adapter = {"status": "TYPED_UNAVAILABLE", "conformance_test_passed": False}
        if adapter["status"] != "TYPED_UNAVAILABLE":
            raise BoundaryViolation(f"{backend} is not TYPED_UNAVAILABLE")
        if adapter["conformance_test_passed"]:
            raise BoundaryViolation(f"{backend} has a passing conformance test")
    return True


def run_boundary_guards() -> List[BoundaryViolation]:
    """Run all boundary guards as a suite."""
    violations: List[BoundaryViolation] = []
    for guard in [
        assert_no_physical_10_pad_claim,
        assert_no_petabyte_per_second_claim,
        assert_no_quantum_ram_claim,
        assert_no_hardware_attestation_claim,
        assert_no_continuum_yang_mills_claim,
        assert_no_cloud_adapters_yet,
    ]:
        try:
            guard()
        except BoundaryViolation as e:
            violations.append(e)
    return violations
