"""Small analytic walk cases, including wraparound and interference."""
from fractions import Fraction

import pytest

from turing.exact.geometry.coined_cycle import CoinedCycleWalk
from turing.exact.geometry.hilbert import ExactComplex

pytestmark = pytest.mark.real


@pytest.mark.parametrize("positions,start", [(1, 0), (1025, 0), (True, 0), (3.0, 0), (3, -1), (3, 3), (3, True)])
def test_walk_rejects_invalid_cycle_or_start(positions, start):
    with pytest.raises(ValueError):
        CoinedCycleWalk(positions, start)


def test_first_step_has_exact_amplitudes_and_wraps():
    walk = CoinedCycleWalk(5)
    assert walk.position_distribution() == {0: Fraction(1)}
    walk.step()
    assert walk.register.amplitudes == {4: ExactComplex(1, 1), 9: ExactComplex(1, -1)}
    assert walk.scale_squared == 4
    assert walk.position_distribution() == {4: Fraction(1, 2), 1: Fraction(1, 2)}


def test_three_steps_include_hadamard_interference():
    walk = CoinedCycleWalk(8)
    for _ in range(3):
        walk.step()
    assert walk.position_distribution() == {
        5: Fraction(1, 8), 7: Fraction(3, 8),
        1: Fraction(3, 8), 3: Fraction(1, 8),
    }


@pytest.mark.parametrize("positions", [2, 3, 5, 16, 1024])
def test_walk_preserves_born_mass_and_translation(positions):
    origin, shifted = CoinedCycleWalk(positions), CoinedCycleWalk(positions, positions - 1)
    for step in range(9):
        distribution = origin.position_distribution()
        assert sum(distribution.values()) == 1
        assert all(isinstance(p, Fraction) and p >= 0 for p in distribution.values())
        assert set(distribution) <= set(range(positions))
        assert shifted.position_distribution() == {(x - 1) % positions: p for x, p in distribution.items()}
        assert origin.register.norm2() == origin.scale_squared == 2 ** (step + 1)
        origin.step()
        shifted.step()
