# Exact Math-Folding Reference

The production reference lives at:

```text
python_backend/core_modules/math_folding.py
```

The canonical mining import is:

```text
chronus/mla1517/math_folding.py
```

The mining module re-exports the repository-local implementation; it does not
call another repository.

## Implemented mathematical contracts

- Exact Fibonacci and Lucas generation through existing `chronus.mla1517.core`
- Exact Binet evaluation in \(Q(\sqrt5)\), represented as rational coefficient
  pairs
- Fibonacci and Lucas Cassini witnesses using arbitrary-precision integers
- Canonical, non-adjacent Zeckendorf address construction and round-trip checks
- Reversible PULVINI pair folding using a unimodular Fibonacci Q-matrix step
- Exact algebraic Pisot threshold \(\Phi^{-n}\)
- Exact discarded spectral-weight accounting for rational singular values

Floating-point inputs are rejected by the Pisot truncation reference.

## Claim boundaries

The Zeckendorf router establishes a deterministic conflict-avoidance address
structure. It does not, by itself, establish reduced physical bus contention.
That requires a substrate benchmark against linear, blocked, and hashed routing.

Cassini witnesses detect corruption only when the sequence index, tensor
metadata, and address are bound into the same evidence receipt.

The Pisot threshold is exact. Trace preservation and sub-exponential resource
scaling are not inferred from the threshold. The implementation reports exact
discarded weight; downstream normalization, fidelity, complexity, and hardware
measurements remain separate evidence.

## Substrate progression

1. CPU arbitrary-precision integer and rational reference
2. Packed CPU implementation
3. OpenCL integer kernel with bit-exact conformance
4. Additional accelerators only after the same conformance suite

CPU exact arithmetic is the mathematical oracle. OpenCL is the next execution
target, not the source of truth.