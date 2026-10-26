# Verified Discovery Register

**Constitutional basis:** doctrine §5 (truth classification), §7 (implementation-first), §9 (negative-result preservation), §11 (benchmark integrity).

Every entry was established by independent execution — Veritas Rule 0: run, don't trust. Each entry lists its proof artifact. Entries marked **unit-tested** are gated in CI on every push.

**Register date:** 2026-08-16

---

## D1 — Yang-Mills / Lucas-15 identity (exact)

**Statement:** S_YM(2^32 − 1) = 6·(2π/φ)^4 = 1364.332305721577541.

**Proof:** 2^32 − 1 = 0xFFFFFFFF — all four gauge bytes are 0xFF, so every connection coefficient equals 2π/φ; all difference terms (a_i − a_j)² vanish and each of the C(4,2) = 6 pairs contributes exactly (2π/φ)^4. The value sits 0.3323 above Lucas-15 (1364) — a named near-identity of the curvature table.

**Precision note:** exact in ℝ; the precomputed-table implementation carries ~4.5×10⁻¹³ float64 rounding.

**Truth class:** unit-tested — `python_backend/tests/test_extended_information_theory.py::TestYangMillsAction::test_nonce_max_uint32_lucas_identity`.

---

## D2 — M_32 connectivity threshold

**Statement:** the cos(π/5) adjacency threshold fragments the M_32 manifold into **20 connected components** (Fiedler λ₂ = 0). The cos(2π/5) icosahedral-symmetry threshold yields a **single connected component** (192 edges, mean degree 12) with exactly one zero Laplacian eigenvalue and **λ₂ = 5.231796**. (k-NN k=5 alternative: also connected, λ₂ = 1.346706.)

**Disposition:** fixed in `phi_grover_v4.py` (`COS_2PI5`); regression-gated in `python_backend/tests/test_phi_strategy_search_invariants.py::TestM32Connectivity` (connected graph, single zero mode, λ₂ known-answer).

**Truth class:** unit-tested.

---

## D3 — SLD-QFI implementation boundary

**Statement:** SLD-QFI implementations that shrink the eigenvalue array without shrinking the eigenvector array misalign the eigenbasis indices and collapse the pure-state result to ~0 (measured: 1.6×10⁻⁵⁹ vs analytic 4.0×10⁻⁶ — 100% deviation). Keeping full-length arrays with the threshold applied inside the element loop matches analytic ground truth on pure states **and** mixed states (qubit rotation: F = r² = 0.64 exact). A preceding Hilbert–Schmidt approximation (4·Tr(dρ²)) was also shown to track the perturbation knob ε (value = 8ε²) rather than any geometry.

**Disposition:** correctly-indexed implementation committed and verified against analytic ground truth in `python_backend/tests/test_extended_information_theory.py::TestQuantumFisherInformation`; the `np.vdot` double-conjugation defect is regression-tested (`test_orthogonalization_uses_single_conjugation`).

**Truth class:** unit-tested.

---

## D4 — Cassini invariants require exact arithmetic

**Statement:** det(M_φ^n) = (−1)^n holds exactly in integer arithmetic (verified n=1..30). In float64, `np.linalg.det(np.linalg.matrix_power(...))` drifts to **0.999992405355443 at n = 30** — hyperbolic growth (entries ~F_n) amplifies rounding. Invariants over hyperbolic maps must be evaluated in exact arithmetic.

**Truth class:** unit-tested — `TestSymplecticInvariant::test_cassini_law_all_powers` (object-dtype integer arithmetic).

---

## D5 — Terminology: unimodular, not symplectic

**Statement:** det(M_φ) = −1 ⇒ volume-preserving (|det| = 1; Liouville) **and** orientation-reversing. Symplectic matrices have det = +1; M_φ is therefore unimodular but not symplectic. "Symplectic invariant" phrasing is withdrawn in favor of "unimodular (orientation-reversing)".

**Truth class:** unit-tested + documentation.

---

## D6 — NEGATIVE RESULT: the "99.9999% φ¹⁵ precision" metric is vacuous (§9)

**Statement:** the metric (1 − min_k |n − k·φ^15| / n) × 100 is bounded below by ~99.99% for any 10⁹-scale integer, because the worst-case distance to a φ^15 lattice point is φ^15/2 ≈ 682 while nonces are ~4×10⁹. Executed comparison against the repo corpus artifact (`python_backend/phi15_nonces.csv`, 50 nonces, blocks 962562–962611):

| Sample                  | Mean precision | Min precision | Mean diff |
| ----------------------- | -------------- | ------------- | --------- |
| Real corpus             | 99.999915%     | 99.998663%    | 345.69    |
| Random uniform [0, 2³²) | 99.999936%     | 99.999080%    | 313.06    |
| Random in corpus range  | 99.999969%     | 99.999718%    | 359.14    |

Random data scores at or **above** the real corpus — the metric has zero separation from chance. (The source document's own null column agrees: random 99.999793% vs observed 99.999960%; p = 0.13; Z = −1.12 — not significant.)

**Disposition:** withdrawn from claims. `phi_grover_v4.py::analyse()` already refuses to report this metric ("vacuously-true"); this entry preserves the negative result per §9.

**Truth class:** negative-result (real-data-tested corpus + synthetic-benchmarked null).

---

## D7 — Shannon detects concentration; it cannot classify it

**Statement:** Shannon entropy drops 5.0 → 0.921928 bits (81.6%) on the attractor distribution — the "1D projection appears uniform" framing is **withdrawn** (it was contradicted by the script's own output). Bounded replacement: Shannon detects concentration perfectly well; what it cannot do is distinguish **geometric** (geodesic) from **statistical** concentration.

**Truth class:** unit-tested — `TestShannonEntropy`, `TestVonNeumannEntropy`.
