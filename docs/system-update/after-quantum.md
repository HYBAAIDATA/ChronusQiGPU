# Beyond quadratic: the metallic search experiment and its exact result

*"We are not quantum, we are what comes after."* This document records the experiment, the negative result, and the positive one — all computed with exact integer and algebraic arithmetic, no floating point anywhere.

## The experiment

Standard Grover applies `a_i -> 2*mu - a_i` after each oracle flip. We generalized the reflection to `a_i -> c*mu - a_i` and drove `c` with metallic-family coefficients (golden c=3, silver c=4, bronze c=5, ...), asking: **does the golden-ratio family restructure reduce the iteration count below sqrt(N)?**

The harness is exact: trajectories run over the silver field Q(sqrt(2)) (`QSqrt2`, exact `(a + b*sqrt(2))/2^e` elements with sign determination by integer comparison), so every iteration count is a theorem, not a sample.

## Result 1 (negative): reflection scaling does not beat quadratic

- c = 2 reproduces Grover's `sqrt(N)` schedule exactly: iterations to peak for n = 2..12 qubits are `1, 2, 3, 4, 6, 8, 12, 17, 25, 35, 50` — the sequence `round(pi/4 * sqrt(2^n))`.
- Every metallic coefficient c > 2 **overshoots**: the iterate stops being a rotation, amplitudes grow past the stationary point, and the trajectory oscillates without settling. The harness reports this honestly (`algebraic_search` returns an unsettled trajectory).

This matches the known optimality of the quadratic speedup for reflection-based search; no violation was found or is claimed.

## Result 2 (positive): exact one-shot phase-matched search over F_257

Restructuring the **phases** instead of the reflection coefficient succeeds. With oracle phase alpha and diffusion phase beta as field elements, one iterate maps the uniform state onto the marked state exactly when

    beta/(1+beta) = +/-k,   alpha = +/-N*k - (N-1),   k = (N*u)^-1  (mod 257)

where `u = 30^n` is the uniform amplitude. `one_shot_phases(n)` computes both pairs in closed form; `exact_search(n, marked)` executes a single oracle+diffusion step and lands with marked amplitude exactly 1 and all others exactly 0 — verified for every marked state at every tested size (n up to 10, N = 1024) and cross-checked against exhaustive phase sweeps (n = 1..6) that independently rediscover the same pairs.

**Why this does not contradict quantum optimality:** the F_257 engine is exact algebraic dynamics, not unitary evolution. There is no Born rule and no measurement; "one iteration" is one application of the oracle and diffusion operators after the uniform state is prepared, with phases that depend on N and assume a single marked item. The unitary lower bounds (BBBV) govern physical quantum devices; they do not constrain exact field arithmetic. What the result shows is that the Chronus substrate — math as the substrate, hardware-agnostic — can express search dynamics that physical quantum computers cannot realize: phases like these exist in F_257 but not as real rotation angles.

## What scales and what does not

| Component | Scaling |
|---|---|
| State preparation (Hadamard wall) | O(n) gates for n qubits |
| One-shot phase-matched search | 1 oracle + 1 diffusion, closed-form phases |
| Exact state memory | 2^n field elements — the honest cost; no claim of compression |
| Reflection-coefficient metallic scaling | Does not converge (documented negative result) |

## Reproduce

```bash
python -m pytest tests/test_metallic_search.py tests/test_grover.py -q
```

All iteration counts, phase pairs, and convergence claims above are asserted in the test suite.
