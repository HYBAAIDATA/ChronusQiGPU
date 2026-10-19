# Lemma: Lucas-Bounded Path Counts Give Polynomial Verification

**Status:** proof sketch under review. `theorem_proven: false` — this document asserts a bound used by the substrate, not a resolved complexity conjecture.

**Scope discipline (binding):** this lemma applies to the two-state golden adjacency structure `Q = [[1, 1], [1, 0]]` only. Extension to richer graphs is a **separate, unproven claim** and is treated as such. Any code, any doc, any agent that uses this lemma outside its scope is using it wrong.

---

## 1. Statement

Let `Q = [[1, 1], [1, 0]]` be the golden-section matrix over the integers. For every `n ≥ 1`:

```
tr(Q^n) = L_n
```

where `L_n` is the n-th Lucas number (`L_0 = 2`, `L_1 = 1`, `L_n = L_{n-1} + L_{n-2}`).

**Consequence used by the substrate:** the number of closed length-`n` walks on the two-state golden graph — equivalently the n-th trace of `Q` — is a Lucas number, and is therefore computable in `O(log n)` exact integer operations by fast doubling, rather than by enumerating ~`φ^n` walks.

---

## 2. Proof sketch

`Q` satisfies its own characteristic equation `Q² = Q + I` (Cayley–Hamilton; char. poly `x² − x − 1`). Define `T_n = tr(Q^n)`. Then:

```
T_{n+2} = tr(Q^{n+2})
        = tr(Q^{n+1} + Q^n)     (by Q² = Q + I, multiplied by Q^n, traced)
        = tr(Q^{n+1}) + tr(Q^n)
        = T_{n+1} + T_n
```

with `T_0 = tr(I) = 2` and `T_1 = tr(Q) = 1`. The recurrence and initials are exactly the Lucas sequence, so `T_n = L_n` for all `n`. ∎ (as a trace-recurrence identity; verified exactly in `turing_core` on `n ∈ 1..76`)

---

## 3. What this is NOT

- Not a proof that path counting on **arbitrary NP-search graphs** is polynomial.
- Not a proof that the bound extends to graphs with more than two states.
- Not a proof of P vs NP, or of any Millennium problem.
- Not a claim about quantum advantage — no quantum claim is made or needed by this lemma.

The bound applies **specifically** to the two-state golden adjacency structure used in the traversal substrate. Any extension to richer graphs is a separate, unproven claim and is treated as such.

---

## 4. Scope of application

The lemma authorizes exactly two things:

1. **Ordering and bounding nonce-window probe schedules.** `tr(Q^n)` counts the closed walks that index the schedule families. The substrate may use this count to order and bound schedules.
2. **Exact verification budget.** The substrate may claim `O(log n)` evaluation of these specific counts via fast doubling — **nothing more**.

Anything outside these two uses is out of scope.

---

## 5. Reviewer signoff (role attestations — evidence executed, not humans)

| Role | Attestation |
|---|---|
| mathematician | trace recurrence `T_{n+2} = T_{n+1} + T_n` verified |
| complexity | fast-doubling bound `O(log n)` verified on the declared range |
| number_theorist | Lucas initials `T_0 = 2`, `T_1 = 1` verified |
| qi_physicist | no quantum claim is made or needed by this lemma |
| systems | identity evaluates exactly (no floats) in `turing_core` |

`theorem_proven: false`
