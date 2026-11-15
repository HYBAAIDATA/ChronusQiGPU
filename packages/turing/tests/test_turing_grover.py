import sys
from fractions import Fraction
from math import isqrt
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1] / "src")
if sys.path[:1] != [_SRC]:
    sys.path.insert(0, _SRC)

from turing.algorithms import grover  # noqa: E402
from turing.algorithms.oracles import BooleanOracle  # noqa: E402


def _marked_set(num_items, num_marked):
    order = sorted(range(num_items), key=lambda x: ((5 * x + 3) % (num_items + 1), x))
    return set(order[:num_marked])


def test_folded_equals_unfolded_for_every_n_up_to_32_and_every_m():
    for num_items in range(1, 33):
        for num_marked in range(num_items + 1):
            marked = _marked_set(num_items, num_marked)
            for k in range(isqrt(num_items) + 2):
                folded = grover.folded_grover(num_items, num_marked, k)
                unfolded = grover.unfolded_grover(num_items, marked, k)
                for x, amplitude in enumerate(unfolded):
                    expected = folded.marked_amplitude if x in marked else folded.unmarked_amplitude
                    assert amplitude == expected
                assert folded.success_probability + folded.failure_probability == 1
                assert sum(a * a for a in unfolded) == num_items


def test_optimal_iterations_maximise_the_exact_success_probability():
    for num_items in (2, 3, 4, 5, 8, 13, 16, 31, 32, 64, 100):
        for num_marked in range(1, num_items + 1):
            best = grover.optimal_iterations(num_items, num_marked)
            probabilities = [grover.success_probability(num_items, num_marked, k)
                             for k in range(isqrt(num_items) + 2)]
            assert probabilities[best] == max(probabilities)
            assert all(p < probabilities[best] for p in probabilities[:best])
    assert grover.optimal_iterations(7, 0) == 0


def test_four_items_one_marked_needs_one_iteration_with_certainty():
    state = grover.folded_grover(4, 1, 1)
    assert state.success_probability == 1
    assert grover.optimal_iterations(4, 1) == 1


def test_one_marked_item_among_256():
    marked_item = 137
    result = grover.search(BooleanOracle.from_marked(256, [marked_item]))
    assert result.marked == (marked_item,)
    assert result.num_items == 256
    assert result.iterations == 12
    assert isinstance(result.success_probability, Fraction)
    assert result.success_probability == result.item_probability
    assert 1 - Fraction(1, 256) < result.success_probability < 1
    unfolded = grover.unfolded_grover(256, [marked_item], result.iterations)
    assert unfolded[marked_item] ** 2 / 256 == result.success_probability
    assert sum(a * a for a in unfolded) == 256
    neighbours = [grover.success_probability(256, 1, k) for k in (11, 13)]
    assert all(p < result.success_probability for p in neighbours)


def test_search_without_marked_items_reports_zero_probability():
    result = grover.search(BooleanOracle.from_list([0] * 16))
    assert result.marked == () and result.iterations == 0 and result.success_probability == 0


def test_invalid_counts_are_rejected():
    for args in ((0, 0, 0), (4, 5, 0), (4, 1, -1)):
        try:
            grover.folded_grover(*args)
        except ValueError:
            pass
        else:
            raise AssertionError(f"folded_grover{args} must fail")
    try:
        grover.unfolded_grover(4, [4], 1)
    except ValueError:
        pass
    else:
        raise AssertionError("marked item outside the domain must fail")
