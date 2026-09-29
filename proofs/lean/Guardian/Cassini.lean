/-!
# Cassini–Hoggatt identity, machine-checked (core Lean 4, no Mathlib)

The Guardian's aethel storage layer gates integrity on the
Cassini-Hoggatt identity

    L_n^2 - 5 * F_n^2 = 4 * (-1)^n

where `L` is the Lucas sequence (2, 1, 3, 4, 7, ...) and `F` is
Fibonacci (0, 1, 1, 2, 3, ...). In Python this is only ever checked
empirically (`aethel.cassini.CassiniVerifier.verify` recomputes both
sides for a given n). Here it is a *theorem*: proved once for every n
by induction, so `verify` can never be falsified by a larger index.

The sign `(-1)^n` is written `sgn n` (`if n % 2 = 0 then 1 else -1`)
to keep the development inside Lean 4 core — no `pow` machinery needed.
-/

namespace Guardian

def fib : Nat → Int
  | 0 => 0
  | 1 => 1
  | n + 2 => fib n + fib (n + 1)

def lucas : Nat → Int
  | 0 => 2
  | 1 => 1
  | n + 2 => lucas n + lucas (n + 1)

/-- The parity sign `(-1)^n` for `n : Nat`. -/
def sgn (n : Nat) : Int := if n % 2 = 0 then 1 else -1

theorem sgn_succ (n : Nat) : sgn (n + 1) = -sgn n := by
  unfold sgn
  omega

/-- The Cassini determinant `L_n² - 5F_n²` as an integer. -/
def cassiniDet (n : Nat) : Int := lucas n * lucas n - 5 * (fib n * fib n)

/-- Two-step induction: the natural eliminator for linear recurrences
of order two (Fibonacci/Lucas). -/
theorem twoStep {P : Nat → Prop} (h0 : P 0) (h1 : P 1)
    (hs : ∀ n, P n → P (n + 1) → P (n + 2)) : ∀ n, P n := by
  intro n
  suffices h : P n ∧ P (n + 1) from h.1
  induction n with
  | zero => exact ⟨h0, h1⟩
  | succ k ih => exact ⟨ih.2, hs k ih.1 ih.2⟩

/-- Auxiliary identity: `L_{n+1} = 2F_{n+2} - F_{n+1}` — the linear
relation that makes the quadratic Cassini step pure algebra. -/
theorem lucas_eq (n : Nat) : lucas (n + 1) = 2 * fib (n + 2) - fib (n + 1) := by
  induction n using twoStep with
  | h0 => decide
  | h1 => decide
  | hs n iha ihb =>
      have ihb' : lucas (n + 2) = 2 * fib (n + 3) - fib (n + 2) := ihb
      have e1 : lucas (n + 3) = lucas (n + 1) + lucas (n + 2) := rfl
      have e2 : fib (n + 4) = fib (n + 2) + fib (n + 3) := rfl
      have e3 : fib (n + 3) = fib (n + 1) + fib (n + 2) := rfl
      rw [e1, e2, e3, iha, ihb']
      omega

/-- Sign alternation of the Cassini determinant, in two steps.
`sgn`/`sq` helper lemmas keep the expansion inside `Int` ring axioms. -/

theorem two_mul_two (x : Int) : 2 * (2 * x) = 4 * x := by
  rw [← Int.mul_assoc]
  rw [show (2 : Int) * 2 = 4 by decide]

theorem mul2_left (x y : Int) : (2 * x) * y = 2 * (x * y) := Int.mul_assoc 2 x y

theorem mul2_right (x y : Int) : y * (2 * x) = 2 * (x * y) := by
  rw [Int.mul_comm y (2 * x)]
  exact Int.mul_assoc 2 x y

theorem mul2_two (x : Int) : (2 * x) * (2 * x) = 4 * (x * x) := by
  rw [← Int.mul_assoc (2 * x) 2 x, Int.mul_comm (2 * x) 2, two_mul_two,
      Int.mul_assoc]

theorem sq_sum2 (a b : Int) : (a + 2*b)*(a + 2*b) = a*a + 4*(a*b) + 4*(b*b) := by
  rw [Int.mul_add, Int.add_mul, Int.add_mul, mul2_right, Int.mul_comm (2*b) a,
      mul2_right, mul2_two, Int.mul_comm b a]
  omega

theorem sq_diff2 (a b : Int) : (2*a - b)*(2*a - b) = 4*(a*a) - 4*(a*b) + b*b := by
  rw [Int.mul_sub, Int.sub_mul, Int.sub_mul]
  rw [mul2_two]
  have h2 : (2*a)*b = 2*(a*b) := mul2_left a b
  have h3 : b*(2*a) = 2*(a*b) := mul2_right a b
  rw [h2, h3]
  omega

/-- `(a+2b)² - 5a² + (2a-b)² - 5b² = 0` — the algebraic heart of the
alternation. With `a = F_{n+2}`, `b = F_{n+1}` the LHS is
`det(n+2) + det(n+1)` after `lucas_eq` substitutes
`L_{k+1} = 2F_{k+2} - F_{k+1}`. -/
theorem sq_id (a b : Int) :
    (a + 2*b)*(a + 2*b) - 5*(a*a) + (2*a - b)*(2*a - b) - 5*(b*b) = 0 := by
  rw [sq_sum2 a b, sq_diff2 a b]
  omega

/-- The determinant flips sign every step. -/
theorem cassini_det_succ (n : Nat) : cassiniDet (n + 1) = -cassiniDet n := by
  cases n with
  | zero => decide
  | succ m =>
      -- det (m+2) = -det (m+1)
      have h1 : lucas (m + 1) = 2 * fib (m + 2) - fib (m + 1) := lucas_eq m
      have h2 : lucas (m + 2) = 2 * fib (m + 3) - fib (m + 2) := lucas_eq (m + 1)
      have e : fib (m + 3) = fib (m + 1) + fib (m + 2) := rfl
      have key : 2 * fib (m + 3) - fib (m + 2) = fib (m + 2) + 2 * fib (m + 1) := by
        rw [e]
        omega
      show cassiniDet (m + 2) = -cassiniDet (m + 1)
      unfold cassiniDet
      rw [h1, h2, key]
      have h := sq_id (fib (m + 2)) (fib (m + 1))
      omega

/-- The Cassini–Hoggatt identity, for every `n`:
`L_n² - 5F_n² = 4·(-1)^n`. -/
theorem cassini (n : Nat) : cassiniDet n = 4 * sgn n := by
  induction n with
  | zero => decide
  | succ k ih =>
      rw [cassini_det_succ k, ih, sgn_succ]
      omega

end Guardian
