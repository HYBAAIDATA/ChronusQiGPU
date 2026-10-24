"""
Test suite for the Golden Quantum Framework runtime modules.
Run with: python tests/test_runtime.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from golden_quantum.runtime.integrity import is_valid_mphi_matrix, recover_exponent, matrix_power
from golden_quantum.runtime.folds import fold_pair, unfold_pair, fold_array, unfold_array, fold_roundtrip
from golden_quantum.runtime.lifting import lift, unlift, lift_roundtrip
from golden_quantum.runtime.pisot import (
    pisot_phi, pisot_3, iterations_for_precision, verify_threshold, convergence_ratio,
)
from golden_quantum.runtime.delta_for import compress, decompress, compression_ratio, delta_encode, delta_decode
from golden_quantum.sequences import fibonacci


def test_integrity_valid_matrices():
    for n in range(100):
        m = matrix_power(n)
        assert is_valid_mphi_matrix(m), f"Q^{n} should be valid"


def test_integrity_invalid_matrices():
    invalids = [
        [[1, 2], [3, 4]],
        [[2, 1], [1, 2]],
        [[3, 1], [1, 2]],
        [[1, 1], [0, 1]],
        [[-1, 1], [1, 0]],
        [[0, 0], [0, 0]],
    ]
    for m in invalids:
        assert not is_valid_mphi_matrix(m), f"{m} should be invalid"


def test_integrity_valid_edge_cases():
    assert is_valid_mphi_matrix([[1, 1], [1, 0]])   # Q^1
    assert is_valid_mphi_matrix([[2, 1], [1, 1]])   # Q^2
    assert is_valid_mphi_matrix([[1, 0], [0, 1]])   # Q^0 = I


def test_exponent_recovery():
    for n in range(100):
        m = matrix_power(n)
        assert recover_exponent(m) == n, f"Failed to recover n={n}"


def test_fold_pair_roundtrip():
    test_cases = [(0, 0), (1, 0), (0, 1), (5, 3), (-1, 1), (-5, -3), (100, -50), (10**6, 10**6)]
    for x, y in test_cases:
        u, v = fold_pair(x, y)
        x2, y2 = unfold_pair(u, v)
        assert (x2, y2) == (x, y), f"Roundtrip failed for ({x}, {y})"


def test_fold_array_roundtrip():
    import random
    random.seed(42)
    arrays = [
        [],
        [42],
        [1, 2, 3, 4],
        list(range(100)),
        [random.randint(-10000, 10000) for _ in range(500)],
        list(range(-100, 100)),
    ]
    for arr in arrays:
        assert fold_roundtrip(arr), f"Array roundtrip failed for length {len(arr)}"


def test_fold_injective():
    seen = set()
    for x in range(-10, 11):
        for y in range(-10, 11):
            u, v = fold_pair(x, y)
            assert (u, v) not in seen, f"Collision at ({x}, {y})"
            seen.add((u, v))


def test_lifting_roundtrip():
    import random
    random.seed(123)
    test_cases = [(0, 0), (1, 0), (0, 1), (1, 1), (-1, -1),
                  (100, 200), (-500, 300), (42, -17)]
    for _ in range(100):
        test_cases.append((random.randint(-10000, 10000), random.randint(-10000, 10000)))
    for x, y in test_cases:
        assert lift_roundtrip(x, y), f"Lift roundtrip failed for ({x}, {y})"


def test_lifting_rejects_floats():
    try:
        lift(1.5, 2.0)
        assert False, "Should have raised TypeError"
    except TypeError:
        pass


def test_pisot_phi_conjugate():
    _, conj, _ = pisot_phi()
    assert abs(conj) < 1


def test_pisot_3_conjugate():
    root, conj, _ = pisot_3()
    assert root > 1
    assert abs(conj) < 1


def test_pisot_phi_threshold():
    _, conj, _ = pisot_phi()
    from decimal import Decimal
    n = iterations_for_precision(abs(conj), Decimal("1e-6"))
    assert n == 29, f"Expected 29, got {n}"
    assert verify_threshold(abs(conj), n, Decimal("1e-6"))


def test_pisot_3_threshold():
    _, conj, _ = pisot_3()
    from decimal import Decimal
    n = iterations_for_precision(abs(conj), Decimal("1e-6"))
    assert n == 12, f"Expected 12, got {n}"
    assert verify_threshold(abs(conj), n, Decimal("1e-6"))


def test_compression_empty():
    assert decompress(compress([])) == []


def test_compression_single():
    assert decompress(compress([42])) == [42]


def test_compression_sorted():
    data = list(range(1000))
    assert decompress(compress(data)) == data


def test_compression_negative():
    data = list(range(-500, 500))
    assert decompress(compress(data)) == data


def test_compression_random():
    import random
    random.seed(789)
    data = [random.randint(-100000, 100000) for _ in range(2000)]
    assert decompress(compress(data)) == data


def test_compression_multi_block():
    data = list(range(0, 10000, 3))
    assert decompress(compress(data, block_size=512)) == data


def test_compression_ratio_sorted_better():
    import random
    random.seed(42)
    sorted_ratio = compression_ratio(list(range(10000)))
    random_ratio = compression_ratio([random.randint(0, 10**6) for _ in range(10000)])
    assert sorted_ratio > random_ratio


def test_delta_roundtrip():
    import random
    random.seed(111)
    data = [random.randint(0, 1000) for _ in range(100)]
    deltas = delta_encode(data)
    assert delta_decode(deltas) == data


def test_compression_non_monotonic():
    data = [100, 50, 75, 25, 200, 10, 150]
    assert decompress(compress(data)) == data


def test_memory_buggy_underflow():
    """The original gap² bug allows gap=5, size=10 with negative offset."""
    from golden_quantum.runtime.memory import allocate_buggy
    accepted, offset = allocate_buggy(5, 10)
    assert accepted, "Buggy code should accept gap=5, size=10"
    assert offset < 0, f"Buggy offset should be negative, got {offset}"


def test_memory_correct_rejects_underflow():
    """The corrected gap >= size invariant rejects the underflow case."""
    from golden_quantum.runtime.memory import allocate_correct
    accepted, offset = allocate_correct(5, 10)
    assert not accepted, "Correct code should reject gap=5, size=10"


def test_memory_correct_accepts_valid():
    """Valid allocations are accepted with non-negative offset."""
    from golden_quantum.runtime.memory import allocate_correct
    accepted, offset = allocate_correct(13, 8)
    assert accepted and offset == 5


def test_memory_property_non_negative_offset():
    """All accepted allocations must have non-negative offset."""
    import random
    from golden_quantum.runtime.memory import allocate_correct
    random.seed(321)
    for _ in range(1000):
        gap = random.randint(1, 500)
        size = random.randint(1, 500)
        accepted, offset = allocate_correct(gap, size)
        if accepted:
            assert offset >= 0, f"Negative offset for gap={gap}, size={size}"
        else:
            assert gap < size, f"Should have accepted gap={gap}, size={size}"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  [PASS] {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {test.__name__}: {e}")
            failed += 1
    print(f"\n{passed}/{passed + failed} tests passed")
    sys.exit(0 if failed == 0 else 1)
