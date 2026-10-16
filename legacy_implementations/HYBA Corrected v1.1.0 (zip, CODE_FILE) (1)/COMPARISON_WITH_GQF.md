# HYBA vs GQF Comparison Report

## Summary

The corrected HYBA package (v1.1.0) passes all 72 unit tests, all 46 comparison probes against the Golden Quantum Framework's runtime regression layer, and all 9 invariant checks. Both implementations produce identical results on every overlapping test case.

## Test Results

### HYBA Unit Tests (72 tests, 0.40s)

| Test Class | Tests | Passed |
|------------|-------|--------|
| TestCassiniIntegrity | 12 | 12 |
| TestStorage | 14 | 14 |
| TestMemory | 6 | 6 |
| TestCompassLifting | 8 | 8 |
| TestCortexFold | 3 | 3 |
| TestAccelPisot | 3 | 3 |
| TestCorePrimitives | 8 | 8 |
| TestInvariants | 10 | 10 |
| TestInfrastructure | 7 | 7 |
| **Total** | **72** | **72** |

### HYBA vs GQF Comparison (46 probes)

| Area | Probes | Passed | Match Rate |
|------|--------|--------|------------|
| Cassini Integrity | 14 | 14 | 100% |
| Fold/Unfold | 8 | 8 | 100% |
| Storage Compression | 6 | 6 | 100% |
| Memory Allocation | 5 | 5 | 100% |
| Golden-Angle Lifting | 3 | 3 | 100% |
| Pisot Convergence | 1 | 1 | 100% |
| HYBA Invariants | 9 | 9 | 100% |
| **Total** | **46** | **46** | **100%** |

### GQF Baseline

The Golden Quantum Framework (v1.0) passes 90/90 checks and 46/46 unit tests:
- 61 theorems
- 13 invariants  
- 16 demonstrations
- 20 original unit tests + 26 runtime unit tests

## Compression Ratios (Matching)

Both implementations produce identical compression ratios on the same data:

| Data Type | HYBA Ratio | GQF Ratio |
|-----------|-----------|-----------|
| Sorted (0..999) | 12.3× | 12.3× |
| Negative (-500..499) | 9.3× | 9.3× |
| Non-monotonic | 1.9× | 1.9× |
| Random (2000 values) | 3.3× | 3.3× |

## Bug Fixes Applied

| Bug | Description | Fix |
|-----|------------|-----|
| 1 | HYBACore class not defined | Already fixed in v1.0 |
| 2 | Cassini integrity accepts impostors | Added symmetry, structural (a-d=b), non-negativity, and full matrix verification |
| 3 | struct.pack overflow on negative deltas | Changed `'<I'` to `'<q'` (signed 64-bit) |
| 4 | Memory allocation underflow (gap²) | Changed `gap² >= size` to `gap >= size` |
| 5 | Float drift in lifting | Added `isinstance(x, Integral)` check, `TypeError` on floats, round-half-away-from-zero |
| NEW | Odd-length fold breaks roundtrip | Pass through trailing element instead of padding |
| EFF | bits_per_value +1 wastes bits | Removed +1, use `max(1, max_val.bit_length())` |
| PISOT | Pisot verification used floats | Migrated to Decimal with localcontext |

## GQF-Only Coverage

Areas tested by GQF but not covered by HYBA:

1. **Zeckendorf representation** (Family 3) — unique non-consecutive Fibonacci sums
2. **Fibonacci coding** (Family 3) — prefix-free self-delimiting codes
3. **Continued fraction of φ** (Family 6) — all partial quotients = 1
4. **Golden angle layout** (Family 7) — low discrepancy, phyllotaxis uniformity
5. **KAM/Diophantine stability** (Family 8) — |φ - p/q| ≥ c/q²
6. **Catalan's identity** (Family 4) — generalization of Cassini
7. **Cayley-Hamilton theorem** (Family 5) — Q² = Q + I
8. **Badly approximable** (Family 6) — φ is "most irrational" number
9. **Exponent recovery from unknown matrix** (Family 9A)
10. **Fold injectivity proof** (Family 9B) — 441 unique pairs

## Unverified Claims

The original HYBA README claimed 50.9× compression, 98-99% search recall, 0.0000 training drift, and 97 passing tests. The 50.9× compression ratio was not reproduced — actual measured ratio on sorted data is 12.3× using int64 baseline. The test files referenced in the original paste were not included, so the 97-test claim could not be verified.
