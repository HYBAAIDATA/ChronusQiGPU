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

## Result 3: multi-marked one-shot search, and the dense statevector is gone

Two further steps complete the frontier the first experiment left open:

**Multiplicity.** With r marked states the invariant subspace is still two-dimensional, and the closed form generalizes: `beta/(1+beta) = ±r·k`, `alpha = 1 − N/(r·(1+beta))`, `k = (N·u)⁻¹`. One iterate puts every marked amplitude at exactly ±1 and every unmarked amplitude at exactly 0 — the full marked set is identified at once. Verified exhaustively over all subsets for n ≤ 4, sampled to n = 10, and cross-checked against a brute-force phase sweep that independently rediscovers the closed-form pairs. r = 1 reduces to the original single-marked form; a sign branch is dropped when its denominator vanishes (N·u ≡ ±r), leaving one sufficient pair.

**Memory.** The earlier "2^n field elements — the honest cost" row reflected the flat-array harness, not the mathematics. The uniform state, the marked indicator, and the iterate span a rank-2 subspace, so the trajectory is exactly the pair `(a_marked, a_unmarked)` — both elements of the prime field F₂₅₇, the same field that anchors the receipts. `chronus.quantum.subspace` executes the search on that pair alone — **no dense statevector is allocated at any point** — and dense-vs-symbolic trajectories are asserted equal step by step. Marked-set membership is decided by oracle evaluation per candidate, never by a state table.

**Persistence.** Working memory is the rank-2 pair; long-term memory is the phyllotaxis store. `EXACT_PHASE_SEARCH` with `"store": true` writes the converged state through Theseus: content-addressed in Ovid, distributed onto a golden-ratio lane, with PV scale lineage on the record and Cassini parity reported as metadata. Retrieval is digest-verified and reproduces the exact state.

## Result 4: the extension field completes the pairing — search and PV parity in one step

With amplitudes, oracle phases and diffusion phases in F₂₅₇[φ] ≅ F₂₅₇² (order 66,048), the target marked amplitude becomes v = φˢ. The closed form generalizes verbatim (`β = r·v/(N·u − r·v)`, `α = 1 − v/(β·u)`), and because N(φˢ) = (−1)ˢ exactly, **one oracle + one diffusion step simultaneously identifies the marked set and encodes the Lucas/PV scale parity in the surviving amplitude**. Verified exhaustively: n = 1..7, r = 1..5, s = 0..7, every combination converging with `norm_parity_verified`. Degenerate parameters (N·u = r·v, only scalar targets in the tested range) fall back to the prime-subfield pair and land on −1, norm 1 — still parity-exact. At s = 0 the extension reduces to the proven prime-field pairs.

## What scales and what does not

| Component | Scaling |
|---|---|
| State preparation (Hadamard wall) | O(n) gates for n qubits |
| One-shot phase-matched search (single or multi-marked) | 1 oracle + 1 diffusion, closed-form phases |
| Extension-field search (F₂₅₇[φ]) | Same single step; marked amplitude is φˢ, norm = (−1)ˢ — PV parity carried by the result itself |
| Exact working state | **2 field elements (rank-2 symbolic)** — the 2^n dense array is eliminated |
| Persistent memory | Theseus/Ovid phyllotaxis store: converged states are content-addressed, lane-addressed by the golden ratio, carrying PV scale lineage and Cassini parity metadata (`"store": true` on `EXACT_PHASE_SEARCH`) |
| Marked-set membership resolution | 1 oracle query per candidate index |
| Reflection-coefficient metallic scaling | Does not converge (documented negative result) |

## Reproduce

```bash
python -m pytest tests/test_metallic_search.py tests/test_grover.py -q
```

All iteration counts, phase pairs, and convergence claims above are asserted in the test suite.
