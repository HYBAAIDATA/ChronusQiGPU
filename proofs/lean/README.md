# Guardian formal proofs (Lean 4)

Machine-checked lemmas for the parts of the Guardian blueprint that are
actually mathematics. Core Lean 4 only — no Mathlib dependency, so the
build needs nothing but the Lean toolchain.

## Build

```sh
cd proofs/lean
lake build
```

Toolchain: `leanprover/lean4:v4.34.1` (pinned in `lean-toolchain`;
`elan` resolves it automatically).

## What is proved

| File | Theorem | Statement |
|------|---------|-----------|
| `Guardian/Cassini.lean` | `cassini` | `lucas n ^ 2 - 5 * (fib n ^ 2) = 4 * sgn n` for **every** `n : Nat` — the Cassini–Hoggatt identity. Python's `CassiniVerifier.verify` recomputes this empirically per index; here it is proved once for all `n` by two-step induction. |
| `Guardian/Zeckendorf.lean` | `encodeIdxs_correct` | `decodeIdxs (encodeIdxs n) = n` — the greedy Zeckendorf expansion always sums back to its input (existence half of Zeckendorf's theorem). |
| `Guardian/Zeckendorf.lean` | `encodeFuel_nonAdjacent` | consecutive indices emitted by the greedy expansion differ by ≥ 2 — the non-adjacency condition `verify_non_adjacent` bit-checks in Python. |
| `Guardian/LedgerBound.lean` | `bound_check` | `decide (r ≤ b) = true ↔ r ≤ b` — the rank-bound check is a total decision procedure in both directions. |
| `Guardian/LedgerBound.lean` | `rank_bound_strict` | `fibN` strictly increases in index for `i ≥ 2` — distinct retained ranks imply distinct indices. |

## What is NOT proved (deliberately)

* **Zeckendorf uniqueness** — a deeper combinatorial theorem; the codec
  needs only existence + non-adjacency. Not claimed anywhere.
* **Yang-Mills mass gap, Navier-Stokes regularity, BSD rank bounds** —
  Millennium-prize problems. The repo's discrete analogues are finite,
  computable objects with honest labels in
  `l_hras/foundations/`; they are not stated as instances of the
  continuum theorems.
* **`F4` naming** — the code's `F4` is the cyclotomic field
  `Q(ζ₈) = Q(√2) + iQ(√2)`, not the exceptional Lie group. Machine-
  checked facts about the six-intelligence joint state live in
  `l_hras/foundations/entanglement.py` (exact partial trace + Meyer–
  Wallach Q over `Q(ζ₈)`), not here.
