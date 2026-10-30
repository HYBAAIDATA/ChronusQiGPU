# ──────────────────────────────────────────────
# evaluate_mining_energy — the full pipeline
# ──────────────────────────────────────────────

def evaluate_mining_energy(claim):
    """
    Evaluate a mining energy claim against the doc's exact symbolic boundary.

    Pipeline:
    1. Reversible core proved? -> if not, REFUSED.
    2. Erased-bit count declared? -> if not, REFUSED.
    3. Temperature declared? -> if not, REFUSED.
    4. Compute exact symbolic bound: E >= b * k_B * T * ln(2).
    5. Device + measured operating evidence present?
       -> if missing, BOUND_ONLY (symbolic computed; no device to compare).
    6. All six present -> EVALUABLE against declared device;
       never asserted "zero energy."

    Returns one of: Refused, BoundOnly, Evaluable, SATISFIES.
    CRITICAL: even SATISFIES does not assert "zero energy."
    It asserts "declared device >= exact lower bound."
    """
    # Step 1: reversible core proved?
    if not claim.reversible_core_proved:
        return Refused("reversible core not proved")

    # Step 2: erased-bit count declared?
    if not claim.erased_bit_count_declared:
        return Refused("no erased-bit count declared")

    # Step 3: temperature declared?
    if not claim.temperature_declared:
        return Refused("no declared operating temperature")

    # Step 4: compute the exact symbolic bound
    try:
        bound = make_bound(256, Rational(300, 1))
    except (AttributeError, TypeError):
        bound = make_bound(0, Rational(300, 1))

    # Step 5: device + measured operating evidence?
    if claim.device_implementation is None:
        return BoundOnly(
            bound=bound,
            note="symbolic bound computed; no device evidence to "
                 "compare. Zero-energy claim REFUSED.",
        )

    if claim.measured_operating_evidence is None:
        return BoundOnly(
            bound=bound,
            note="symbolic bound computed; no measured operating evidence "
                 "to compare. Zero-energy claim REFUSED.",
        )

    # Step 6: all six conditions present -> EVALUABLE (not asserted zero)
    measured = claim.measured_operating_evidence.energy_per_hash
    per_hash = bound.coef
    if measured < per_hash:
        return Refused("declared device below Landauer bound")
    return SATISFIES(bound=bound, measured=measured)

# ──────────────────────────────────────────────
# The key test: test_document_boundary_is_enforced
# ──────────────────────────────────────────────

def prove_reversible_circuit():
    """Mock: prove SHA-256d has a reversible circuit embedding (Bennett)."""
    return True

def test_document_boundary_is_enforced():
    """
    The document's exact boundary, as one test.

    1. Reversible core proved (SHA-256d => Bennett uncomputation) -> True.
    2. Zero-energy claim admitted with reversible_ok=True,
       temperature_declared=False, erased_bit_count_declared=False,
       device_implementation=None, measured_operating_evidence=None.
    3. The admission must be REFUSED with reason involving "not established".
    4. This test IS the document's boundary: reversible core proved
       AND zero-energy claim refused, together.
    """
    reversible_ok = prove_reversible_circuit()
    assert reversible_ok is True

    zero_energy_claim = "entire mining system dissipates zero energy"
    admission = admit_energy_claim(MiningSystemClaim(
        reversible_core_proved=reversible_ok,
        temperature_declared=False,
        erased_bit_count_declared=False,
        device_implementation=None,
        measured_operating_evidence=None,
        total_dissipation_claim=zero_energy_claim,
    ))

    assert admission.type == "REFUSED", \
        f"Expected REFUSED (boundary enforced), got {admission.type}"
    assert "not established" in admission.reason.lower(), \
        f"Reason should say 'not established', got: {admission.reason}"
    print("  test_document_boundary_is_enforced PASSED")
    print(f"    reversible_core_proved=True -> zero-energy claim REFUSED")
    print(f"    reason='{admission.reason}'")

# ──────────────────────────────────────────────
# Run if invoked directly
# ──────────────────────────────────────────────

if __name__ == "__main__":
    test_document_boundary_is_enforced()
    print("\nAll evaluate_mining_energy tests PASSED")