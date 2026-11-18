"""Small independent recurrence references and scheduler boundary checks."""
import pytest

from chronus.geodesic.scheduler import (
    MAX_ACTIVE_DIM, exact_fibonacci_lucas, exact_fibonacci_lucas_mod,
    hamming_step_histogram, lucas_pisano_geodesic_order, pisano_period_pow2,
    schedule_parameters,
)

pytestmark = pytest.mark.real


def recurrence(n, modulus):
    f, g = 0, 1
    for _ in range(n):
        f, g = g % modulus, (f + g) % modulus
    return f % modulus, (2 * g - f) % modulus


@pytest.mark.parametrize('n', [0, 1, 2, 31, 257])
@pytest.mark.parametrize('modulus', [1, 2, 3, 17, 256])
def test_modular_doubling_matches_linear_recurrence(n, modulus):
    assert exact_fibonacci_lucas_mod(n, modulus) == recurrence(n, modulus)


@pytest.mark.parametrize('bad', [-1, True, False, 1.5, '2', None])
def test_fibonacci_indices_reject_invalid_values(bad):
    for function in (exact_fibonacci_lucas, lambda n: exact_fibonacci_lucas_mod(n, 17)):
        with pytest.raises(ValueError, match='non-negative integer'):
            function(bad)


@pytest.mark.parametrize('bad', [0, -1, True, False, 1.5, '2', None])
def test_modulus_must_be_positive_integer(bad):
    with pytest.raises(ValueError, match='positive integer'):
        exact_fibonacci_lucas_mod(2, bad)


@pytest.mark.parametrize('bad', [0, -1, True, 1.5, '2', None, MAX_ACTIVE_DIM + 1])
def test_schedule_dimension_validation(bad):
    with pytest.raises(ValueError, match='active_dim'):
        schedule_parameters(bad)


@pytest.mark.parametrize('bad', [-1, True, False, 1.5, '2', None])
def test_schedule_epoch_validation(bad):
    with pytest.raises(ValueError, match='epoch_step'):
        schedule_parameters(3, bad)


@pytest.mark.parametrize('dim,epoch', [(1, 0), (1, 2), (3, 1), (5, 7)])
def test_affine_order_without_gray_matches_independent_recurrence(dim, epoch):
    size = 1 << dim
    f, lucas = recurrence(3 * epoch + 1, size)
    expected = [(lucas * t + f) % size for t in range(size)]
    assert lucas_pisano_geodesic_order(dim, epoch_step=epoch, apply_gray_geodesic=False) == expected
    assert lucas_pisano_geodesic_order(dim, epoch_step=epoch) == [x ^ (x >> 1) for x in expected]


def test_max_dimension_huge_epoch_wraps_without_materialising_domain():
    period = pisano_period_pow2(MAX_ACTIVE_DIM)
    assert schedule_parameters(MAX_ACTIVE_DIM, (1 << 1000) * period + 7) == schedule_parameters(MAX_ACTIVE_DIM, 7)


@pytest.mark.parametrize('order,expected', [([], {}), ([7], {}), ([1, 1, 1], {0: 2}), ([0, 1, 7, 0], {1: 1, 2: 1, 3: 1})])
def test_hamming_histogram_counts_only_adjacent_steps(order, expected):
    assert hamming_step_histogram(order) == expected
