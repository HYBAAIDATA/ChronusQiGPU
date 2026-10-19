# HYBA Nature-First Verification Report — v4 (Measured)

- **Suite:** `nature_first_evidence/suite_v4.py`
- **Executed:** `python nature_first_evidence/suite_v4.py` (exit code 0)
- **Environment:** Python 3.12.10, Windows
- **Date:** 2026-08-16
- **Determinism:** all scenarios use fixed seeds → the run is byte-for-byte reproducible.

> Per `docs/governance/VERITAS.md` Rule 0, this document reports **only what the suite actually
> measures**. Where the numbers contradict a previously circulated draft report,
> the discrepancy is laid out explicitly (Section 4).

## 1. Headline — measured

| Metric      | Value     |
| ----------- | --------- |
| Total tests | 35        |
| Passed      | 29        |
| Failed      | 6         |
| Pass rate   | **82.9%** |

The six failures are **all in Scenario 7** (energy concentration / φ-fold compression).

## 2. What the suite genuinely establishes (passed, exact)

| #               | Test                                                                                                                              | Measured                                     |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| 1.1             | Cassini det(M^n) = (-1)^n, n=1..200                                                                                               | exact                                        |
| 1.2             | volume preservation \|det(M^n)\| = 1, n=1..200                                                                                    | exact                                        |
| 1.3             | Pisot \|φ^n − L_n\| = φ^(−n), n=5..100                                                                                            | ratio 1.0                                    |
| 1.4             | Binet F(n) = (φ^n − ψ^n)/√5, n=0..1000                                                                                            | exact                                        |
| 1.5             | M^a·M^b = M^(a+b)                                                                                                                 | exact                                        |
| 1.6             | tr(M^n) = L_n, n=1..100                                                                                                           | exact                                        |
| 2.1–2.2         | Golden transform round-trip (struct/random)                                                                                       | max err ~1e-10                               |
| 2.3–2.5         | [φ,1] amplified to φ^16=2207.0; [ψ,1] suppressed to 7.33e-4                                                                       | exact to float                               |
| 3.1–3.3         | Shannon-1D vs vN-32D vs geodesic variance on synthetic generating sets                                                            | H 2.85 vs 3.55; S 0.999 vs 4.991; var 0.087x |
| 4.1/4.2/4.4/4.5 | coherence-gate behaviour on Fibonacci/Lucas ratios and Pisot table                                                                | means 0.9566–0.9569                          |
| 9.1–9.3         | SHA-256 "nonce" vectors: both 1D Shannon (4.99 bits) and 32D vN (4.99) say uniform; φ-structured synth data collapses vN to 0.999 | reproducible                                 |

These are exact identities or deterministic measurements on constructed data —
**solid and reproducible** as stated.

## 3. Failures (measured) — Scenario 7: energy concentration / compression

| #   | Assertion                        | Threshold | Measured                                     |
| --- | -------------------------------- | --------- | -------------------------------------------- |
| 7.1 | sine concentrates ≥50% in top-64 | >0.5      | **0.179 (17.9%)**                            |
| 7.2 | random stays <20%                | <0.2      | **0.360 (36.0%)**                            |
| 7.3 | φ-aligned ≥50%                   | >0.5      | **0.178 (17.8%)**                            |
| 7.4 | structured > 2× random           | —         | sine 0.179 vs random 0.360 → **0.5×**        |
| 7.5 | compression(90%): sine > random  | —         | sine **1.8×** (581) vs random **2.3×** (439) |

Interpretation: the applied per-pair 2×2 golden transform does **not** sparsify;
in the measured regime random data concentrates more energy in its top-64
coefficients than smooth sine data. The "compression" claim as stated is not
supported by this code.

## 4. Coherence gate behaviour (Scenario 4 — measured)

| Number        | Coherence    | Claimed class |
| ------------- | ------------ | ------------- |
| φ (golden)    | 0.998363     | Pisot         |
| 1+√2 (silver) | 0.987458     | Pisot         |
| √2            | **0.987458** | non-Pisot     |
| π             | 0.883096     | non-Pisot     |

The gate scores √2 **as high as** the silver Pisot number → it is a Pisot
companion-proximity detector, **not** a φ-specific resonance gate. Test 4.3
(discrimination > 1.2×) fails at the measured **1.17×**.

## 5. Scenario 5 ("Millennium" labels) — what actually runs

| #   | Label                | What the code checks                                | Hardcoded?                    |
| --- | -------------------- | --------------------------------------------------- | ----------------------------- |
| 5.1 | Yang-Mills           | prints a formula; compares two constants            | **passes trivially (`True`)** |
| 5.2 | Riemann ("fib zeta") | min \|ζ_F(0.5+it)\| over t∈[0,25] (0.495 at t=13.6) | no                            |
| 5.3 | P vs NP              | prints φ/2<1 (`True`)                               | **hardcoded**                 |
| 5.4 | Navier-Stokes        | det(M^n)=±1 identity                                | no                            |
| 5.5 | BSD                  | Cassini identity (degree 2)                         | no                            |
| 5.6 | Hodge                | det(M)=−1                                           | no                            |

Passing 5.4/5.5/5.6 verifies linear-algebra identities about M=[[1,1],[1,0]].
It does **not** demonstrate the Yang-Mills mass gap, the Riemann Hypothesis,
P≠NP, global regularity of Navier–Stokes, the Birch–Swinnerton-Dyer rank
conjecture, or any Hodge conjecture statement.

## 6. Reconciliation vs. the circulated "v3 corrected" draft report (Rule 0)

The draft claimed **"35/35 · Grade A+ · Q.E.D."** and headline metrics that do
**not** exist in the executed code. Measured reality, side by side:

| Draft claim                           | Present in code?                               | Measured                          |
| ------------------------------------- | ---------------------------------------------- | --------------------------------- |
| 35/35 (100%)                          | —                                              | **29/35 (82.9%)**                 |
| coherence discrimination 333×         | No (gate is the same `1/(1+\|nL−round(nL)\|)`) | **1.17×** (4.3 FAIL)              |
| "√2 score 0.003, φ 1.000"             | Not implemented                                | √2 = **0.987458** (≈ φ)           |
| 256× compression / 89.7% top-k energy | No such folding in code                        | 17.9% sine; **random 36.0%** wins |
| QFI = φ² (Hodge)                      | No QFI computation anywhere                    | det(M)=−1 identity only           |
| BSD rank=1 via φ-elliptic curve       | No EC rank computation                         | Cassini identity only             |
| Yang-Mills Δ = 1.807e-8 "solved"      | 5.1 passes `True`; prints 2.769873e-07         | not a gauge-theory argument       |
| "100,000× memory", "Nobel / Fields"   | No supporting measurement                      | n/a                               |

These draft claims are **not reproducible from `suite_v4.py`**. Under Veritas
Rule 0, they must not be presented as verified results until the underlying code
implements and measures them.

## 7. What the v4 suite is genuinely good for

- Exact verification of Fibonacci/Lucas/matrix-power identities (Scenario 1) —
  fully exact, ideal as foundational invariants (cf. the repo's
  `golden_algebra_basis.py`).
- Information-geometry _demonstration engine_: given a φ-constructed generating
  set, Shannon-1D ≈ random while von-Neumann collapses — an internally
  consistent metric story for constructed data.
- A sharp **counter-finding**: the per-pair 2×2 golden transform on 1024-pt real
  sequences (Scenario 7) does **not** concentrate energy, and random data
  concentrates _more_. Any future compression claim must beat this with a real
  code + measurement, not a renamed assertion.

## 8. Reproducibility notes

- I reconstructed `suite_v4.py` from the pasted draft **verbatim** except:
  1. output path `"/data/hyba_test_results_v4.json"` → `results/` (the original
     path does not exist on this machine);
  2. console glyphs rendered as ASCII (cosmetic only);
  3. a spelling fix for the helper name `compression_ratio_90` (no logic change);
  4. dropped one dead expression (`... if False else 0`) in Scenario 9 — a
     no-op that never executes (the measured branch is identical).
- All seeds are fixed → reruns should reproduce the exact JSON in
  `results/hyba_test_results_v4.json`.

```bash
# reproduce
python nature_first_evidence/suite_v4.py
# serve the evidence
pip install fastapi uvicorn httpx
uvicorn nature_first_evidence.api:app --port 8300
```

---

_End of measured verification. Summary: 35 tests, 29 pass, 6 fail (82.9%).
Draft-report headline claims not reproduced._
