"""
FAMILY 9: RUNTIME INFRASTRUCTURE
==================================
Tests for φ-based runtime components: integrity validation, data folding,
lifting transforms, generalized Pisot convergence, and compression.

THEOREMS:
  - Cassini integrity: unknown matrices can be validated as M_φ^n states
  - M_φ fold: exact integer invertibility (det = -1)
  - Pisot convergence thresholds: exact n for |conj|^n < ε
  - Delta+FOR compression: lossless roundtrip

INVARIANTS:
  - Golden-angle lifting: integer roundtrip exactness
  - Float input rejection for lifting
  - Compressed data decompresses to exact original

DEMONSTRATIONS:
  - Pisot convergence rate comparison (φ vs x²-3x-1)
  - Compression ratios on different data patterns
"""

import random
from ..results import CheckRegistry
from ..runtime.integrity import is_valid_mphi_matrix, recover_exponent, matrix_power
from ..runtime.folds import fold_pair, unfold_pair, fold_array, unfold_array, fold_roundtrip
from ..runtime.lifting import lift, unlift, lift_roundtrip
from ..runtime.pisot import (
    pisot_phi, pisot_3, iterations_for_precision, verify_threshold, convergence_ratio,
)
from ..runtime.delta_for import compress, decompress, compression_ratio, delta_encode, delta_decode
from ..runtime.memory import allocate_buggy, allocate_correct, allocate_lucas, lucas_threshold, prime_gap
from ..sequences import fibonacci, lucas
from decimal import Decimal


def run(registry: CheckRegistry, max_n: int = 5000) -> None:
    family = "FAMILY 9: Runtime Infrastructure"
    purpose = "RUNTIME"

    # ═══════════════════════════════════════════════════════════════════
    #  9A: CASSINI INTEGRITY — UNKNOWN MATRIX VALIDATION
    # ═══════════════════════════════════════════════════════════════════

    # ── 9A-1: Valid M_φ^n matrices pass validation ──
    test_ns = list(range(0, 200))
    all_valid = True
    for n in test_ns:
        m = matrix_power(n)
        if not is_valid_mphi_matrix(m):
            all_valid = False
            registry.add_check(family, purpose,
                f"9A-1: Valid M_φ^{n} passes integrity check", False, "theorem")
            break
    if all_valid:
        registry.add_check(family, purpose,
            f"9A-1: All valid M_φ^n (n=0..199) pass integrity check",
            True, "theorem",
            "Checks: 2×2 shape, symmetry, a-d=b, det=±1, non-negative")

    # ── 9A-2: Invalid matrices fail validation ──
    invalid_matrices = [
        [[1, 2], [3, 4]],           # Not symmetric, det=-2
        [[2, 1], [1, 2]],            # Symmetric but a-d=0≠1=b, det=3
        [[3, 1], [1, 2]],            # a-d=1=b, det=5≠±1
        [[1, 1], [0, 1]],           # Not symmetric
        [[5, 3], [3, 2]],           # Valid structure but det=1, check recovers n=4
        [[-1, 1], [1, 0]],          # Negative entry (Q^(-1) form)
        [[0, 0], [0, 0]],           # Zero matrix
        [[1, 1], [1, 0]],           # This IS Q^1 = valid! Should pass
    ]
    # [[5,3],[3,2]] is Q^4: F(5)=5, F(4)=3, F(3)=2. Valid!
    # [[1,1],[1,0]] is Q^1: F(2)=1, F(1)=1, F(0)=0. Valid!
    expected_valid = [False, False, False, False, True, False, False, True]
    all_correct = True
    for i, (m, expected) in enumerate(zip(invalid_matrices, expected_valid)):
        result = is_valid_mphi_matrix(m)
        if result != expected:
            all_correct = False
            registry.add_check(family, purpose,
                f"9A-2: Matrix {m} validation (expected {expected})",
                False, "theorem",
                f"Got {result}")
            break
    if all_correct:
        registry.add_check(family, purpose,
            "9A-2: Invalid matrices rejected, valid ones accepted",
            True, "theorem",
            "Tested 8 matrices including Q^1, Q^4, Q^(-1), zero, and random invalids")

    # ── 9A-3: Exponent recovery ──
    all_recovered = True
    for n in range(0, 100):
        m = matrix_power(n)
        recovered = recover_exponent(m)
        if recovered != n:
            all_recovered = False
            registry.add_check(family, purpose,
                f"9A-3: Recover exponent for M_φ^{n}", False, "theorem",
                f"Expected {n}, got {recovered}")
            break
    if all_recovered:
        registry.add_check(family, purpose,
            "9A-3: Exponent recovery from unknown M_φ^n (n=0..99)",
            True, "theorem",
            "Recovers n via F(n)=m[0][1], verifies full matrix match")

    # ── 9A-4: Mutated matrices fail ──
    m = matrix_power(50)
    m_mutated = [row[:] for row in m]
    m_mutated[0][0] += 1  # Single entry mutation
    mutation_detected = not is_valid_mphi_matrix(m_mutated)
    registry.add_check(family, purpose,
        "9A-4: Single-entry mutation detected by integrity check",
        mutation_detected, "invariant",
        f"Original valid: {is_valid_mphi_matrix(m)}, Mutated valid: {is_valid_mphi_matrix(m_mutated)}")

    # ═══════════════════════════════════════════════════════════════════
    #  9B: M_φ FOLD — EXACT INTEGER INVERTIBILITY
    # ═══════════════════════════════════════════════════════════════════

    # ── 9B-1: Pair roundtrip ──
    test_pairs = [(0, 0), (1, 0), (0, 1), (1, 1), (5, 3), (-1, 1),
                  (-5, -3), (100, -50), (0, 100), (10**6, 10**6)]
    all_pairs_ok = True
    for x, y in test_pairs:
        u, v = fold_pair(x, y)
        x2, y2 = unfold_pair(u, v)
        if (x2, y2) != (x, y):
            all_pairs_ok = False
            registry.add_check(family, purpose,
                f"9B-1: Pair roundtrip ({x},{y})", False, "theorem")
            break
    if all_pairs_ok:
        registry.add_check(family, purpose,
            "9B-1: M_φ fold pair roundtrip (incl. negatives, zeros, large ints)",
            True, "theorem",
            "fold: (x,y)→(x+y,x), unfold: (u,v)→(v,u-v). det=[[1,1],[1,0]]=-1")

    # ── 9B-2: Array roundtrip ──
    random.seed(42)
    test_arrays = [
        [],
        [42],
        [1, 2],
        [1, 2, 3, 4, 5, 6, 7, 8],
        list(range(100)),
        list(range(0, 1000, 7)),
        [random.randint(-10000, 10000) for _ in range(500)],
        [random.randint(-10**6, 10**6) for _ in range(100)],
        list(range(-100, 100)),
        [0] * 50 + [1] * 50,
    ]
    all_arrays_ok = True
    for arr in test_arrays:
        if not fold_roundtrip(arr):
            all_arrays_ok = False
            registry.add_check(family, purpose,
                f"9B-2: Array roundtrip (len={len(arr)})", False, "theorem")
            break
    if all_arrays_ok:
        registry.add_check(family, purpose,
            f"9B-2: M_φ fold array roundtrip for {len(test_arrays)} test arrays",
            True, "theorem",
            "Tests: empty, single, even, odd, sorted, random, negative, large")

    # ── 9B-3: Fold preserves information ──
    # The fold is a bijection on Z², so it cannot lose information
    # Verify by checking that different inputs produce different outputs
    seen_outputs = set()
    info_preserved = True
    for x in range(-10, 11):
        for y in range(-10, 11):
            u, v = fold_pair(x, y)
            if (u, v) in seen_outputs:
                info_preserved = False
                break
            seen_outputs.add((u, v))
        if not info_preserved:
            break
    registry.add_check(family, purpose,
        "9B-3: M_φ fold is injective (no information loss) for 441 pairs",
        info_preserved, "theorem",
        "21×21 grid of (x,y) pairs, all produce unique outputs")

    # ═══════════════════════════════════════════════════════════════════
    #  9C: GOLDEN-ANGLE 3-SHEAR INTEGER LIFTING
    # ═══════════════════════════════════════════════════════════════════

    # ── 9C-1: Integer roundtrip ──
    random.seed(123)
    test_coords = [(0, 0), (1, 0), (0, 1), (1, 1), (-1, -1),
                   (100, 200), (-500, 300), (10**6, -10**6),
                   (42, -17), (0, 999)]
    # Add random integer pairs
    for _ in range(100):
        test_coords.append((random.randint(-10000, 10000), random.randint(-10000, 10000)))

    all_lift_ok = True
    for x, y in test_coords:
        if not lift_roundtrip(x, y):
            all_lift_ok = False
            registry.add_check(family, purpose,
                f"9C-1: Lifting roundtrip ({x},{y})", False, "theorem")
            break
    if all_lift_ok:
        registry.add_check(family, purpose,
            f"9C-1: Golden-angle lifting roundtrip for {len(test_coords)} integer pairs",
            True, "theorem",
            "3-shear integer wavelet, round-half-away-from-zero rounding")

    # ── 9C-2: Float input rejection ──
    float_rejected = False
    try:
        lift(1.5, 2.0)
    except TypeError:
        float_rejected = True
    registry.add_check(family, purpose,
        "9C-2: Float inputs rejected by lifting (TypeError)",
        float_rejected, "invariant",
        "Integer-only enforcement prevents float drift accumulation")

    # ── 9C-3: Large integer roundtrip ──
    random.seed(456)
    large_ok = True
    for _ in range(50):
        x = random.randint(-10**9, 10**9)
        y = random.randint(-10**9, 10**9)
        if not lift_roundtrip(x, y):
            large_ok = False
            break
    registry.add_check(family, purpose,
        "9C-3: Lifting roundtrip for large integers (up to 10⁹)",
        large_ok, "theorem",
        "50 random pairs with coordinates in [-10⁹, 10⁹]")

    # ═══════════════════════════════════════════════════════════════════
    #  9D: GENERALIZED PISOT CONVERGENCE
    # ═══════════════════════════════════════════════════════════════════

    # ── 9D-1: φ conjugate properties ──
    phi_root, phi_conj, phi_poly = pisot_phi()
    phi_conj_mag = abs(phi_conj)
    phi_pisot_ok = phi_conj_mag < 1
    registry.add_check(family, purpose,
        f"9D-1: φ is Pisot (|conjugate| = {float(phi_conj_mag):.6f} < 1)",
        phi_pisot_ok, "theorem",
        f"Minimal polynomial: {phi_poly}, conjugate ≈ {float(phi_conj_mag):.6f}")

    # ── 9D-2: x²-3x-1 conjugate properties ──
    root3, conj3, poly3 = pisot_3()
    conj3_mag = abs(conj3)
    pisot3_ok = conj3_mag < 1 and root3 > 1
    registry.add_check(family, purpose,
        f"9D-2: x²-3x-1 root is Pisot (|conj| = {float(conj3_mag):.6f} < 1, root = {float(root3):.6f} > 1)",
        pisot3_ok, "theorem",
        f"Minimal polynomial: {poly3}")

    # ── 9D-3: Exact convergence threshold for φ (n=29 for 10⁻⁶) ──
    precision = Decimal("1e-6")
    n_phi = iterations_for_precision(phi_conj_mag, precision)
    threshold_phi_ok = verify_threshold(phi_conj_mag, n_phi, precision)
    registry.add_check(family, purpose,
        f"9D-3: φ convergence threshold: |ψ|^{n_phi} < 10⁻⁶ but |ψ|^{n_phi-1} ≥ 10⁻⁶",
        threshold_phi_ok and n_phi == 29, "theorem",
        f"|ψ| ≈ {float(phi_conj_mag):.6f}, n={n_phi}")

    # ── 9D-4: Exact convergence threshold for x²-3x-1 (n=12 for 10⁻⁶) ──
    n_3 = iterations_for_precision(conj3_mag, precision)
    threshold_3_ok = verify_threshold(conj3_mag, n_3, precision)
    registry.add_check(family, purpose,
        f"9D-4: x²-3x-1 convergence threshold: |ψ₃|^{n_3} < 10⁻⁶ but |ψ₃|^{n_3-1} ≥ 10⁻⁶",
        threshold_3_ok and n_3 == 12, "theorem",
        f"|ψ₃| ≈ {float(conj3_mag):.6f}, n={n_3}")

    # ── 9D-5: Convergence rate comparison (demonstration) ──
    ratio = convergence_ratio(phi_conj, conj3)
    faster = n_3 < n_phi
    registry.add_check(family, purpose,
        f"9D-5: x²-3x-1 converges faster than φ ({n_3} vs {n_phi} iterations, ratio {ratio:.2f}×)",
        faster, "demonstration",
        f"Smaller conjugate magnitude → faster exponential decay")

    # ── 9D-6: Threshold at different precisions ──
    precisions = [Decimal("1e-3"), Decimal("1e-6"), Decimal("1e-12"), Decimal("1e-24")]
    all_thresholds_ok = True
    for prec in precisions:
        n_p = iterations_for_precision(phi_conj_mag, prec)
        n_t = iterations_for_precision(conj3_mag, prec)
        if n_p <= 0 or n_t <= 0 or n_t >= n_p:
            all_thresholds_ok = False
            break
    if all_thresholds_ok:
        registry.add_check(family, purpose,
            "9D-6: x²-3x-1 always converges faster than φ at all tested precisions",
            True, "theorem",
            f"Tested at 10⁻³, 10⁻⁶, 10⁻¹², 10⁻²⁴")

    # ═══════════════════════════════════════════════════════════════════
    #  9E: DELTA + FOR COMPRESSION
    # ═══════════════════════════════════════════════════════════════════

    # ── 9E-1: Lossless roundtrip — empty ──
    empty_result = decompress(compress([]))
    registry.add_check(family, purpose,
        "9E-1: Empty array compression roundtrip",
        empty_result == [], "theorem")

    # ── 9E-2: Lossless roundtrip — single value ──
    single_result = decompress(compress([42]))
    registry.add_check(family, purpose,
        "9E-2: Single value compression roundtrip",
        single_result == [42], "theorem")

    # ── 9E-3: Lossless roundtrip — sorted sequential ──
    sorted_data = list(range(1000))
    sorted_result = decompress(compress(sorted_data))
    registry.add_check(family, purpose,
        "9E-3: Sorted sequential (0..999) compression roundtrip",
        sorted_result == sorted_data, "theorem")

    # ── 9E-4: Lossless roundtrip — negative values ──
    neg_data = list(range(-500, 500))
    neg_result = decompress(compress(neg_data))
    registry.add_check(family, purpose,
        "9E-4: Negative values (-500..499) compression roundtrip",
        neg_result == neg_data, "theorem")

    # ── 9E-5: Lossless roundtrip — random unsorted ──
    random.seed(789)
    random_data = [random.randint(-100000, 100000) for _ in range(2000)]
    random_result = decompress(compress(random_data))
    registry.add_check(family, purpose,
        "9E-5: Random unsorted (2000 values) compression roundtrip",
        random_result == random_data, "theorem")

    # ── 9E-6: Lossless roundtrip — multi-block ──
    large_data = list(range(0, 10000, 3))  # 3334 values, multiple blocks
    large_result = decompress(compress(large_data, block_size=512))
    registry.add_check(family, purpose,
        "9E-6: Multi-block (3334 values, block_size=512) roundtrip",
        large_result == large_data, "theorem")

    # ── 9E-7: Compression ratio — sorted data (demonstration) ──
    sorted_ratio = compression_ratio(list(range(10000)))
    random.seed(42)
    random_ratio = compression_ratio([random.randint(0, 10**6) for _ in range(10000)])
    sorted_better = sorted_ratio > random_ratio
    registry.add_check(family, purpose,
        f"9E-7: Sorted data compresses better than random ({sorted_ratio:.1f}× vs {random_ratio:.1f}×)",
        sorted_better, "demonstration",
        f"Sorted: {sorted_ratio:.1f}×, Random: {random_ratio:.1f}×")

    # ── 9E-8: Delta encode/decode roundtrip ──
    random.seed(111)
    delta_test = [random.randint(0, 1000) for _ in range(100)]
    deltas = delta_encode(delta_test)
    decoded = delta_decode(deltas)
    registry.add_check(family, purpose,
        "9E-8: Delta encode/decode roundtrip (100 random values)",
        decoded == delta_test, "theorem")

    # ── 9E-9: Compression with signed deltas ──
    non_monotonic = [100, 50, 75, 25, 200, 10, 150]
    nm_result = decompress(compress(non_monotonic))
    registry.add_check(family, purpose,
        "9E-9: Non-monotonic data with negative deltas compresses correctly",
        nm_result == non_monotonic, "theorem",
        f"Input: {non_monotonic}, deltas: {delta_encode(non_monotonic)}")

    # ═══════════════════════════════════════════════════════════════════
    #  9F: MEMORY ALLOCATION — PRIME GAP OVERFLOW REGRESSION
    # ═══════════════════════════════════════════════════════════════════

    # ── 9F-1: Buggy allocation accepts underflow case ──
    # gap=5, size=10: buggy code has capacity=25 >= 10, but offset=-5
    accepted_buggy, offset_buggy = allocate_buggy(5, 10)
    bug_confirmed = accepted_buggy and offset_buggy < 0
    registry.add_check(family, purpose,
        "9F-1: Original gap² bug produces negative offset (gap=5, size=10)",
        bug_confirmed, "theorem",
        f"Buggy: accepted={accepted_buggy}, offset={offset_buggy} (should be -5)")

    # ── 9F-2: Correct allocation rejects underflow case ──
    accepted_correct, offset_correct = allocate_correct(5, 10)
    fix_confirmed = (not accepted_correct) or (offset_correct >= 0)
    registry.add_check(family, purpose,
        "9F-2: Corrected gap >= size invariant rejects underflow (gap=5, size=10)",
        fix_confirmed, "invariant",
        f"Correct: accepted={accepted_correct}, offset={offset_correct}")

    # ── 9F-3: Correct allocation accepts valid case ──
    accepted_valid, offset_valid = allocate_correct(13, 8)
    registry.add_check(family, purpose,
        "9F-3: Valid allocation accepted (gap=13, size=8, offset=5)",
        accepted_valid and offset_valid == 5, "theorem",
        f"Accepted={accepted_valid}, offset={offset_valid}")

    # ── 9F-4: All accepted allocations have non-negative offset ──
    random.seed(321)
    all_offsets_ok = True
    tested_count = 0
    for _ in range(1000):
        gap = random.randint(1, 500)
        size = random.randint(1, 500)
        accepted, offset = allocate_correct(gap, size)
        tested_count += 1
        if accepted and offset < 0:
            all_offsets_ok = False
            break
        if not accepted and gap >= size:
            all_offsets_ok = False  # Should have accepted
            break
    registry.add_check(family, purpose,
        f"9F-4: All accepted allocations have offset ≥ 0 ({tested_count} random tests)",
        all_offsets_ok, "invariant",
        "Property: accepted ⟺ gap >= size, and offset = gap - size >= 0")

    # ── 9F-5: Buggy vs correct divergence count ──
    divergence_count = 0
    for gap in range(1, 100):
        for size in range(1, 100):
            buggy_acc, buggy_off = allocate_buggy(gap, size)
            correct_acc, correct_off = allocate_correct(gap, size)
            if buggy_acc != correct_acc:
                divergence_count += 1
            elif buggy_acc and buggy_off < 0:
                divergence_count += 1  # Accepted by both but buggy has negative offset
    registry.add_check(family, purpose,
        f"9F-5: Buggy allocation diverges from correct in {divergence_count} cases (gap,size ∈ [1,99])",
        divergence_count > 0, "demonstration",
        f"Divergence cases: {divergence_count} out of 9801")
