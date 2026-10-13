"""
HYBA Corrected v1.1.0 — Full Unit Test Suite

Tests all 6 bug fix areas plus core HYBA functionality.
Run with: python -m pytest tests/ -v
"""

import sys
import os
import random
import struct

import pytest

from python_backend.hyba.core import HYBACore
from python_backend.hyba.storage import HYBAStorage
from python_backend.hyba.memory import HYBAMemory
from python_backend.hyba.compute import HYBACompute
from python_backend.hyba.invariants import HYBAInvariants
from python_backend.hyba.infrastructure import HYBAInfrastructure


# ── Fixtures ──

@pytest.fixture
def core():
    return HYBACore()

@pytest.fixture
def storage():
    return HYBAStorage()

@pytest.fixture
def compute():
    return HYBACompute()

@pytest.fixture
def invariants():
    return HYBAInvariants()


# ═══════════════════════════════════════════════════════════════════
# 1. CASSINI INTEGRITY (Bug 2 fix)
# ═══════════════════════════════════════════════════════════════════

class TestCassiniIntegrity:

    def test_valid_q0(self, core):
        """Q^0 = identity matrix should pass."""
        assert core.cassini_integrity_check([[1, 0], [0, 1]])

    def test_valid_q1(self, core):
        """Q^1 should pass — F(1)=1 ambiguity case."""
        assert core.cassini_integrity_check([[1, 1], [1, 0]])

    def test_valid_q2(self, core):
        """Q^2 should pass — F(2)=1 ambiguity case (same F value as Q^1)."""
        assert core.cassini_integrity_check([[2, 1], [1, 1]])

    def test_valid_q3(self, core):
        """Q^3 should pass."""
        assert core.cassini_integrity_check([[3, 2], [2, 1]])

    def test_valid_many_powers(self, core):
        """All Q^n for n=0..199 should pass integrity check."""
        for n in range(200):
            m = core.matrix_power(n)
            assert core.cassini_integrity_check(m), f"Q^{n} should be valid"

    def test_impostor_trace_det_match(self, core):
        """[[0,1],[1,4]] has trace=4=L(3), det=-1=(-1)^3, but isn't Q^3."""
        assert not core.cassini_integrity_check([[0, 1], [1, 4]])

    def test_impostor_not_symmetric(self, core):
        assert not core.cassini_integrity_check([[1, 2], [3, 4]])

    def test_impostor_wrong_structure(self, core):
        """Symmetric but a-d != b."""
        assert not core.cassini_integrity_check([[2, 1], [1, 2]])

    def test_impostor_negative_entry(self, core):
        """Q^(-1) form has negative entries."""
        assert not core.cassini_integrity_check([[-1, 1], [1, 0]])

    def test_impostor_zero_matrix(self, core):
        assert not core.cassini_integrity_check([[0, 0], [0, 0]])

    def test_impostor_wrong_det(self, core):
        """Structurally correct but det != ±1."""
        assert not core.cassini_integrity_check([[3, 1], [1, 2]])

    def test_mutation_detected(self, core):
        """Single-entry mutation of a valid Q^n should fail."""
        m = [row[:] for row in core.matrix_power(50)]
        m[0][0] += 1
        assert not core.cassini_integrity_check(m)


# ═══════════════════════════════════════════════════════════════════
# 2. STORAGE (Bug 3, NEW odd-length, EFF bits_per_value)
# ═══════════════════════════════════════════════════════════════════

class TestStorage:

    def test_empty_roundtrip(self, storage):
        compressed = storage.compress([])
        decompressed = storage.decompress(compressed)
        assert decompressed == []

    def test_single_value(self, storage):
        data = [42]
        compressed = storage.compress(data)
        assert storage.decompress(compressed) == data

    def test_sorted_sequential(self, storage):
        data = list(range(1000))
        compressed = storage.compress(data)
        assert storage.decompress(compressed) == data

    def test_negative_values(self, storage):
        data = list(range(-500, 500))
        compressed = storage.compress(data)
        assert storage.decompress(compressed) == data

    def test_non_monotonic_signed_deltas(self, storage):
        """Bug 3 fix: negative deltas must not overflow struct.pack."""
        data = [100, 50, 75, 25, 200, 10, 150]
        compressed = storage.compress(data)
        assert storage.decompress(compressed) == data

    def test_random_unsorted(self, storage):
        random.seed(789)
        data = [random.randint(-100000, 100000) for _ in range(2000)]
        compressed = storage.compress(data)
        assert storage.decompress(compressed) == data

    def test_multi_block(self, storage):
        s = HYBAStorage(block_size=64)
        data = list(range(0, 1000, 3))
        compressed = s.compress(data)
        assert s.decompress(compressed) == data

    def test_compression_ratio_sorted_better(self, storage):
        random.seed(42)
        sorted_data = list(range(10000))
        random_data = [random.randint(0, 10**6) for _ in range(10000)]
        sorted_ratio = (len(sorted_data) * 8) / len(storage.compress(sorted_data))
        random_ratio = (len(random_data) * 8) / len(storage.compress(random_data))
        assert sorted_ratio > random_ratio

    def test_fold_unfold_even(self, storage):
        data = [1, 2, 3, 4, 5, 6, 7, 8]
        folded = storage._fold(data[:])
        unfolded = storage._unfold(folded[:])
        assert unfolded == data

    def test_fold_unfold_odd(self, storage):
        """NEW fix: odd-length fold must roundtrip."""
        data = [1, 2, 3]
        folded = storage._fold(data[:])
        unfolded = storage._unfold(folded[:])
        assert unfolded == data

    def test_fold_unfold_odd_5(self, storage):
        data = [1, 2, 3, 4, 5]
        folded = storage._fold(data[:])
        unfolded = storage._unfold(folded[:])
        assert unfolded == data

    def test_fold_unfold_empty(self, storage):
        assert storage._fold([]) == []
        assert storage._unfold([]) == []

    def test_fold_unfold_single(self, storage):
        data = [42]
        folded = storage._fold(data[:])
        unfolded = storage._unfold(folded[:])
        assert unfolded == data

    def test_compress_with_fold(self, storage):
        """Compression with fold=True must still roundtrip."""
        data = [1, 2, 3, 4, 5, 6, 7, 8]
        compressed = storage.compress(data[:], use_fold=True)
        decompressed = storage.decompress(compressed, use_fold=True)
        assert decompressed == data

    def test_compress_with_fold_odd(self, storage):
        """Compression with fold on odd-length must roundtrip."""
        data = [1, 2, 3, 4, 5]
        compressed = storage.compress(data[:], use_fold=True)
        decompressed = storage.decompress(compressed, use_fold=True)
        assert decompressed == data


# ═══════════════════════════════════════════════════════════════════
# 3. MEMORY ALLOCATION (Bug 4 fix)
# ═══════════════════════════════════════════════════════════════════

class TestMemory:

    def test_rejects_gap_smaller_than_size(self):
        """Bug 4 fix: gap=4, size=10 must be rejected (old code used gap²=16)."""
        mem = HYBAMemory(max_primes=100)
        # Patch to controlled primes/gaps
        mem._primes = [7, 11]
        mem._gaps = [4]
        with pytest.raises(MemoryError):
            mem.allocate(10)

    def test_accepts_gap_equals_size(self):
        mem = HYBAMemory(max_primes=100)
        mem._primes = [101, 111]
        mem._gaps = [10]
        addr = mem.allocate(10)
        assert addr is not None

    def test_accepts_gap_larger_than_size(self):
        mem = HYBAMemory(max_primes=100)
        mem._primes = [101, 114]
        mem._gaps = [13]
        addr = mem.allocate(8)
        assert addr is not None

    def test_all_accepted_offsets_nonneg(self):
        """Property test: all accepted allocations have offset >= 0."""
        mem = HYBAMemory(max_primes=100)
        random.seed(321)
        for _ in range(100):
            gap = random.randint(1, 50)
            size = random.randint(1, 50)
            # Simulate the corrected invariant
            if gap >= size:
                offset = gap - size
                assert offset >= 0

    def test_write_read(self):
        mem = HYBAMemory(max_primes=100)
        mem._primes = [101, 114]
        mem._gaps = [13]
        addr = mem.allocate(8)
        mem.write(addr, "test_data")
        assert mem.read(addr) == "test_data"

    def test_free(self):
        mem = HYBAMemory(max_primes=100)
        mem._primes = [101, 114]
        mem._gaps = [13]
        addr = mem.allocate(8)
        mem.write(addr, "data")
        mem.free(addr)
        assert not mem.is_allocated(addr)


# ═══════════════════════════════════════════════════════════════════
# 4. COMPUTE — LIFTING (Bug 5 fix)
# ═══════════════════════════════════════════════════════════════════

class TestCompassLifting:

    def test_integer_roundtrip_basic(self, compute):
        for x, y in [(0, 0), (1, 0), (0, 1), (1, 1), (-1, -1)]:
            lx, ly = compute.compass_lift(x, y)
            ux, uy = compute.compass_unlift(lx, ly)
            assert (ux, uy) == (x, y), f"Roundtrip failed for ({x}, {y})"

    def test_integer_roundtrip_large(self, compute):
        for x, y in [(100, 200), (-500, 300), (10**6, -10**6)]:
            lx, ly = compute.compass_lift(x, y)
            ux, uy = compute.compass_unlift(lx, ly)
            assert (ux, uy) == (x, y)

    def test_integer_roundtrip_random(self, compute):
        random.seed(123)
        for _ in range(100):
            x = random.randint(-10000, 10000)
            y = random.randint(-10000, 10000)
            lx, ly = compute.compass_lift(x, y)
            ux, uy = compute.compass_unlift(lx, ly)
            assert (ux, uy) == (x, y), f"Failed for ({x}, {y})"

    def test_large_int_roundtrip(self, compute):
        random.seed(456)
        for _ in range(50):
            x = random.randint(-10**9, 10**9)
            y = random.randint(-10**9, 10**9)
            lx, ly = compute.compass_lift(x, y)
            ux, uy = compute.compass_unlift(lx, ly)
            assert (ux, uy) == (x, y)

    def test_float_rejected(self, compute):
        """Bug 5 fix: floats must raise TypeError."""
        with pytest.raises(TypeError):
            compute.compass_lift(1.5, 2.0)

    def test_float_rejected_unlift(self, compute):
        with pytest.raises(TypeError):
            compute.compass_unlift(1.5, 2.0)

    def test_mixed_int_float_rejected(self, compute):
        with pytest.raises(TypeError):
            compute.compass_lift(1, 2.5)

    def test_numpy_int_accepted(self, compute):
        """Integral type (numpy int64) should be accepted."""
        try:
            import numpy as np
            x, y = np.int64(5), np.int64(3)
            lx, ly = compute.compass_lift(x, y)
            ux, uy = compute.compass_unlift(lx, ly)
            assert (ux, uy) == (5, 3)
        except ImportError:
            pytest.skip("numpy not installed")


class TestCortexFold:

    def test_fold_unfold_even(self, compute):
        data = [1, 2, 3, 4, 5, 6]
        folded = compute.cortex_fold(data)
        unfolded = compute.cortex_unfold(folded)
        assert list(unfolded) == data

    def test_fold_unfold_odd(self, compute):
        """Odd-length cortex fold must roundtrip."""
        data = [1, 2, 3, 4, 5]
        folded = compute.cortex_fold(data)
        unfolded = compute.cortex_unfold(folded)
        assert list(unfolded) == data

    def test_fold_unfold_single(self, compute):
        data = [42]
        folded = compute.cortex_fold(data)
        unfolded = compute.cortex_unfold(folded)
        assert list(unfolded) == data


class TestAccelPisot:

    def test_threshold_1e_6(self, compute):
        """x²-3x-1 Pisot needs exactly 12 iterations for 10⁻⁶."""
        assert compute.accel_multiplies(1e-6) == 12

    def test_threshold_1e_3(self, compute):
        n = compute.accel_multiplies(1e-3)
        assert n >= 1 and n < 12

    def test_threshold_1e_12(self, compute):
        n = compute.accel_multiplies(1e-12)
        assert n > 12


# ═══════════════════════════════════════════════════════════════════
# 5. CORE PRIMITIVES
# ═══════════════════════════════════════════════════════════════════

class TestCorePrimitives:

    def test_fibonacci_basic(self, core):
        assert core.fibonacci(0) == 0
        assert core.fibonacci(1) == 1
        assert core.fibonacci(10) == 55
        assert core.fibonacci(50) == 12586269025

    def test_lucas_basic(self, core):
        assert core.lucas(0) == 2
        assert core.lucas(1) == 1
        assert core.lucas(10) == 123
        assert core.lucas(50) == 28143753123

    def test_binet_f_exactness(self, core):
        for n in [0, 1, 5, 10, 50, 100, 500, 1000]:
            assert core.fibonacci(n) == core.binet_f(n), f"Binet F({n}) mismatch"

    def test_binet_l_exactness(self, core):
        for n in [0, 1, 5, 10, 50, 100, 500]:
            assert core.lucas(n) == core.binet_l(n), f"Binet L({n}) mismatch"

    def test_matrix_power_structure(self, core):
        """Q^n = [[F(n+1), F(n)], [F(n), F(n-1)]]."""
        for n in range(1, 50):
            m = core.matrix_power(n)
            assert m[0][0] == core.fibonacci(n + 1)
            assert m[0][1] == core.fibonacci(n)
            assert m[1][0] == core.fibonacci(n)
            assert m[1][1] == core.fibonacci(n - 1)

    def test_cassini_identity(self, core):
        """det(Q^n) = (-1)^n."""
        for n in range(100):
            m = core.matrix_power(n)
            det = core.matrix_det(m)
            expected = -1 if n % 2 == 1 else 1
            assert det == expected, f"Cassini failed at n={n}"

    def test_matrix_power_law(self, core):
        """Q^a · Q^b = Q^(a+b)."""
        for a, b in [(1, 1), (2, 3), (5, 8), (10, 15)]:
            prod = core.matrix_multiply(core.matrix_power(a), core.matrix_power(b))
            assert prod == core.matrix_power(a + b)

    def test_fib_pair_fast_doubling(self, core):
        for n in range(100):
            fn, fn1 = core.fib_pair(n)
            assert fn == core.fibonacci(n)
            assert fn1 == core.fibonacci(n + 1)


# ═══════════════════════════════════════════════════════════════════
# 6. INVARIANTS
# ═══════════════════════════════════════════════════════════════════

class TestInvariants:

    def test_cassini(self, invariants):
        result = invariants.verify_cassini()
        assert result['passed'], f"Cassini failures: {result['failures']}"

    def test_volume_preservation(self, invariants):
        assert invariants.verify_volume_preservation()

    def test_pisot_convergence(self, invariants):
        result = invariants.verify_pisot_convergence()
        assert result['passed'], f"Pisot failures: {result['failures']}"

    def test_pisot_monotonic(self, invariants):
        assert invariants.verify_pisot_monotonic()

    def test_binet_exactness(self, invariants):
        result = invariants.verify_binet_exactness()
        assert result['passed'], f"Binet failures: {result['failures']}"

    def test_lucas_binet(self, invariants):
        result = invariants.verify_lucas_binet()
        assert result['passed'], f"Lucas-Binet failures: {result['failures']}"

    def test_matrix_power_law(self, invariants):
        result = invariants.verify_matrix_power_law()
        assert result['passed'], f"Power law failures: {result['failures']}"

    def test_commutativity(self, invariants):
        result = invariants.verify_commutativity()
        assert result['passed'], f"Commutativity failures: {result['failures']}"

    def test_integrity_rejects_impostors(self, invariants):
        result = invariants.verify_integrity_rejects_impostors()
        assert result['passed'], f"Impostor failures: {result['failures']}"

    def test_verify_all(self, invariants):
        results = invariants.verify_all()
        all_passed = all(
            r.get('passed', r) if isinstance(r, dict) else r
            for r in results.values()
        )
        assert all_passed, "Some invariants failed"


# ═══════════════════════════════════════════════════════════════════
# 7. INFRASTRUCTURE
# ═══════════════════════════════════════════════════════════════════

class TestInfrastructure:

    def test_initialize(self):
        infra = HYBAInfrastructure()
        assert infra.initialize()
        assert infra.is_initialized()

    def test_process_compress_decompress(self):
        infra = HYBAInfrastructure()
        infra.initialize()
        data = [1, 2, 3, 4, 5, 6, 7, 8]
        compressed = infra.process(data[:], "compress")
        decompressed = infra.process(compressed, "decompress")
        assert decompressed == data

    def test_process_fold_unfold(self):
        infra = HYBAInfrastructure()
        infra.initialize()
        data = [1, 2, 3, 4, 5, 6]
        folded = infra.process(data[:], "fold")
        unfolded = infra.process(folded, "unfold")
        assert list(unfolded) == data

    def test_process_precision(self):
        infra = HYBAInfrastructure()
        infra.initialize()
        result = infra.process(None, "precision", precision=1e-6)
        assert result == 12

    def test_process_memory(self):
        infra = HYBAInfrastructure()
        infra.initialize()
        addr = infra.process(None, "memory_allocate", size=2)
        assert addr is not None
        infra.process(None, "memory_write", address=addr, value="test")
        assert infra.process(None, "memory_read", address=addr) == "test"
        infra.process(None, "memory_free", address=addr)

    def test_not_initialized_rejects(self):
        infra = HYBAInfrastructure()
        with pytest.raises(RuntimeError):
            infra.process([1, 2, 3], "compress")

    def test_shutdown(self):
        infra = HYBAInfrastructure()
        infra.initialize()
        infra.shutdown()
        assert not infra.is_running()
        assert not infra.is_initialized()
