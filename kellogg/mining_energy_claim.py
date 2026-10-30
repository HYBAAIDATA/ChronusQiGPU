#!/usr/bin/env python3
"""
mining_energy_claim — The doc's boundary: a reversible SHA-256d core is
mathematically possible. A zero-energy MINING SYSTEM is not established
by that. Admission requires six conditions; any missing -> REFUSED.
"""

from __future__ import annotations
from typing import Optional
from dataclasses import dataclass


# ──────────────────────────────────────────────
# DeviceSpec — named physical device
# ──────────────────────────────────────────────

@dataclass
class DeviceSpec:
    name: str
    type: str  # e.g. "GPU", "ASIC", "FPGA"
    serial: Optional[str] = None


# ──────────────────────────────────────────────
# Evidence — measured operating data
# ──────────────────────────────────────────────

@dataclass
class Evidence:
    energy_per_hash: float  # Joules per SHA-256d hash, measured
    timestamp: str  # ISO format
# ──────────────────────────────────────────────
# Result types for admit_energy_claim
# ──────────────────────────────────────────────

class Decision:
    """Base class for all decision types."""
    pass


class Refused(Decision):
    """The claim is refused — fail-closed on any missing condition."""
    def __init__(self, reason: str):
        self.type = "REFUSED"
        self.reason = reason


class Evaluable(Decision):
    """The claim is evaluable against a declared device — but not admitted as zero."""
    def __init__(self, bound, note: str):
        self.type = "EVALUABLE"
        self.bound = bound  # EnergyBound
        self.note = note


class BoundOnly(Decision):
    """A symbolic bound was computed, but no device evidence to compare."""
    def __init__(self, bound, note: str):
        self.type = "BOUND_ONLY"
        self.bound = bound
        self.note = note


class Satisfies(Decision):
# ──────────────────────────────────────────────
# admit_energy_claim — the six-condition gate
# ──────────────────────────────────────────────

def admit_energy_claim(c: MiningSystemClaim) -> Decision:
    """
    Evaluate a mining energy claim against the doc's boundary.

    Six conditions must all be present for the claim to be EVALUABLE.
    If any is missing -> REFUSED (fail-closed).
    """
    # Step 1: is the reversible core proved?
    if not c.reversible_core_proved:
        return Refused("reversible core not proved")

    # Step 2: is there a declared erasure budget?
    if not c.erased_bit_count_declared:
        return Refused("no erased-bit count declared")

    # Step 3: is there a declared temperature?
    if not c.temperature_declared:
        return Refused("no declared operating temperature")

    # Step 4: compute the exact symbolic bound
    # We need erased bits count and temperature as Rational.
    # For now, construct a bound with the declared values if available.
    # If the claim doesn't carry numeric values, we can't compute a specific bound.
    # The doc says: if device + evidence are None -> BOUND_ONLY or REFUSED.

    # Step 5: is there a device implementation + measured operating evidence?
    if c.device_implementation is None:
        return Refused("no physical device implementation")
# ──────────────────────────────────────────────
# Tests (the "test_mining_energy_claim" module)
# ──────────────────────────────────────────────

def test_zero_energy_mining_system_is_refused():
    """The doc's core case: reversible core true, but missing temp/bits/device/evidence."""
    claim = MiningSystemClaim(
        reversible_core_proved=True,
        temperature_declared=False,
        erased_bit_count_declared=False,
        device_implementation=None,
        measured_operating_evidence=None,
        total_dissipation_claim="zero energy mining system",
    )
    d = admit_energy_claim(claim)
    assert d.type == "REFUSED", f"Expected REFUSED, got {d.type} with reason={d.reason}"
    assert "temperature" in d.reason.lower(), \
        f"Reason should mention temperature, got: {d.reason}"
    print("  test_zero_energy_mining_system_is_refused PASSED")


def test_actual_doc_test_cases():
    """Test the exact cases from the pseudocode specification."""

    # Test 1: zero energy claim with missing temperature
    claim1 = MiningSystemClaim(
        reversible_core_proved=True,
        temperature_declared=False,
        erased_bit_count_declared=False,
        device_implementation=None,
        measured_operating_evidence=None,
        total_dissipation_claim="zero energy mining system",
    )
    d1 = admit_energy_claim(claim1)
    assert d1.type == "REFUSED", f"Test 1: Expected REFUSED, got {d1.type}"
    assert "temperature" in d1.reason.lower(), \
        f"Test 1: Reason should mention temperature, got: {d1.reason}"

    # Test 2: ALL SIX conditions present -> EVALUABLE (not refused)
    claim2 = MiningSystemClaim(
        reversible_core_proved=True,
        temperature_declared=True,
        erased_bit_count_declared=True,
        device_implementation=DeviceSpec(name="test-gpu", type="GPU"),
        measured_operating_evidence=Evidence(
            energy_per_hash=1.0e-18, timestamp="2025-01-01", method="spec"
        ),
        total_dissipation_claim="zero wall power",
    )
    d2 = admit_energy_claim(claim2)
    # All six conditions are present -> should be EVALUABLE
    assert d2.type == "EVALUABLE", \
        f"Test 2: Expected EVALUABLE (all 6 conditions present), got {d2.type}"
    assert d2.note is not None, "EVALUABLE result should have a note"
    assert "not asserted zero" in d2.note.lower(), \
        f"Test 2: Note should say 'not asserted zero', got: {d2.note}"

    # Test 3: device=None AND evidence=None -> REFUSED
    claim3 = MiningSystemClaim(
        reversible_core_proved=True,
        temperature_declared=True,
        erased_bit_count_declared=True,
        device_implementation=None,       # <-- missing
        measured_operating_evidence=None, # <-- missing
        total_dissipation_claim="zero wall power",
    )
    d3 = admit_energy_claim(claim3)
    # Both device AND evidence are None -> should refuse
    assert d3.type == "REFUSED", f"Test 3: Expected REFUSED (missing device+evidence), got {d3.type}"
    assert "no physical device" in d3.reason or "no measured operating" in d3.reason, \
        f"Test 3: Reason should mention missing device/evidence, got: {d3.reason}"

    print("  test_actual_doc_test_cases PASSED (all 3 sub-tests)")


# ──────────────────────────────────────────────
# Run tests if invoked directly
# ──────────────────────────────────────────────

if __name__ == "__main__":
    test_zero_energy_mining_system_is_refused()
    test_actual_doc_test_cases()
    print("\nAll mining_energy_claim tests PASSED")

    if c.measured_operating_evidence is None:
        return Refused("no measured operating evidence")

    # Step 6: all six present -> the claim is EVALUABLE, not admitted as zero
    # We can now compute the bound and compare against measured evidence.
    # Since the claim may not carry erased_bits and temperature_K as numeric
    # values in this implementation, we return EVALUABLE with a note.
    from .therm_bound import make_bound, Rational
    bound = make_bound(256, Rational(300, 1))  # example bound
    note = ("evaluable against declared device; not asserted zero. "
            "Full bound computation requires erased_bits and temperature_K "
            "in the claim payload.")
    return Evaluable(bound=bound, note=note)
    """The declared device satisfies the exact Landauer bound."""
    def __init__(self, bound, measured):
        self.type = "SATISFIES"
        self.bound = bound
        self.measured = measured
    method: str  # e.g. "power-meter", " manufacturer spec"


# ──────────────────────────────────────────────
# MiningSystemClaim — the six-condition type
# ──────────────────────────────────────────────

@dataclass
class MiningSystemClaim:
    reversible_core_proved: bool
    temperature_declared: bool
    erased_bit_count_declared: bool
    device_implementation: Optional[DeviceSpec]
    measured_operating_evidence: Optional[Evidence]
    total_dissipation_claim: Optional[str]