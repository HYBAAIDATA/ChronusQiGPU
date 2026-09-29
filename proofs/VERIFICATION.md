# Verified vs. empirical — the manifest

Answers the consortium demand for formal verification ("Lean 4, Coq, or
Isabelle/HOL ... machine-checked lemmas") by separating what this repo
has machine-checked from what it only ever measures.

## Machine-checked (Lean 4, `proofs/lean`, `lake build` green)

| Claim site in Python | Theorem | Status |
|---|---|---|
| `aethel.cassini.CassiniVerifier.verify` — recomputes `L_n² − 5F_n² = 4(−1)ⁿ` per index | `Guardian.Cassini.cassini` | proved ∀ n |
| `aethel.zeckendorf` codec round-trip | `Guardian.Zeckendorf.encodeIdxs_correct` | proved ∀ n |
| `aethel.zeckendorf` non-adjacency bit check | `Guardian.Zeckendorf.encodeFuel_nonAdjacent` | proved ∀ n |
| `r ≤ bound` ledger-style gates | `Guardian.LedgerBound.bound_check`, `rank_bound_strict` | proved ∀ r b i j |

## Exactly computable — measured, not assumed (`l_hras/foundations/`)

| Demand | Artifact | What it honestly says |
|---|---|---|
| 1. Gottesman–Knill | `complexity.py` | gate set is Clifford+T+Toffoli → **universal, not Clifford**; GK does not apply. Memory is exponential in qubits, bounded by a fail-closed cap (`MLA1517_MAX_AMPLITUDES`, default 2²⁰); the six-intelligence joint path never superposes — it is classically simulable by construction. |
| 2. PDE functor | `gauge.py` | discrete U(1) lattice gauge field on the event graph; plaquette-holonomy field strength; `λ₂` graph-Laplacian spectral gap — labelled "finite-volume gap, not the continuum SU(N) mass gap". Discrete flow field with divergence/enstrophy + finite-time Lyapunov — labelled "not global NS regularity". |
| 3. F4 / 6-partite | `entanglement.py` | `F4` = `Q(ζ₈)` cyclotomic field, NOT the Lie group. Real multipartite monotone: exact Meyer–Wallach `Q` + per-party Schmidt ranks in `Q(ζ₈)`. Measured: joint state is a basis product → `Q = 0`, no multipartite entanglement exists to witness. |
| 4. Continuous→discrete | `quantization.py` | fold is a diffeomorphism (float64) but declared `is_isometry: False` (Jacobian κ measured); certificate quantizer declared `is_bijective: False, many_to_one: True` with error bound `1/(2φ¹⁵)`. |

## Empirical only (honest labels kept)

* Detection/refusal rates — `TARGET` in `l_hras/claims.py`, measured on
  declared simulations; never an absolute.
* `toe/poincare_yangmills.gauge_gap` — documented in-repo as "the first
  positive eigenvalue of the 2I quantum-group Laplacian; not the
  continuum Yang–Mills mass gap".
* Zeckendorf **uniqueness** — not proved in Lean and not claimed.

## Reproduce

```sh
# proofs
cd proofs/lean && lake build        # Lean 4.34.1, no Mathlib
# foundations reports
python -m pytest tests/test_l_hras_foundations.py -q
```
