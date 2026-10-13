"""
Test suite for the Golden Quantum Framework.
Run with: python -m pytest tests/ -v
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from golden_quantum.sequences import fibonacci, lucas, fib_pair, binet_f, binet_l
from golden_quantum.coding import zeckendorf, fib_encode, fib_decode, is_valid_fib_code
from golden_quantum.matrices import matrix_power, matrix_det, matrix_trace, matrix_mult
from golden_quantum.constants import PHI_D, PSI_D, PHI_F


def test_fibonacci_basic():
    assert fibonacci(0) == 0
    assert fibonacci(1) == 1
    assert fibonacci(2) == 1
    assert fibonacci(10) == 55
    assert fibonacci(20) == 6765


def test_lucas_basic():
    assert lucas(0) == 2
    assert lucas(1) == 1
    assert lucas(2) == 3
    assert lucas(10) == 123


def test_fibonacci_recurrence():
    for n in range(2, 1000):
        assert fibonacci(n + 1) == fibonacci(n) + fibonacci(n - 1)


def test_lucas_recurrence():
    for n in range(2, 1000):
        assert lucas(n + 1) == lucas(n) + lucas(n - 1)


def test_binet_exactness():
    for n in [0, 1, 5, 10, 50, 100, 500, 1000]:
        assert binet_f(n) == fibonacci(n)
        assert binet_l(n) == lucas(n)


def test_cassini_identity():
    for n in range(1, 500):
        lhs = fibonacci(n - 1) * fibonacci(n + 1) - fibonacci(n) ** 2
        assert lhs == (-1) ** n


def test_zeckendorf_sum():
    for n in range(1, 1001):
        indices = zeckendorf(n)
        total = sum(fibonacci(k) for k in indices)
        assert total == n


def test_zeckendorf_nonconsecutive():
    for n in range(1, 1001):
        indices = zeckendorf(n)
        for i in range(len(indices) - 1):
            assert indices[i] - indices[i + 1] >= 2


def test_fib_coding_roundtrip():
    for n in range(1, 1001):
        code = fib_encode(n)
        assert fib_decode(code) == n


def test_fib_code_ends_with_11():
    for n in range(1, 1001):
        assert fib_encode(n).endswith("11")


def test_invalid_fib_codes():
    invalid = ["", "1", "0", "01", "0000"]
    for code in invalid:
        assert not is_valid_fib_code(code)


def test_matrix_power():
    Q = [[1, 1], [1, 0]]
    Q2 = matrix_mult(Q, Q)
    assert Q2 == [[2, 1], [1, 1]]
    assert matrix_power(2) == [[2, 1], [1, 1]]


def test_matrix_det_cassini():
    for n in range(50):
        assert matrix_det(matrix_power(n)) == (-1) ** n


def test_matrix_trace_lucas():
    for n in range(50):
        assert matrix_trace(matrix_power(n)) == lucas(n)


def test_phi_psi_properties():
    from decimal import Decimal as D
    tol = D("1e-100")
    assert abs(PHI_D + PSI_D - 1) < tol
    assert abs(PHI_D * PSI_D + 1) < tol
    assert abs(PHI_D ** 2 - PHI_D - 1) < tol


def test_fast_doubling():
    for n in range(1000):
        fn, fn1 = fib_pair(n)
        assert fn == fibonacci(n)
        assert fn1 == fibonacci(n + 1)


def test_large_fibonacci():
    """F(10000) should have 2090 digits."""
    f = fibonacci(10000)
    assert len(str(f)) == 2090


def test_large_lucas():
    """L(1000) should be computable and match Binet."""
    assert lucas(1000) == binet_l(1000)


def test_run_all_default():
    """run_all() should complete with all theorems/invariants passing."""
    from golden_quantum.runner import run_all
    r = run_all(max_n=500)
    assert r.total > 0
    assert r.all_passed
    assert r.failed_count == 0


def test_json_output():
    """JSON output should be valid JSON with expected structure."""
    import json
    from golden_quantum.runner import run_all, format_json
    r = run_all(max_n=500)
    json_str = format_json(r)
    data = json.loads(json_str)
    assert "summary" in data
    assert "families" in data
    assert data["summary"]["total"] > 0
    assert data["summary"]["all_theorems_invariants_passed"] is True


if __name__ == "__main__":
    # Run without pytest
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
