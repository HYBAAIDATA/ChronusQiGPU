# M_32 Grover unified — exact-arithmetic audit

Branch: `feat/m32-grover-unified` (PR #168).
Date: 18 November 2026, Europe/London (UTC+0).

Exact surface: `python_backend/exact_folded_grover.py`, `python_backend/m32_grover_unified.py`, `python_backend/bit_sliced_domain_oracle.py`, and the `turing_universal_quantum_computer/`, `Intelligence/`, and `millennium/` copies of `grover_exact_scale.py`. `FoldedGrover`, `optimal_iterations`, `analytical_success`, `run_folded`, `PHI`, `PSI`, `binet_lucas`, `binet_residual`, `pisot_damp`, and `convergence_bits` are imported from `python_backend.exact_folded_grover`. Z[phi] arithmetic reuses `kellogg.scales` (`Zphi` at `kellogg/scales.py:33`, `Zphi.sign` at line 80, `PHI` at line 115, `phi_power` at line 154, `binet_fold` at line 163, `pisot_drift` at line 180, `lucas` at line 144). Sibling ring: `lucas.algebra.ZPhi` (`lucas/algebra.py:21`) and `PHI` (line 85).

`GroverSearch.optimal_iterations` and `lucas_adaptive_iterations` in `Intelligence/quantum_algorithms.py` and `millennium/quantum_algorithms.py` delegate to the same exact stepper. (`turing_universal_quantum_computer/.../quantum_algorithms.py` has `optimal_iterations` only.)

Evidence below is only for items that actually passed.

## Checklist (all PASS)

| # | Item | Result | Evidence |
| --- | --- | --- | --- |
| 1 | Two-amplitude fold is exact. Uniform start scales out \(1/\sqrt{N}\); stored amplitudes start as integers \(a=b=1\). State types are `int` or `Fraction`, never `float`. | PASS | `FoldedGrover.uniform`; `test_fold_state_is_int_or_fraction_never_float`. |
| 2 | Diffusion uses rational coefficients: oracle \(a\to -a\), then \(m=(Ma+(N-M)b)/N\), \(a'=2m-a\), \(b'=2m-b\), with `Fraction`. | PASS | `FoldedGrover.step`. |
| 3 | Success probability \(p=Ma^2/N\) is an exact `Fraction`. | PASS | `FoldedGrover.marked_probability`. |
| 4 | Scaled Cassini identity: \(Ma^2+(N-M)b^2=N\) exactly; normalised witness is exactly \(1\). | PASS | `test_fold_norm_is_exactly_one_and_scaled_is_N`. |
| 5 | \(\varphi^{-1}\) threshold is the integer test \(p>(\sqrt{5}-1)/2\Leftrightarrow(2p+1)^2>5\) with \(2p+1>0\). | PASS | `exceeds_phi_inverse`; `test_threshold_is_exact_phi_inverse`. |
| 6 | Optimal \(k\) is found by stepping the exact recurrence until \(p\) stops increasing. No \(\pi\) / `asin`. | PASS | `optimal_iterations`. \(N=4096,M=1\) peaks at \(k=50\) (same as the old \(\lfloor\pi/(4\theta)\rfloor\)); \(N=16,M=1\to 3\); \(N=4,M=1\to 1\); \(N=16,M=4\to 1\). |
| 7 | Pisot damping \(1-\lvert\psi\rvert^n=1-\varphi^{-n}\) is exact in \(\mathrm{Z}[\varphi]\) (and equivalently \(\mathbb{Q}(\sqrt{5})\)), and is not used as a Grover phase. | PASS | `pisot_damp` returns `kellogg.scales.Zphi`. `run_folded` refuses any `damp` other than `None` or `1`. `test_pisot_damp_converges_to_one`, `test_pisot_phases_are_refused_by_the_exact_fold`. |
| 8 | Inexact complex phases \(e^{i\beta}\) (Pisot-damped `cmath.exp`, 0.25° grid) are removed from the search path. Only canonical phases \(\pm 1\) are used. | PASS | `FoldedGrover.step` takes no phase arguments. `lucas_adaptive_iterations` ignores `lucas_index` and returns the exact peak (`test_lucas_adaptive_iterations_matches_exact_peak`: \(k=50\) even for `lucas_index=3`, which used to be 53 under inexact phases). |
| 9 | Binet / PHI / PSI helpers in all three `grover_exact_scale.py` copies are exact \(\mathrm{Z}[\varphi]\) elements or integers, not floats. `cmath` and float PHI/PSI/Binet are gone. | PASS | `PHI = kellogg.scales.PHI` (\(\varphi\)); `PSI = PHI.conjugate()`; `binet_lucas(n)` is the integer \(L_n=\mathrm{tr}(\varphi^n)\); `binet_residual(n)=\varphi^{-n}=(\varphi-1)^n\); `convergence_bits(n)=\lfloor\log_2(\varphi^n)\rfloor` by comparing \(\varphi^n\) to \(2^k\) with `Zphi.sign`. `test_binet_residual_equals_pisot_drift`, `test_binet_residual_beyond_mantissa` (signed drift at \(n=76\) is the known limbs \((-5527939700884757, 3416454622906707)\)). |
| 10 | `grep` of the exact surface has no `math.sin` / `cos` / `sqrt` / `asin` / `pi` / `log` / `log2` / `exp`, no `import math`, and no `cmath`. | PASS | `rg` on the six exact-surface files returned no matches (exit 1) at 12:53 Europe/London. Enforced by `test_search_path_has_no_float_trig` and `test_touched_surface_has_no_float_trig`. `test_grover_search_iteration_methods_have_no_float_trig` greps the source of `optimal_iterations` and `lucas_adaptive_iterations` in the Intelligence and millennium copies: CLEAN. |
| 11 | Exact marked probability matches the old float closed form \(\sin^2((2k+1)\theta)\) to \(10^{-12}\). | PASS | `test_fold_matches_float_closed_form_to_1e12`. |
| 12 | Domain order is deterministic (Zeckendorf of `header[:76]`, Pisano \(\pi(32)=48\), Lucas). No RNG on the search path. | PASS | `test_module_has_no_rng`, `test_search_is_deterministic`, `test_same_header_same_domain_order`. |
| 13 | `BitSlicedDomainOracle`: genesis nonce 2083236893 at lane 73 gives `phase_mask == 1<<73`; bit-exact vs `hashlib` on random 128-nonce domains and on all 500 mainnet headers; zero false negatives. | PASS | `test_genesis_lane_73_phase_mask`, `test_phase_mask_bit_exact_under_difficulty`, `test_phase_mask_bit_exact_on_all_500_headers`. |
| 14 | Winner-in-window, 500 verified mainnet headers (blocks 975565–976064): 500/500 correct, 0 false positives. | PASS | Rerun 18 November 2026, 12:29–12:41 Europe/London, 8 workers (exact-fold path unchanged by this Z[phi] helper pass). W=4096: 21.4 s, mean distinct hashed 2282.794 vs linear 2088.62, mean lane-compressions 4359.3459375 vs fair linear 3984.4475. W=65536: 241.5 s, 35039.054 vs 33283.756 hashed, 66801.18146875 vs 63450.1755 compressions. |
| 15 | Overfit check (window at `nonce+W`): 0 found / 0 false positives on all 500 headers. | PASS | Same rerun. W=4096: 38.1 s, 4096 hashed, 7808.0 compressions, matches linear. W=65536: 453.6 s, 65536 hashed, 124928.0 compressions, matches linear. |
| 16 | Honest per-lane compression accounting. No sub-linear claim. | PASS | Include-winner means sit slightly *above* fair linear (~+375 at W=4096, ~+3351 at W=65536) because whole Voronoi lanes are processed. Overfit non-hits charge the same. |
| 17 | Lucas oracle marks only solutions; `pool_kernel_score` receives a real 32-byte folded-state pack. | PASS | `test_lucas_enhanced_oracle_marks_only_solutions`, `test_pool_kernel_score_uses_real_folded_state`. The 32-byte pack is four uint64 Fraction limbs, not floats. |

## Tests

75 passed in 22.60 s, 18 November 2026, 12:53 Europe/London (UTC+0), `/workspace/cqvenv/bin/pytest -q` on:

- `tests/test_m32_grover_unified.py`
- `tests/test_grover_exact_scale.py`
- `tests/test_a_grover_exact.py`
- `tests/test_a_lucas_math.py`
- `tests/test_grover_nonce_boundary.py`
- `tests/test_benchmark_grover_exact.py`

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

## Remaining facts (not claimed as exact quantum marking)

- **Oracle marking is classical SHA-256d** (bit-sliced planes, then `hashlib` confirm). A real Grover oracle has to mark the same set; compressions are counted honestly.
- **`QuantumGates`, QFT, QPE, and similar helpers** in the three `quantum_algorithms.py` copies still use `import math` for generic rotation angles (Hadamard/`T`/`R_k`/`Rx`/`Ry`/`Rz`, phase estimation, ansatz). Those routines are not on the folded Grover search path. `GroverSearch.optimal_iterations`, `lucas_adaptive_iterations`, and the analytical fold comparison inside `run()` are exact. File-level `rg` still reports 21 `math` hits in each copy of that file.
