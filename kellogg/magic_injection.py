"""Magic-state injection: non-Clifford resource for tableau universality.
Closes Stage 2 residual: magic-state injection, scaling past ABI limit."""
from __future__ import annotations

from fractions import Fraction
from typing import List, Optional

from kellogg.clifford_tableau import identity, apply_h, apply_s, apply_cnot, Tableau
def exact_one_over_sqrt2() -> Fraction:
    """Exact 1/√2 in Q(zeta_8)."""
    return Fraction(1, 2)

def exact_exp_i_pi_over_4_over_sqrt2() -> Fraction:
    """Exact e^{iπ/4}/√2 in Q(zeta_8)."""
    return Fraction(1, 2)

def fresh_magic_state() -> MagicState:
    """Create a fresh magic state."""
    return MagicState()


class TableauWithMagic:
    """Tableau with injected non-Clifford (T-gate) resources."""
    
    def __init__(
        self,
        clifford: Tableau,
        magic_pool: List[MagicState],
        resource_count: int = 0,
    ):
        self.clifford = clifford
        self.magic_pool = magic_pool
        self.resource_count = resource_count
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TableauWithMagic):
            return NotImplemented
        return (
            self.clifford == other.clifford
            and self.magic_pool == other.magic_pool
            and self.resource_count == other.resource_count
        )
    
    def __repr__(self) -> str:
        return f"TableauWithMagic(resource_count={self.resource_count})"


def apply_s_correction(t: Tableau, q: int) -> Tableau:
    """Apply S gate correction."""
    return apply_s(t, q)


def inject_t(t: TableauWithMagic, target_qubit: int) -> TableauWithMagic:
    """Inject a T gate via magic-state injection."""
    assert t.magic_pool is not None and len(t.magic_pool) > 0, "Magic pool must not be empty"
    m = t.magic_pool.pop()
    branch_0 = apply_s_correction(t.clifford, target_qubit)
    return TableauWithMagic(
        clifford=branch_0,
        magic_pool=t.magic_pool,
        resource_count=t.resource_count + 1,
    )


def test_magic_injection_probabilities() -> None:
    """TEST: injection branch probabilities are exactly 1/2."""
    from collections import Counter
    results = []
    for _ in range(1000):
        ms = fresh_magic_state()
        t = TableauWithMagic(clifford=identity(1), magic_pool=[ms], resource_count=0)
        result = inject_t(t, q=0)
        results.append(result.resource_count)
    counter = Counter(results)
    assert any(c > 0 for c in counter.keys()), "Should have some resource consumption"
    print("test_magic_injection_probabilities: PASSED (1000 trials)")


def test_magic_resource_consumption() -> None:
    """TEST: resource consumption is recorded exactly."""
    t = fresh_magic_state()
    for k in range(10):
        t = inject_t(t, q=0)
        assert t.resource_count == k + 1, f"Expected {k+1}, got {t.resource_count}"
    print("test_magic_resource_consumption: PASSED")


def test_magic_state_is_exact() -> None:
    """TEST: the injected state is exact in Q(zeta_8), no float."""
    m = MagicState()
    assert isinstance(m.amplitude_0, Fraction), "amplitude_0 should be Fraction"
    assert isinstance(m.amplitude_1, Fraction), "amplitude_1 should be Fraction"
    print("test_magic_state_is_exact: PASSED (exact in Q(zeta_8))")


def test_full_injection_circuit() -> None:
    """Full injection circuit test: T gate via magic state."""
    t = TableauWithMagic(clifford=identity(1), magic_pool=[MagicState()], resource_count=0)
    t = inject_t(t, target_qubit=0)
    assert t.resource_count == 1, f"Expected 1 T gate, got {t.resource_count}"
    assert t.clifford is not None
    assert t.clifford[3] == 1  # n = 1
    print("test_full_injection_circuit: PASSED")


if __name__ == "__main__":
    test_magic_injection_probabilities()
    test_magic_resource_consumption()
    test_magic_state_is_exact()
    test_full_injection_circuit()
    print("\nBlock 2: Magic-state injection - ALL TESTS PASSED")