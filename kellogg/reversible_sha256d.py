#!/usr/bin/env python3
"""
reversible_sha256d — Reversible circuit accounting for SHA-256d.
Landauer applies ONLY to logically erased bits. Uncomputation returns
ancillae to |0⟩; it does NOT erase them in the Landauer sense.
"""

from __future__ import annotations
from typing import Optional


# ──────────────────────────────────────────────
# ReversibleCircuit type
# ──────────────────────────────────────────────

@dataclass
class ReversibleCircuit:
    input_bits: int
    ancillary_bits: int
    output_bits: int      # the 256-bit digest
    uncomputed_bits: int  # temporary state uncomputed
    reset_bits: int       # bits reset to known state

    # Invariants (enforced by assertions in tests):
    #   0 <= uncomputed_bits <= ancillary_bits  (ancillae can't be less than temp state)
    #   reset_bits >= 0


# ──────────────────────────────────────────────
# erased_bits — only reset bits count as Landauer erasure
# ──────────────────────────────────────────────

def erased_bits(c: ReversibleCircuit) -> int:
    """Only bits explicitly reset to a known state count as erased."""
    assert 0 <= c.uncomputed_bits <= c.ancillary_bits, \
        "uncomputed_bits must be <= ancillary_bits and >= 0"
    assert c.reset_bits >= 0
    return c.reset_bits


# ──────────────────────────────────────────────
# accounted_bits — total bits the circuit must account for
# ──────────────────────────────────────────────

def accounted_bits(c: ReversibleCircuit) -> int:
    """Total bits the circuit must account for (not all are erased)."""
    return c.input_bits + c.ancillary_bits + c.output_bits


# ──────────────────────────────────────────────
# Tests (the "test_reversible_sha256d" module)
# ──────────────────────────────────────────────

def test_uncomputed_is_not_erased():
    """uncomputation returns ancillae to |0⟩; it does not erase them."""
    c = ReversibleCircuit(
        input_bits=512, ancillary_bits=1024,
        output_bits=256, uncomputed_bits=1024,
        reset_bits=0
    )
    assert erased_bits(c) == 0, "erased_bits should be 0 when reset_bits=0"
    assert accounted_bits(c) == 1792, \
        f"Expected 1792, got {accounted_bits(c)}"
    # uncomputation returns ancillae to |0⟩; it does not erase
    # them in the Landauer sense. This is the fact the doc states.
    print("  test_uncomputed_is_not_erased PASSED")


def test_reset_is_the_only_erasure():
    """Only the reset bits (output bits reset for reuse) count as erasure."""
    c = ReversibleCircuit(
        input_bits=512, ancillary_bits=1024,
        output_bits=256, uncomputed_bits=1024,
        reset_bits=256
    )
    assert erased_bits(c) == 256, \
        f"erased_bits should be 256 (the reset bits), got {erased_bits(c)}"
    # the 256 output bits, when reset for reuse, are the erasure
    print("  test_reset_is_the_only_erasure PASSED")


# ──────────────────────────────────────────────
# Run tests if invoked directly
# ──────────────────────────────────────────────

if __name__ == "__main__":
    test_uncomputed_is_not_erased()
    test_reset_is_the_only_erasure()
    print("\nAll reversible_sha256d tests PASSED")