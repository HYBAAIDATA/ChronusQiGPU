"""Golden Quantum integration tests for the Turing VQC core."""

from decimal import Decimal

import pytest

import turing_universal_quantum_computer as tqc
from turing_universal_quantum_computer.capabilities import audit_claims
from turing_universal_quantum_computer.golden_quantum import (
    EvidenceLayer,
    GoldenQuantumCore,
    UniversalConstantInterface,
)


def test_uci_overrides_are_simulation_only_and_reference_is_immutable():
    uci = UniversalConstantInterface()
    original_c = uci.reference["c"]
    context = uci.context(c="1.5", alpha="0.01")

    assert context.values["c"] == Decimal("1.5")
    assert context.overrides["alpha"] == Decimal("0.01")
    assert context.physical_constants_mutated is False
    assert uci.reference["c"] == original_c
    with pytest.raises(TypeError):
        uci.reference["c"] = Decimal(1)


def test_prime_gap_addressing_reports_finite_physical_allocation():
    core = GoldenQuantumCore(prime_count=64)
    address = core.memory.address(10**12)
    report = core.memory.report()

    assert address.left_prime < address.right_prime
    assert address.gap == address.right_prime - address.left_prime
    assert 0 <= address.offset < address.gap
    assert report["allocated_prime_count"] == 64
    assert report["physical_bytes"] == 512
    assert report["infinite_memory_claim"] is False


def test_recursive_golden_fold_is_exact_and_integrity_checked():
    core = GoldenQuantumCore()
    payload = bytes(range(256)) * 3
    artifact = core.fold(payload, depth=8)

    assert core.unfold(artifact) == payload
    assert artifact.evidence_layer is EvidenceLayer.VERIFIED
    assert artifact.truth_class == "exact_reversible_transform"


def test_golden_mandelbrot_order_is_a_complete_attested_permutation():
    core = GoldenQuantumCore()
    candidates, attestation = core.order_search(4096, 257, mandelbrot_prefix=64)

    assert len(candidates) == 257
    assert set(candidates) == set(range(4096, 4096 + 257))
    assert attestation.complete_permutation is True
    assert attestation.evidence_layer is EvidenceLayer.EXPERIMENTAL
    assert attestation.advantage_claimed is False
    assert attestation.foundation_digest == core.foundation.digest
    assert core.verify_attestation(attestation)


def test_phase_report_separates_verified_experimental_and_speculative_claims():
    report = GoldenQuantumCore().phase_report()
    layers = {phase["evidence_layer"] for phase in report["phases"]}

    assert EvidenceLayer.VERIFIED.value in layers
    assert EvidenceLayer.EXPERIMENTAL.value in layers
    assert report["advantage_claimed"] is False
    assert "physical-constant mutation" in report["speculative_non_executable"]


def test_profile_is_integrated_into_the_virtual_computer_core():
    machine = tqc.TenThousandQubitSystem(16)
    core = machine.golden_quantum()

    assert core.system is machine
    status = machine.status()
    assert "golden_quantum_profile" in status["capabilities"]
    assert status["unified_theory"]["verified"] is True
    assert status["unified_theory"]["digest"] == core.foundation.digest
    assert tqc.GoldenQuantumCore is GoldenQuantumCore


def test_claim_audit_rejects_unqualified_speculative_physics_claims():
    text = (
        "The engine provides infinite memory with zero physical memory allocation, "
        "mutating physical constants to manifest results with zero-latency communication."
    )
    reasons = {violation.reason for violation in audit_claims(text)}

    assert len(reasons) == 4


def test_turing_foundation_is_standalone_from_operational_packages():
    import ast
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[1]
        / "turing_universal_quantum_computer"
        / "unified_theory.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not any(name.startswith(("toe", "Intelligence", "chronus")) for name in imports)
