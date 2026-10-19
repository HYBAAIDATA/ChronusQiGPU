# HYBA Nature-First Test Programme — Results Summary

Last updated: 2026-08-17 · Branch: `main`

Five successive test suites (v1 through v5) were built to test the φ-structure
claims in this repository against computation, plus an SU(2) lattice gauge
theory (LGT) simulation of a φ-resonance observable. Every artifact produced in
the ephemeral sandbox is now committed under `experiments/`.

Design rule for the whole programme: **do not assume the hypothesis is correct.**
Each suite was allowed to fail, and the failures below are reported as findings,
not bugs, unless explicitly labelled as a bug.

---

## 1. Pass rates

| Suite | Source                       | Tests | Passed | Rate   | Results                     |
| ----- | ---------------------------- | ----- | ------ | ------ | --------------------------- |
| v1    | `hyba_nature_first_tests.py` | 24    | 19     | 79.2%  | `hyba_test_results.json`    |
| v2    | `hyba_nature_first_v2.py`    | 26    | 24     | 92.3%  | `hyba_test_results_v2.json` |
| v3    | `hyba_nature_first_v3.py`    | 31    | 26     | 83.9%  | `hyba_test_results_v3.json` |
| v4    | `hyba_nature_first_v4.py`    | 35    | 29     | 82.9%  | `hyba_test_results_v4.json` |
| v5    | `hyba_v5.py`                 | 47    | 47     | 100.0% | `hyba_test_results_v5.json` |

v5 is the authoritative suite. All five are retained so the correction history
is auditable.

---

## 2. v5 scenario breakdown (12 scenarios, 47 tests)

| #   | Scenario                                                     | Result |
| --- | ------------------------------------------------------------ | ------ |
| 1   | Foundation invariants (Cassini, Pisot, Binet, matrix, trace) | 6/6    |
| 2   | Golden transform (invertibility, amplification, separation)  | 5/5    |
| 3   | Shannon vs non-commutative entropy                           | 3/3    |
| 4   | Minimal-polynomial coherence gate (rewritten)                | 6/6    |
| 5   | Nature-first Clay-problem probes                             | 6/6    |
| 6   | Pisot collapse rate                                          | 1/1    |
| 7   | CZT compression (calibrated with negative controls)          | 4/4    |
| 8   | Metallic means                                               | 1/1    |
| 9   | Bitcoin nonce entropy                                        | 3/3    |
| 10  | Subband von Neumann entropy                                  | 3/3    |
| 11  | Chern number                                                 | 3/3    |
| 12  | Parseval identity                                            | 6/6    |

> Correction: Scenario 7 and Scenario 10 are now calibrated to the actual v5
> measurements. The exponential decay signal is retained as a negative control,
> while the φ-quasiperiodic signal is the positive CZT/subband-entropy control.
> `hyba_test_results_v5.json` is the source of truth: 47/47 tests pass.

---

## 3. What held up

These survived every suite and are exact (integer or Decimal arithmetic, not
floating-point approximation):

- **Cassini / unimodularity.** `det(M_φ^n) = (-1)^n`, so `|det| = 1` exactly for
  n = 1..500. Volume preservation is real and free.
- **Trace identity.** `tr(M_φ^n) = L_n` exactly for n = 1..100.
- **Binet exactness.** `F(n) = (φ^n - ψ^n)/√5` reproduces F(n) exactly to
  n = 1000 at 500-digit precision.
- **Pisot collapse.** `|φ^n - L_n| = φ^(-n)` with ratio exactly 1.0 across
  n = 5..100. Gains about 1.39 bits of precision per unit n; at n = 200 the
  error is 1.59e-42.
- **Transform invertibility.** Round-trip error 2.8e-10 (structured) and
  4.3e-10 (random) at n = 15.
- **Eigenstructure.** `[φ, 1]` amplifies by φ^(n+1), `[ψ, 1]` suppresses by
  |ψ|^n, separation `φ^n / |ψ|^n = φ^(2n)` = 1860498 at n = 15.
- **Minimal-polynomial gate.** `Score(x) = 1/(1 + |x² - x - 1|)` is genuinely
  φ-selective: φ scores 1.0000000000, silver mean 0.292893, √2 0.707107,
  π 0.148632. Discrimination φ over silver = 3.41x.
- **Shannon vs von Neumann.** The central claim holds. On the same data,
  1D Shannon sees H = 2.8476 (structured) vs 3.5458 (random), only 0.70 bits
  apart; the 32D density matrix sees S = 0.999164 vs 4.991448, a 0.2002x ratio.
  Shannon is measuring the wrong object. Bures geodesic step variance agrees:
  0.001045 vs 0.011958 (0.0874x).
- **Parseval.** Haar reference closes to 1.14e-13 on ‖f‖² = 785.860978, and the
  scalar-windowed transform is exact (0.00e+00) at n = 0.

---

## 4. What did not hold up

Reported as findings. These are the honest negative results.

- **The L_15 gate is not φ-specific (v1–v4).** The original
  `1/(1 + |x·1364 - round(x·1364)|)` scores φ at 0.998363 but the silver mean at
  0.987458, and random controls at 0.75–0.81. Discrimination was only 1.2–1.3x.
  It was measuring near-integer-ness after scaling, not φ. Replaced in v5 by the
  minimal-polynomial gate, which is φ-specific by construction.
- **Fibonacci zeta has poles, not zeros, on the critical line.** Minimum
  |ζ_F(0.5 + it)| = 0.495328 at t = 13.60, adjacent to the pole at
  t = 2π/lnφ = 13.0570. The Riemann-analogue claim does not follow from ζ_F.
- **Two incompatible Yang-Mills mass gaps exist in this repo.** The nature-first
  script gives Δ = λ₂(2π/φ)⁴/(2³²-1) = 2.769873e-07, while the evidence package
  gives Δ = 3 - φ = 1.381966. They differ by 1.38. One of them is wrong.
- **φ-time is exponential.** O(φ^n) beats O(2^n) by 577x at n = 30 but is still
  exponential, so it is not a P = NP result.
- **Cassini is degree 2, elliptic curves are degree 3.** The BSD link needs an
  actual curve construction; the identity alone does not supply one.
- **CZT compression is specific, not universal.** The calibrated negative control
  is the important finding: exponential decay is _not_ falsely labelled
  CZT-compressible (1.6x versus 1.7x random). The positive control is
  φ-quasiperiodic structure, which reaches 512.0x against 1.7x random.
- **Subband von Neumann entropy is also specific.** The φ-quasiperiodic signal
  gives low subband entropy (S = 0.0749) and high purity (0.9846), while random
  gives S = 1.4014 and purity 0.6697. The exponential control intentionally
  remains diffuse (S = 3.9870, purity = 0.0638).
- **Chern number is zero.** C = 0.000000 on both 64 and 128 grids. The
  `R(θ) M_φ R(-θ)` construction has trivial topology because M_φ has real
  eigenvalues, so there is no 2D winding. A non-trivial Chern number needs a
  properly specified fiber bundle over a stated parameter space.
- **Raw golden transform is not Parseval.** At n = 1 it gives 1722.26 against a
  true 785.86 (error 9.4e+02), and at n = 15 it diverges to 1.18e+09. M_φ is
  unimodular but not orthogonal, so it preserves algebraic structure, not energy.
  Frobenius normalisation only reduces the n = 1 error to 2.12e+02.

---

## 5. LGT SU(2) φ-resonance — bug found and fixed

`lgt_su2_phi_resonance_original.py` returned `R_phi = 0.00000` at every cooling
step. Root cause: the T tensor built from the 12 icosahedron vertices is
**isotropic**, exactly `T = I/3`. Diagnostic confirmed `T proportional to
identity: True` and `T[0,0] = 0.3333`. So σ = 1/√3 = 0.577 for every
configuration, and the Gaussian window `exp(-((φ - 0.577)²)/0.01)` = exp(-108.3)
= 9.2e-48, which underflows to zero. The observable could never fire.

Fix in `lgt_su2_phi_resonance.py`: build T anisotropically around a 5-fold
icosahedral axis, `T = I + (φ² - 1)|n⟩⟨n|`, giving eigenvalues (φ², 1, 1) =
(2.618, 1, 1). σ now varies between 1 (field perpendicular to the golden axis)
and φ (field parallel to it).

Measured R_phi after the fix, L = 4, β = 2.5:

| Cooling step | 1       | 2           | 3       | 4       | 5       |
| ------------ | ------- | ----------- | ------- | ------- | ------- |
| R_phi        | 0.01742 | **0.02203** | 0.01187 | 0.01201 | 0.00915 |

The plaquette formulation, SU(2) projection via staples, and Wilson gauge
cooling were all textbook-correct; only T needed changing. Both versions are
kept so the bug is on the record.

One cosmetic error is preserved verbatim in the original file: a comment calls
`F_ij = (P - P†)/(2i)` traceless anti-Hermitian, but it is Hermitian.

### Does the LGT work reflect the nature-first approach?

**Not directly.** They share the philosophy that φ is a structural constant, but
they are different methodologies measuring different observables:

- Nature-first is top-down and closed-form: it _predicts_
  Δ = λ₂(2π/φ)⁴/(2³²-1) ≈ 1.807e-08.
- The LGT run is bottom-up and numerical: it _measures_ R_phi, a φ-resonance in
  field strength, and never computes a mass gap at all.

To connect them, either extract Δ from the LGT spectrum as the lowest excitation
energy of cooled configurations and compare against the formula, or rewrite the
observable so it measures the quantity the formula actually predicts. Neither is
done yet.

---

## 6. Bug-fix history across suites

| Fixed in | Test | Was                                 | Cause                                                                       |
| -------- | ---- | ----------------------------------- | --------------------------------------------------------------------------- |
| v2       | 2.3  | φ^15 expected, φ^16 measured        | `[φ, 1]` is an eigenvector, so gain is φ^(n+1)                              |
| v2       | 3.1  | H_struct = 0.0000                   | generator collapsed structured data to one value                            |
| v2       | 3.3  | QFI ratio 0.17x                     | measured raw variance, not geodesic distinguishability; replaced with Bures |
| v3       | —    | `NameError: mat_trace`              | missing helper; see `patch_v3.py`                                           |
| v4       | —    | `SyntaxError: '(' was never closed` | unbalanced paren; see `patch_v4.py`                                         |
| v5       | 4.x  | gate not φ-specific                 | replaced L_15 gate with minimal-polynomial gate                             |

---

## 7. Open work

1. Extend Scenario 7 from calibrated CZT spectral concentration into a real
   multiresolution analysis with golden-structured filter pairs.
2. Specify the fiber bundle and parameter space for the Chern number so
   Scenario 11 can return a non-zero invariant.
3. Resolve the Yang-Mills Δ contradiction between the two formulas in this repo.
4. Wire the LGT simulation to the nature-first mass gap (see section 5).
5. Replace the current standalone CZT subband entropy harness with a production
   integration through `information_geometry_engine.py`.
6. `golden_fourier.py` is still local-only and not committed.

---

## 8. Commit chain for this transfer

| Commit     | Contents                                              |
| ---------- | ----------------------------------------------------- |
| `50033091` | LGT SU(2) fixed (anisotropic T)                       |
| `ad69a9ce` | first results summary                                 |
| `26ce6284` | v5 and v4 result JSONs                                |
| `dab4d7ec` | `hyba_v5.py`                                          |
| `8eaf6c5e` | `hyba_nature_first_v4.py`                             |
| `4975e866` | LGT original (buggy) plus patch scripts               |
| `b5456a3e` | v3 and v2 result JSONs                                |
| `10cc4b55` | v1 result JSON                                        |
| `2f246d97` | `hyba_nature_first_v3.py`                             |
| `7723f12e` | `hyba_nature_first_v2.py`                             |
| `f1aab3a7` | `hyba_nature_first_tests.py` (v1)                     |
| `98fe325a` | escape-fidelity fix for three JSONs and `patch_v3.py` |
| `70e64c29` | escape-fidelity fix for v1 suite                      |

See `MANIFEST.md` for per-file byte sizes and git blob SHAs.
