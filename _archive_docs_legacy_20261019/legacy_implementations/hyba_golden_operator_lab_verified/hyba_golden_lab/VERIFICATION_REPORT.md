# Independent Verification Report — HYBA Golden Operator Laboratory

**Scope:** This report documents an independent re-run of every check and
benchmark in this package, on 2026-08-20, from a clean environment
(Python 3, NumPy 2.4.4, SciPy 1.17.1, no network access). No source files
were modified before running. Numbers below are copied directly from
program output, not from `FOUNDATIONS.md` or `README.md`.

The purpose is to state plainly what is confirmed, what is a genuine
open/measured result (not proven either way), and where the existing
docs slightly overreach the data — so this package can be trusted at
face value rather than taken on faith.

## 1. Identity and fidelity battery — `04_benchmarks/test_fidelity.py`

All 24 checks passed, machine-precision or exact:

- Golden-ratio identities (Binet, Cassini, Lucas trace/det, doubling): exact or ~1e-11 max error.
- Unitarity of H, X, Y, Z, CNOT, QFT4, and a golden-angle rotation: confirmed.
- QFT inversion fidelity F = 1; Grover found the marked state with P* = 0.9453; MPS reconstruction of a GHZ state F = 1.0000.
- Zeckendorf uniqueness, kernel positive-semi-definiteness (min eigenvalue -1.06e-15, i.e. zero within float noise): confirmed.

**Verdict: the "frozen mathematical core" claims are correct.** This part of the package is exact linear algebra, not simulation dressed up as more than it is, and it verifies independently of the authors' own test run.

## 2. Braid group and homology regression — `04_benchmarks/test_regression.py`

All 18 checks passed:

- Braid relations (σᵢσᵢ₊₁σᵢ = σᵢ₊₁σᵢσᵢ₊₁) and far commutation, n = 2..6: errors 0 to ~1e-15.
- Norm preservation under braid words: exact to 10 decimal places shown.
- Vietoris–Rips Betti numbers for a circle, two disjoint blobs, and a filled disk matched known topological answers exactly.

**Verdict: confirmed as claimed.**

## 3. Benchmark battery — `04_benchmarks/run_lab.py` (36 experiments)

This is the part making a genuine, appropriately-hedged research claim
("may concentrate probability mass"), not a proof. Independent numbers:

| Experiment | N_eff | Note |
|---|---|---|
| QAOA baseline (uniform angles) | 8.00 | did not reach the paper's convergence threshold |
| QAOA Pisot×Lucas angles | 4.63 | matches FOUNDATIONS.md's stated 8.00 → 4.63 |
| Grover, baseline | 4.33 | — |
| Grover, folded through M³ | 7.66 | **increases** N_eff — confirms the doc's own admission that this fold spreads rather than concentrates |
| QFT exact vs. Pisano-folded | 1.00 / 1.00 | identical; folding here is a representation change, as documented |

**Ablation (phi_only, lucas_only, fibonacci_only, Mⁿ, phi_psi_project, all_combined, random_matrix control):**
N_eff ranged narrowly from 4.03 to 5.04 across all seven variants, including the random-matrix control at 4.61. The docs state "the random-matrix control does not concentrate" — that's technically true (it's not the lowest value) but the effect size here is modest, not dramatic: random_matrix sits in the middle of the pack, not clearly separated from the golden-family variants. **This is the one place I'd soften the language** — the hypothesis is supported directionally but the ablation alone is not strong evidence of a large, structure-specific effect. The QAOA result (8.00 → 4.63) is the more convincing data point in this battery.

**Adversarial tests:** N_eff stayed essentially flat (7.58 → 7.58, 8.00 → 7.58) under M⁸ folding on both aligned and unstructured inputs — consistent with the doc's claim that the effect is structure-dependent and doesn't fire indiscriminately.

## 4. What this package does NOT claim, confirmed by inspection

- No SHA256d, hashrate, nonce search, or mining code exists anywhere in this package. Confirmed by full-text search — the mining disclaimer in `README.md` is accurate, not just asserted.
- No hardware quantum device is required or referenced; every "quantum" object (Hilbert space, unitary, measurement) is standard linear algebra run classically, which the package states explicitly.
- No O(I) / complexity-class claims are made; the complexity experiments report raw measured coherence-rank counts (8, 21, 55, 144 for n=6,8,10,12) without asserting a big-O trend.

## Summary

The frozen mathematical core (Section 1–2) is exact and independently reproducible — this is solid. The exploratory benchmark claims (Section 3) are honestly hedged in the existing docs and mostly hold up under re-run, with one caveat: the ablation control margin is real but narrow, and readers should treat the QAOA result as the strongest single piece of evidence for the "golden eigenbasis concentrates probability" hypothesis, not the ablation table alone.
