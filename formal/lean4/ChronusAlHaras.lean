/-
================================================================================
  AL HARAS (HYBA Security): coboundary lemmas for the constant sheaf on a graph
================================================================================
  Status: specification source only. This file is NOT compiled or
  machine-checked in this repository's CI: no workflow or lakefile builds
  formal/lean4/, and it has not been checked against a pinned Mathlib release.
  It is written for Mathlib with the `∑ x ∈ s, f x` notation. Nothing here is a
  certification or an assurance claim.

  Setting: a 0-cochain is a function `s : V → A` into an additive commutative
  group `A` (AL HARAS uses A = ℚ^d). On an oriented edge `u → v` the coboundary
  of the constant sheaf (identity restriction maps) is `s v - s u`.

  Executable counterparts, run with exact arithmetic on finite instances in
  src/chronus/security/al_haras/formal_invariants.py:
    coboundary_eq_zero_iff                   ~ check "sheaf_coboundary_zero_iff_consistent"
    not_coboundary_of_closed_walk_sum_ne_zero ~ check "cycle_sum_obstruction"
  The converse of the cycle-sum criterion (vanishing sums around all cycles of
  a connected graph make an edge cochain a coboundary) is only checked
  executably; it is not stated here.
================================================================================
-/

-- `import Mathlib` because the big-operator module paths moved between Mathlib versions.
import Mathlib

namespace Chronus.AlHaras

variable {V A : Type*} [AddCommGroup A]

/-- Coboundary of the 0-cochain `s` on the oriented edge `u → v`. -/
def coboundary (s : V → A) (u v : V) : A :=
  s v - s u

/-- Edge consistency: the coboundary vanishes on `u → v` exactly when the
states at `u` and `v` agree. -/
theorem coboundary_eq_zero_iff (s : V → A) (u v : V) :
    coboundary s u v = 0 ↔ s v = s u := by
  unfold coboundary
  exact sub_eq_zero

/-- Telescoping: along a walk `w 0, w 1, …, w n` the coboundary sums to the
difference of the end-point states. -/
theorem coboundary_sum_walk (s : V → A) (w : ℕ → V) (n : ℕ) :
    ∑ i ∈ Finset.range n, coboundary s (w i) (w (i + 1)) = s (w n) - s (w 0) :=
  Finset.sum_range_sub (fun i => s (w i)) n

/-- Around a closed walk (`w n = w 0`) the coboundary of any 0-cochain sums to zero. -/
theorem coboundary_sum_closed_walk (s : V → A) (w : ℕ → V) (n : ℕ)
    (hclosed : w n = w 0) :
    ∑ i ∈ Finset.range n, coboundary s (w i) (w (i + 1)) = 0 := by
  rw [coboundary_sum_walk s w n, hclosed, sub_self]

/-- Cycle-sum obstruction: an edge cochain `c` whose sum around some closed walk
is non-zero is not the coboundary of any 0-cochain. -/
theorem not_coboundary_of_closed_walk_sum_ne_zero (c : V → V → A) (w : ℕ → V) (n : ℕ)
    (hclosed : w n = w 0)
    (hsum : ∑ i ∈ Finset.range n, c (w i) (w (i + 1)) ≠ 0) :
    ¬ ∃ s : V → A, ∀ u v, c u v = coboundary s u v := by
  rintro ⟨s, hs⟩
  apply hsum
  calc ∑ i ∈ Finset.range n, c (w i) (w (i + 1))
      = ∑ i ∈ Finset.range n, coboundary s (w i) (w (i + 1)) :=
        Finset.sum_congr rfl (fun i _ => hs (w i) (w (i + 1)))
    _ = 0 := coboundary_sum_closed_walk s w n hclosed

end Chronus.AlHaras
