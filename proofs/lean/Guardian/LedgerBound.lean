import Guardian.Zeckendorf

/-!
# Rank-bound checks are decidable — not empirical (core Lean 4)

The consortium's fifth demand asks for the machine-checked status of
the `r ≤ bound` shape that appears in the toe/BSD-style ledger gates.
This file states precisely what is verifiable:

* `bound_check` — `r ≤ b` on `Nat` is a *decidable* proposition, so a
  Python-side `assert r <= bound` corresponds to a total decision
  procedure, not a sampled test. The `↔` gives both directions: the
  boolean check is sound and complete w.r.t. the proposition.
* `rank_bound_strict` — the ledger's index discipline is strict:
  Fibonacci values strictly increase with index once `i ≥ 2`, so a
  larger retained rank genuinely requires a larger index. (This is
  the same strictness that makes the greedy Zeckendorf step well
  defined.)

The honest limit, stated plainly: these lemmas verify the *bound
check and index arithmetic*. Whether an arbitrary network trace maps
onto the adversarial region is a modeling question mathematics does
not decide — see `proofs/VERIFICATION.md` for the verified/empirical
split.
-/


namespace Guardian

/-- The bound check is a total decision procedure: `decide (r ≤ b)`
is `true` iff `r ≤ b`, in both directions. No sampling. -/
theorem bound_check (r b : Nat) : decide (r ≤ b) = true ↔ r ≤ b := by
  simp

/-- Strict rank growth: Fibonacci values strictly increase in index
once the index is at least 2, so `i < j` with `i ≥ 2` gives
`fibN i < fibN j`. -/
theorem rank_bound_strict {i j : Nat} (hi : 2 ≤ i) (h : i < j) :
    fibN i < fibN j :=
  fib_strict i j h (by omega)

/-- Consequence: distinct retained ranks imply distinct indices —
the check `fibN i < fibN j` can never pass with `j ≤ i` for `i ≥ 2`. -/
theorem rank_bound_injective {i j : Nat} (hi : 2 ≤ i) (h : i < j) :
    fibN i ≠ fibN j :=
  Nat.ne_of_lt (rank_bound_strict hi h)

end Guardian
