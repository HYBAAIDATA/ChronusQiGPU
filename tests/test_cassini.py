"""Exact coverage and boundary contracts for recovered Cassini schedules."""
import math

import pytest

from chronus.pythia.cassini import cassini_permutation, fibonacci, hendrix_stride, partition_interval

pytestmark = pytest.mark.real


@pytest.mark.parametrize("size,parts", [(0, 4), (1, 4), (10, 3), (600, 600), (601, 600)])
def test_partition_is_balanced_contiguous_and_complete(size, parts):
    intervals = partition_interval(17, size, parts)
    assert len(intervals) == parts
    assert intervals[0].start == 17
    assert intervals[-1].stop == 17 + size
    assert all(a.stop == b.start for a, b in zip(intervals, intervals[1:]))
    quotient, remainder = divmod(size, parts)
    assert [p.size for p in intervals] == [quotient + 1] * remainder + [quotient] * (parts - remainder)


@pytest.mark.parametrize("args", [(-1, 1, 2), (0, -1, 2), (0, 1, 0)])
def test_invalid_partitions_are_rejected(args):
    with pytest.raises(ValueError):
        partition_interval(*args)


@pytest.mark.parametrize("width", [1, 2, 6, 31, 600, 601])
@pytest.mark.parametrize("face", [0, 1, 31, 599])
def test_cassini_schedule_covers_each_offset_once(width, face):
    schedule = cassini_permutation(width, face, seed=-123456789)
    assert len(schedule) == width
    assert sorted(schedule) == list(range(width))
    assert math.gcd(schedule.stride, width) == 1
    assert schedule.cassini_order == face + 2
    assert schedule.cassini_determinant == (-1) ** (face + 2)
    assert schedule == cassini_permutation(width, face, seed=-123456789)
    with pytest.raises(IndexError):
        schedule.offset_at(-1)
    with pytest.raises(IndexError):
        schedule.offset_at(width)


@pytest.mark.parametrize("width,face", [(0, 0), (-1, 0), (1, -1)])
def test_invalid_cassini_inputs_are_rejected(width, face):
    with pytest.raises(ValueError):
        cassini_permutation(width, face, 0)


def test_seed_translates_origin_without_changing_stride():
    a, b = (cassini_permutation(17, 4, seed) for seed in (0, 1))
    assert a.stride == b.stride
    assert list(b) == [(x + 1) % 17 for x in a]
    assert [fibonacci(n) for n in range(8)] == [0, 1, 1, 2, 3, 5, 8, 13]


@pytest.mark.parametrize("window", [1, 2, 6, 32, 600, 65536, 2**32])
def test_hendrix_stride_uses_lucas_76_and_is_coprime(window):
    stride = hendrix_stride(window)
    assert 1 <= stride <= window
    assert math.gcd(stride, window) == 1
    previous, current = 2, 1
    for _ in range(1, 76):
        previous, current = current, previous + current
    expected = current % window or 1
    while math.gcd(expected, window) != 1:
        expected = (expected + 1) % window or 1
    assert stride == expected


@pytest.mark.parametrize("window", [0, -1, True, 1.0, "2"])
def test_hendrix_requires_positive_exact_integer(window):
    with pytest.raises(ValueError):
        hendrix_stride(window)
