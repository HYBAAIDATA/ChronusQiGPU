# M_32 Grover unified — exact-arithmetic audit

Branch: `feat/m32-grover-unified` (PR #168).
Date: 18 November 2026, Europe/London (UTC+0).
Scope of the *search path*: `python_backend/m32_grover_unified.py`, `python_backend/exact_folded_grover.py`, `python_backend/bit_sliced_domain_oracle.py`.
`FoldedGrover`, `optimal_iterations`, `analytical_success`, and `run_folded` in the `turing_universal_quantum_computer/`, `Intelligence/`, and `millennium/` copies of `grover_exact_scale.py` are imported from `python_backend.exact_folded_grover`.

Evidence below is only for items that actually passed. Items not on the search path are listed under “Not claimed”.

## Checklist (all PASS)

| # | Item | Result | Evidence |
| --- | --- | --- | --- |
| 1 | Two-amplitude fold is exact. Uniform start scales out \(1/\sqrt{N}\); stored marked/unmarked amplitudes start as integers \(a=b=1\). State types are `int` or `fractions.Fraction`, never `float`. | PASS | `python_backend/exact_folded_grover.py` `FoldedGrover.uniform` returns `a=1, b=1`. `test_fold_state_is_int_or_fraction_never_float` steps 8 iterates on \(N=4096,M=1\) and asserts `isinstance(..., (int, Fraction))` and `type(...) is not float`. |
| 2 | Diffusion uses rational/integer coefficients: oracle \(a\to -a\), then \(m=(M a+(N-M)b)/N\), \(a'=2m-a\), \(b'=2m-b\), with `Fraction`. | PASS | `FoldedGrover.step` (no phase arguments). Division is `... / Fraction(self.N)`, not Python 3 float `/`. |
| 3 | Success probability \(p=M a^2/N\) is an exact `Fraction` of the scaled amplitudes. | PASS | `FoldedGrover.marked_probability`. JSON telemetry serialises it as `"n/d"`. |
| 4 | Scaled Cassini identity: \(M a^2+(N-M)b^2=N\) exactly, so the normalised witness is exactly \(1\). | PASS | `test_fold_norm_is_exactly_one_and_scaled_is_N` on \((N,M)\in\{(2,1),(16,1),(16,3),(4096,1),(4096,3),(1024,7)\}\) through peak\(+3\) steps: `cassini_scaled()==N` and `cassini_witness()==Fraction(1)`. |
| 5 | \(\varphi^{-1}\) threshold is an exact integer comparison: \(p>(\sqrt{5}-1)/2 \Leftrightarrow (2p+1)^2>5\) with \(2p+1>0\). No roots or floats. | PASS | `exceeds_phi_inverse`. `test_threshold_is_exact_phi_inverse`: \(1/2\) and \(3/5\) below, \(2/3\) and \(5/8\) above; Fibonacci ratios \(F_{n-1}/F_n\) for \(n=3..19\) match the cross-multiply predicate; after 50 exact steps on \(N=4096,M=1\), \(p\) exceeds the cut. |
| 6 | Optimal iteration count is found by stepping the exact recurrence until \(p\) stops increasing. No \(\pi\) / `asin`. | PASS | `optimal_iterations`. `test_optimal_iterations_found_by_exact_stepping`: \(N=4096,M=1\) peaks at \(k=50\) (same as the old \(\lfloor\pi/(4\theta)\rfloor\)); \(N=2,M=1\) stays at \(p=1/2\), so \(k=0\); \(N=10^{100}\) returns the sentinel `ITERATION_CAP+1=2000001` without stepping. |
| 7 | Pisot damping \(1-\lvert\psi\rvert^n\) is exact in \(\mathbb{Q}(\sqrt{5})\), and is not used as a Grover phase. | PASS | `QSqrt5` and `pisot_damp_qsqrt5`. `test_pisot_damp_is_exact_in_qsqrt5_not_a_phase`: \(n=1\) is \((3-\sqrt{5})/2\), \(n=2\) is \((\sqrt{5}-1)/2\). `run_folded(..., damp=1/2)` raises `ValueError`. `m32_grover_unified.unified_search` ignores `pisot_n`. |
| 8 | Inexact complex phases \(e^{i\beta}\) (including the old 0.25° grid and Pisot-damped `cmath.exp`) are removed from the search path. Only canonical phases \(\pm 1\) are used. | PASS | Module docstring of `exact_folded_grover.py`. `FoldedGrover.step` takes no phase arguments. Small-lane statevector engine removed from `m32_grover_unified.py`. Documented limitation: with \(\pm 1\) phases, \(N=2,M=1\) never crosses \(\varphi^{-1}\) (\(p\) stays \(1/2\)). |
| 9 | `grep` / `rg` of the search path has no `math.sin`, `math.cos`, `math.sqrt`, `math.asin`, `math.pi`, `import cmath`, or `cmath.`. | PASS | `rg -n 'math\.(sin\|cos\|sqrt\|asin\|pi)\b\|import cmath\|cmath\.'` on the three search-path files returned no matches (exit 1) at 12:29 Europe/London. Enforced by `test_search_path_has_no_float_trig`. |
| 10 | Exact marked probability matches the old float closed form \(\sin^2((2k+1)\theta)\) to \(10^{-12}\). | PASS | `test_fold_matches_float_closed_form_to_1e12` on \((N,M)\in\{(16,1),(64,1),(256,3),(4096,1),(1024,5)\}\) at the exact peak \(k\). The reference `sin`/`asin` lives only in the test file, not on the search path. |
| 11 | Domain order is deterministic (Zeckendorf of `header[:76]`, Pisano \(\pi(32)=48\), Lucas). No RNG on the search path. Same header \(\Rightarrow\) same order. | PASS | `test_module_has_no_rng`, `test_search_is_deterministic`, `test_same_header_same_domain_order`. |
| 12 | `BitSlicedDomainOracle`: genesis nonce 2083236893 at lane 73 gives `phase_mask == 1<<73`; bit-exact vs `hashlib` on random 128-nonce domains (regtest `0x207fffff`, testnet `0x1f00ffff`, genesis `0x1d00ffff`) and on all 500 mainnet headers; zero false negatives. | PASS | `test_genesis_lane_73_phase_mask`, `test_phase_mask_bit_exact_under_difficulty`, `test_phase_mask_bit_exact_on_all_500_headers`. |
| 13 | Winner-in-window, 500 verified mainnet headers (blocks 975565–976064): 500/500 correct, 0 false positives. | PASS | Rerun 18 November 2026, 12:29–12:41 Europe/London, 8 workers. W=4096: 21.4 s, mean distinct hashed 2282.794 vs linear 2088.62, mean lane-compressions 4359.3459375 vs fair linear 3984.4475. W=65536: 241.5 s, 35039.054 vs 33283.756 hashed, 66801.18146875 vs 63450.1755 compressions. |
| 14 | Overfit check (window at `nonce+W`, winner not in the window): 0 found / 0 false positives on all 500 headers. | PASS | Same rerun. W=4096: 38.1 s, 4096 hashed, 7808.0 compressions \(=4096\times(61+61)/64\), matches linear. W=65536: 453.6 s, 65536 hashed, 124928.0 compressions \(=65536\times(61+61)/64\), matches linear. |
| 15 | Honest per-lane compression accounting. No sub-linear claim. Fair linear baseline uses the same midstate, cached rounds 0–2, and H2 early abort. | PASS | Include-winner means sit slightly *above* fair linear (about +375 compressions at W=4096, +3351 at W=65536) because whole Voronoi lanes are processed. Overfit non-hits all abort after the word-7 check, so both methods charge the same. Accounting is per-lane rounds/64, not one compression per bitsliced pass. |
| 16 | Lucas oracle marks only solutions; `pool_kernel_score` receives the real 32-byte folded state. | PASS | `test_lucas_enhanced_oracle_marks_only_solutions`, `test_pool_kernel_score_uses_real_folded_state`. |

## Tests

66 passed in 23.21 s, 18 November 2026, 12:42 Europe/London (UTC+0), `/workspace/cqvenv/bin/pytest -q` on:

- `tests/test_m32_grover_unified.py`
- `tests/test_grover_exact_scale.py`
- `tests/test_a_grover_exact.py`
- `tests/test_a_lucas_math.py`
- `tests/test_grover_nonce_boundary.py`

Exact-fold additions in `test_m32_grover_unified.py` include: no float trig on the search path, int/Fraction state, exact norm, exact \(\varphi^{-1}\) threshold, \(10^{-12}\) match vs the old float closed form, peak-by-stepping, and \(\mathbb{Q}(\sqrt{5})\) Pisot damping that is refused as a phase.

## Benchmarks (same 500 headers, midstate-fair)

**Winner in the window**

| W | Correct | Distinct nonces hashed (mean) | Linear nonces evaluated (mean) | Lane-compressions (mean) | Fair linear compressions (mean) | Wall time (8 workers) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 4,096 | 500/500 | 2,282.794 | 2,088.62 | 4,359.3459375 | 3,984.4475 | 21.4 s |
| 65,536 | 500/500 | 35,039.054 | 33,283.756 | 66,801.18146875 | 63,450.1755 | 241.5 s |

**Overfit** (window at `nonce+W`)

| W | Found | FP | Distinct hashed (mean) | Lane-compressions (mean) | Fair linear compressions (mean) | Wall time (8 workers) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 4,096 | 0/500 | 0 | 4,096 | 7,808.0 | 7,808.0 | 38.1 s |
| 65,536 | 0/500 | 0 | 65,536 | 124,928.0 | 124,928.0 | 453.6 s |

Mean lane-compressions on the include-winner runs are slightly above the fair linear scan. That is not a speedup and is not claimed as one.

## Not claimed

These still contain float trigonometry and are **not** part of the `m32_grover_unified` search path. They are recorded so this audit does not over-claim.

- `Intelligence/quantum_algorithms.py` `GroverSearch.optimal_iterations` still uses `math.asin` / `math.pi`. `GroverSearch.lucas_adaptive_iterations` still walks a float `cmath.exp` Pisot-damped iterate (the historical Lucas-fix helper). The unified search does not call either routine. The leftover unit test `test_lucas_adaptive_iterations_uses_pisot_phases` only covers that helper.
- The three `grover_exact_scale.py` copies still import `cmath` and still have float `math.sqrt` helpers for PHI / PSI / Binet documentation. `FoldedGrover` / `run_folded` / `optimal_iterations` / `analytical_success` are imported from `python_backend.exact_folded_grover` and no longer execute those helpers.
- Oracle marking remains classical SHA-256d (bit-sliced planes, then `hashlib` confirm). A real Grover oracle has to mark the same set; compressions are counted honestly.

## HYBA compliance (this path)

**Exact on the search path.** Two-amplitude fold over \(\mathbb{Q}\), Cassini identity, \(\varphi^{-1}\) comparison in \(\mathbb{Z}\), peak iteration by the exact recurrence, \(1-\lvert\psi\rvert^n\) in \(\mathbb{Q}(\sqrt{5})\) (not used as a phase), Zeckendorf / Pisano / Lucas domain order (deterministic, no RNG), bit-sliced SHA-256d `phase_mask` (bit-exact vs `hashlib`).

**Flagged.** Oracle marking is classical SHA-256d. Inexact \(e^{i\beta}\) Pisot / grid phases were removed from the search path rather than approximated.
