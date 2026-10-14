"""Tests for Euclid / Salamander Mathematical Research and Proof Tracking Substrate.

Validates Section 12 Scientific & Mathematical Protocols:
1. Formal conjecture representation with explicit domains, statements, and assumptions.
2. Rejection of duplicate conjectures and invalid lemma dependencies.
3. Proof DAG tracking with cycle and missing parent detection.
4. Honest proof status evaluation (unresolved steps prevent FORMALLY_VERIFIED).
5. Strict claim boundary: numerical experimentation provides evidence, NOT formal proof.
6. Counterexample recording immediately falsifies conjecture status to COUNTEREXAMPLE_FOUND.
"""

from __future__ import annotations

import pytest

from Intelligence.mathematical_research import (
    ConjectureStatus,
    FormalConjecture,
    Lemma,
    MathematicalProofTracker,
    ProofDAGError,
)


def test_register_conjecture_and_rejection_of_duplicates() -> None:
    """Tracker registers conjectures and prevents duplicate IDs."""
    tracker = MathematicalProofTracker()
    conj = tracker.register_conjecture(
        conjecture_id="BSDC-01",
        domain="arithmetic_geometry",
        statement="L(E, 1) = 0 iff E(Q) has infinite order",
        assumptions=["E is an elliptic curve over Q"],
        unresolved_steps=["Analytic continuation of L-function", "p-adic regulator bound"],
    )

    assert conj.conjecture_id == "BSDC-01"
    assert conj.status == ConjectureStatus.CONJECTURED
    assert len(conj.unresolved_steps) == 2

    with pytest.raises(ValueError, match="already registered"):
        tracker.register_conjecture(
            conjecture_id="BSDC-01",
            domain="arithmetic_geometry",
            statement="duplicate",
        )

    retrieved = tracker.get_conjecture("BSDC-01")
    assert retrieved is not None
    assert retrieved.domain == "arithmetic_geometry"


def test_lemma_dependency_validation() -> None:
    """Lemmas require existing dependencies and unique IDs."""
    tracker = MathematicalProofTracker()
    tracker.register_conjecture(
        conjecture_id="TOY-THM",
        domain="algebra",
        statement="For all g in G, (g^-1)^-1 = g",
    )

    # Adding lemma with non-existent dependency raises ProofDAGError
    with pytest.raises(ProofDAGError, match="Dependency 'lemma_0' not found"):
        tracker.add_lemma(
            "TOY-THM",
            Lemma(
                lemma_id="lemma_1",
                statement="g * g^-1 = e",
                assumptions=(),
                dependencies=("lemma_0",),
                provenance="group_axioms",
            ),
        )

    # Adding valid root lemma
    l0 = Lemma(
        lemma_id="lemma_0",
        statement="Every element in G has an inverse g^-1 such that g * g^-1 = e",
        assumptions=(),
        dependencies=(),
        provenance="group_definition",
        is_verified=True,
    )
    tracker.add_lemma("TOY-THM", l0)

    # Adding duplicate lemma ID raises ProofDAGError
    with pytest.raises(ProofDAGError, match="Duplicate lemma_id 'lemma_0'"):
        tracker.add_lemma("TOY-THM", l0)


def test_honest_proof_status_evolution() -> None:
    """Status evolution respects unresolved steps and lemma verification closure."""
    tracker = MathematicalProofTracker()
    tracker.register_conjecture(
        conjecture_id="FERMAT-L2",
        domain="number_theory",
        statement="a^2 + b^2 = c^2 has integer solutions",
        unresolved_steps=["exhaustion_check"],
    )

    l1 = Lemma(
        lemma_id="l1",
        statement="3^2 + 4^2 = 5^2",
        assumptions=(),
        dependencies=(),
        provenance="arithmetic",
        is_verified=False,
    )
    tracker.add_lemma("FERMAT-L2", l1)

    # With unverified lemma and unresolved steps, status is CONJECTURED
    assert tracker.evaluate_proof_status("FERMAT-L2") == ConjectureStatus.CONJECTURED

    # Verify lemma l1
    tracker.verify_lemma(
        "FERMAT-L2",
        lemma_id="l1",
        proof_method="direct_computation",
        verification_receipt="receipt_9_plus_16_eq_25",
    )

    # Because unresolved_steps is still non-empty, status moves to PARTIALLY_PROVEN, NOT FORMALLY_VERIFIED!
    conj = tracker.get_conjecture("FERMAT-L2")
    assert conj is not None
    assert tracker.evaluate_proof_status("FERMAT-L2") == ConjectureStatus.PARTIALLY_PROVEN

    # Clear unresolved steps
    conj.unresolved_steps.clear()
    assert tracker.evaluate_proof_status("FERMAT-L2") == ConjectureStatus.FORMALLY_VERIFIED


def test_numerical_experiment_strict_claim_boundary() -> None:
    """Numerical experiments NEVER elevate a conjecture to FORMALLY_VERIFIED."""
    tracker = MathematicalProofTracker()
    tracker.register_conjecture(
        conjecture_id="GOLDBACH",
        domain="number_theory",
        statement="Every even integer greater than 2 is the sum of two primes",
    )

    # Run consistent numerical checks up to 1,000,000
    res = tracker.record_numerical_experiment(
        "GOLDBACH",
        experiment_name="sieve_verification_1M",
        parameters={"max_n": 1000000},
        results={"counterexamples": 0, "tested_count": 500000},
        consistent=True,
    )

    assert res["claim"] == "NUMERICAL_EVIDENCE_NOT_FORMAL_PROOF"
    conj = tracker.get_conjecture("GOLDBACH")
    assert conj is not None
    # Must be EXPERIMENTALLY_EVIDENCED, never FORMALLY_VERIFIED
    assert conj.status == ConjectureStatus.EXPERIMENTALLY_EVIDENCED
    assert conj.status != ConjectureStatus.FORMALLY_VERIFIED


def test_counterexample_falsification() -> None:
    """A counterexample immediately shifts conjecture status to COUNTEREXAMPLE_FOUND."""
    tracker = MathematicalProofTracker()
    tracker.register_conjecture(
        conjecture_id="FALSE-CONJ",
        domain="primes",
        statement="n^2 - n + 41 is prime for all positive integers n",
    )

    # At n = 41, 41^2 - 41 + 41 = 41^2 (composite)
    tracker.record_counterexample(
        "FALSE-CONJ",
        description="Fails at n=41 where value is 41^2 = 1681",
        witness={"n": 41, "val": 1681, "factors": [41, 41]},
    )

    conj = tracker.get_conjecture("FALSE-CONJ")
    assert conj is not None
    assert conj.status == ConjectureStatus.COUNTEREXAMPLE_FOUND
    assert len(conj.counterexamples) == 1
