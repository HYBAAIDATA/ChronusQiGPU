/-!
# Zeckendorf codec, machine-checked (core Lean 4, no Mathlib)

The aethel Zeckendorf codec (`aethel.zeckendorf.HardenedZeckendorfCodec`)
encodes each 8-byte chunk as a bitmask over Fibonacci numbers and
verifies the non-adjacency condition. The Python codec is checked
empirically against random inputs; here the two properties that make
it a codec at all are *theorems*:

* `encodeIdxs_correct` — `decodeIdxs (encodeIdxs n) = n` for every
  `n : Nat`: the greedy largest-Fibonacci expansion always sums back
  to the input (existence half of Zeckendorf's theorem).
* `encodeFuel_nonAdjacent` — consecutive indices the greedy expansion
  emits differ by at least two, so no two *consecutive* Fibonacci
  numbers appear (the non-adjacency condition the Python codec
  bit-checks with `mask & (mask << 1) == 0`).

Formulation note: indices are returned as a list rather than a
bitmask so the proofs stay inside Lean 4 core (no `Nat.testBit`
machinery needed); `NoAdjacent` on the index list is exactly the
property `verify_non_adjacent` computes on the corresponding bitmask.

What is NOT proved here (and is not claimed): uniqueness of the
expansion. Uniqueness is a deeper combinatorial theorem; the codec
only needs existence + non-adjacency.
-/

namespace Guardian

def fibN : Nat → Nat
  | 0 => 0
  | 1 => 1
  | n + 2 => fibN n + fibN (n + 1)

theorem twoStep {P : Nat → Prop} (h0 : P 0) (h1 : P 1)
    (hs : ∀ n, P n → P (n + 1) → P (n + 2)) : ∀ n, P n := by
  intro n
  suffices h : P n ∧ P (n + 1) from h.1
  induction n with
  | zero => exact ⟨h0, h1⟩
  | succ k ih => exact ⟨ih.2, hs k ih.1 ih.2⟩

theorem fib_pos_succ (n : Nat) : 0 < fibN (n + 1) := by
  induction n using twoStep with
  | h0 => decide
  | h1 => decide
  | hs n iha ihb =>
      have ihb' : 0 < fibN (n + 2) := ihb
      have e : fibN (n + 3) = fibN (n + 1) + fibN (n + 2) := rfl
      rw [e]; omega

theorem fib_mono_succ (n : Nat) : fibN n ≤ fibN (n + 1) := by
  induction n using twoStep with
  | h0 => decide
  | h1 => decide
  | hs n iha ihb =>
      show fibN (n + 2) ≤ fibN (n + 3)
      have e : fibN (n + 3) = fibN (n + 1) + fibN (n + 2) := rfl
      rw [e]; omega

theorem fib_mono {i j : Nat} (h : i ≤ j) : fibN i ≤ fibN j := by
  induction h with
  | refl => exact Nat.le_refl _
  | step hk ih => exact Nat.le_trans ih (fib_mono_succ _)

theorem fib_strict (i l : Nat) (h : i < l) (hl : 3 ≤ l) : fibN i < fibN l := by
  have m1 : fibN i ≤ fibN (l - 1) := fib_mono (by omega)
  have m2 : fibN (l - 1) < fibN l := by
    have e : fibN l = fibN (l - 2) + fibN (l - 1) := by
      cases l with
      | zero => omega
      | succ k => cases k with
        | zero => omega
        | succ k => rfl
    have p : 0 < fibN (l - 2) := by
      have e1 : fibN 1 = 1 := rfl
      have m : fibN 1 ≤ fibN (l - 2) := fib_mono (by omega)
      omega
    omega
  exact Nat.lt_of_le_of_lt m1 m2

theorem fib_ge (n : Nat) : n + 1 ≤ fibN (n + 2) := by
  induction n using twoStep with
  | h0 => decide
  | h1 => decide
  | hs n iha ihb =>
      have ihb' : n + 2 ≤ fibN (n + 3) := ihb
      have e : fibN (n + 4) = fibN (n + 2) + fibN (n + 3) := rfl
      rw [e]; omega

def largestAux (n : Nat) : Nat → Nat
  | 0 => 0
  | b + 1 => if fibN (b + 1) ≤ n then b + 1 else largestAux n b

theorem largestAux_spec_le (n : Nat) :
    ∀ b, (∃ k, k ≤ b ∧ fibN k ≤ n) → fibN (largestAux n b) ≤ n := by
  intro b
  induction b with
  | zero =>
      intro h
      rcases h with ⟨k, hk, hfk⟩
      have : k = 0 := Nat.eq_zero_of_le_zero hk
      subst this
      simp [largestAux]
      exact hfk
  | succ b ih =>
      intro h
      unfold largestAux
      by_cases hb : fibN (b + 1) ≤ n
      · simp [hb]
      · simp [hb]
        apply ih
        rcases h with ⟨k, hk, hfk⟩
        have : k ≠ b + 1 := fun e => hb (e ▸ hfk)
        exact ⟨k, Nat.le_of_lt_succ (Nat.lt_of_le_of_ne hk this), hfk⟩

theorem largestAux_le (n : Nat) : ∀ b, largestAux n b ≤ b := by
  intro b
  induction b with
  | zero => simp [largestAux]
  | succ b ih =>
      unfold largestAux
      by_cases hb : fibN (b + 1) ≤ n
      · simp [hb]
      · simp [hb]
        omega

theorem largestAux_ge (n : Nat) :
    ∀ b k, k ≤ b → fibN k ≤ n → k ≤ largestAux n b := by
  intro b
  induction b with
  | zero =>
      intro k hk hfk
      have : k = 0 := Nat.eq_zero_of_le_zero hk
      subst this
      simp [largestAux]
  | succ b ih =>
      intro k hk hfk
      unfold largestAux
      by_cases hb : fibN (b + 1) ≤ n
      · simp [hb]
        exact hk
      · simp [hb]
        have : k ≠ b + 1 := fun e => hb (e ▸ hfk)
        exact ih k (Nat.le_of_lt_succ (Nat.lt_of_le_of_ne hk this)) hfk

theorem largestAux_max (n : Nat) :
    ∀ b j, largestAux n b < j → j ≤ b → ¬ fibN j ≤ n := by
  intro b
  induction b with
  | zero =>
      intro j hj hle
      simp [largestAux] at hj
      omega
  | succ b ih =>
      intro j hj hle
      unfold largestAux at hj
      by_cases hb : fibN (b + 1) ≤ n
      · simp [hb] at hj
        omega
      · simp [hb] at hj
        have hcases : j = b + 1 ∨ j ≤ b := by
          have hsucc : j ≤ b + 1 := hle
          cases Nat.eq_or_lt_of_le hsucc with
          | inl heq => exact Or.inl heq
          | inr hlt => exact Or.inr (Nat.le_of_lt_succ hlt)
        cases hcases with
        | inl heq => exact fun hf => hb (heq ▸ hf)
        | inr hlt => exact ih j hj hlt

/-- Largest Fibonacci index whose value does not exceed `n`. -/
def largestFibIdx (n : Nat) : Nat := largestAux n (n + 2)

theorem largestFibIdx_spec_le {n : Nat} (h : 0 < n) :
    fibN (largestFibIdx n) ≤ n :=
  largestAux_spec_le n (n + 2) ⟨1, by omega, by
    have e : fibN 1 = 1 := rfl
    omega⟩

theorem largestFibIdx_pos {n : Nat} (h : 0 < n) : 1 ≤ largestFibIdx n := by
  have e : fibN 1 = 1 := rfl
  have w : fibN 1 ≤ n := by omega
  exact largestAux_ge n (n + 2) 1 (by omega) w
theorem largestFibIdx_spec_gt {n : Nat} (h : 0 < n) :
    n < fibN (largestFibIdx n + 1) := by
  unfold largestFibIdx at *
  have hidx : largestAux n (n + 2) ≤ n + 1 := by
    have le : largestAux n (n + 2) ≤ n + 2 := largestAux_le n (n + 2)
    have heq : largestAux n (n + 2) ≠ n + 2 := by
      intro heq
      have hle := largestFibIdx_spec_le h
      unfold largestFibIdx at hle
      rw [heq] at hle
      have hfge : n + 1 ≤ fibN (n + 2) := fib_ge n
      omega
    cases Nat.eq_or_lt_of_le le with
    | inl he => exact absurd he heq
    | inr hl => exact Nat.le_of_lt_succ hl
  have max := largestAux_max n (n + 2) (largestAux n (n + 2) + 1) (by omega) (by omega)
  omega
/-- Greedy Zeckendorf expansion, fuel-bounded for structural
recursion. `encodeIdxs n` is `encodeFuel (n+1) n`; fuel never binds
because each step strictly decreases `n`. -/
def encodeFuel : Nat → Nat → List Nat
  | 0, _ => []
  | fuel + 1, n =>
      if n = 0 then [] else
        let k := largestFibIdx n
        k :: encodeFuel fuel (n - fibN k)

def encodeIdxs (n : Nat) : List Nat := encodeFuel (n + 1) n

def decodeIdxs : List Nat → Nat
  | [] => 0
  | k :: ks => fibN k + decodeIdxs ks

private theorem fib_pos_of_pos {n : Nat} (h : 0 < n) : 0 < fibN (largestFibIdx n) := by
  have hidx : 1 ≤ largestFibIdx n := largestFibIdx_pos h
  have m : fibN 1 ≤ fibN (largestFibIdx n) := fib_mono hidx
  have e : fibN 1 = 1 := rfl
  omega

/-- `fibN` is weakly monotone, so `fibN i < fibN l` forces `i < l`. -/
theorem fib_lt_left {i l : Nat} (h : fibN i < fibN l) : i < l :=
  Nat.lt_of_not_ge fun hle => Nat.not_lt_of_le (fib_mono hle) h

/-- The greedy index for positive `n` is at least 2: `fibN 2 = fibN 1`
makes the largest eligible index win the tie. -/
private theorem idx_ge_two {n : Nat} (hn : 0 < n) : 2 ≤ largestFibIdx n := by
  have hpos := largestFibIdx_pos hn
  have hgt := largestFibIdx_spec_gt hn
  cases Nat.eq_or_lt_of_le hpos with
  | inl he =>
      rw [← he] at hgt
      have f2 : fibN (1 + 1) = 1 := rfl
      omega
  | inr hlt => exact hlt

/-- Correctness of the greedy codec: `decode ∘ encode = id`. This is
the existence half of Zeckendorf's theorem. -/
theorem encodeFuel_correct :
    ∀ fuel n, n < fuel → decodeIdxs (encodeFuel fuel n) = n := by
  intro fuel
  induction fuel with
  | zero =>
      intro n hn
      exact absurd hn (Nat.not_lt_zero n)
  | succ fuel ih =>
      intro n hn
      simp only [encodeFuel]
      by_cases h0 : n = 0
      · subst h0; simp; rfl
      · simp only [h0, ite_false, decodeIdxs]
        have hle := largestFibIdx_spec_le (by omega : 0 < n)
        have hpos := fib_pos_of_pos (by omega : 0 < n)
        have hlt : n - fibN (largestFibIdx n) < fuel := by omega
        rw [ih (n - fibN (largestFibIdx n)) hlt]
        exact Nat.add_sub_cancel' hle

theorem encodeIdxs_correct (n : Nat) : decodeIdxs (encodeIdxs n) = n :=
  encodeFuel_correct (n + 1) n (Nat.lt_succ_self n)

/-- Consecutive indices in a Zeckendorf expansion differ by at least
two — the non-adjacency condition, at index level. -/
def NoAdjacent : List Nat → Prop
  | [] => True
  | [_] => True
  | a :: b :: rest => a ≥ b + 2 ∧ NoAdjacent (b :: rest)

/-- The greedy remainder `n - fibN k` is strictly below `fibN (k-1)` —
the engine of non-adjacency. -/
private theorem remainder_lt {n : Nat} (hn : 0 < n) :
    n - fibN (largestFibIdx n) < fibN (largestFibIdx n - 1) := by
  have hgt := largestFibIdx_spec_gt hn
  have hle := largestFibIdx_spec_le hn
  have hidx := idx_ge_two hn
  have e : fibN (largestFibIdx n + 1) = fibN (largestFibIdx n - 1) + fibN (largestFibIdx n) := by
    cases hkk : largestFibIdx n with
    | zero => omega
    | succ j => cases hjj : j with
      | zero => omega
      | succ j' => rfl
  have hf1 : 0 < fibN (largestFibIdx n - 1) := by
    have e1 : fibN 1 = 1 := rfl
    have m : fibN 1 ≤ fibN (largestFibIdx n - 1) := fib_mono (by omega)
    omega
  omega

theorem encodeFuel_nonAdjacent :
    ∀ fuel n, n < fuel → NoAdjacent (encodeFuel fuel n) := by
  intro fuel
  induction fuel with
  | zero =>
      intro n hn
      exact absurd hn (Nat.not_lt_zero n)
  | succ fuel ih =>
      intro n hn
      simp only [encodeFuel]
      by_cases h0 : n = 0
      · subst h0; exact True.intro
      · simp only [h0, ite_false]
        have hpos := fib_pos_of_pos (by omega : 0 < n)
        have hle := largestFibIdx_spec_le (by omega : 0 < n)
        have hrem := remainder_lt (by omega : 0 < n)
        have hlt : n - fibN (largestFibIdx n) < fuel := by omega
        by_cases hm0 : n - fibN (largestFibIdx n) = 0
        · have he : encodeFuel fuel (n - fibN (largestFibIdx n)) = [] := by
            cases fuel with
            | zero => rfl
            | succ f => simp [encodeFuel, hm0]
          rw [he]
          exact True.intro
        · cases fuel with
          | zero => omega
          | succ f =>
              simp only [encodeFuel]
              simp only [hm0, ite_false]
              have htail := ih (n - fibN (largestFibIdx n)) hlt
              simp only [encodeFuel] at htail
              simp only [hm0, ite_false] at htail
              have hge : largestFibIdx n ≥ largestFibIdx (n - fibN (largestFibIdx n)) + 2 := by
                have hidx2 := idx_ge_two (by omega : 0 < n)
                have hspec := largestFibIdx_spec_le (by omega : 0 < n - fibN (largestFibIdx n))
                by_cases hsmall : largestFibIdx n ≤ 3
                · have fbound : fibN (largestFibIdx n - 1) ≤ 1 := by
                    have m : fibN (largestFibIdx n - 1) ≤ fibN 2 :=
                      fib_mono (by omega : largestFibIdx n - 1 ≤ 2)
                    have f2 : fibN 2 = 1 := rfl
                    omega
                  omega
                · have hl : 3 ≤ largestFibIdx n - 1 := by omega
                  have hfl : fibN (largestFibIdx (n - fibN (largestFibIdx n)))
                           < fibN (largestFibIdx n - 1) := Nat.lt_of_le_of_lt hspec hrem
                  have hlti := fib_lt_left hfl
                  omega
              exact ⟨hge, htail⟩

end Guardian
