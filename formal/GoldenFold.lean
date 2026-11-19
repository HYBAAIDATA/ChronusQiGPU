/- Core Lean 4, pinned toolchain. General Cassini and divisibility-form
period congruence, plus the explicit modular identity. -/
namespace GoldenFold

structure Mat2 where
  a : Int
  b : Int
  c : Int
  d : Int
  deriving DecidableEq, Repr

def Mat2.id : Mat2 := ⟨1, 0, 0, 1⟩
def Mat2.Q : Mat2 := ⟨1, 1, 1, 0⟩
def Mat2.add (x y : Mat2) : Mat2 :=
  ⟨x.a+y.a, x.b+y.b, x.c+y.c, x.d+y.d⟩
def Mat2.scale (s : Int) (x : Mat2) : Mat2 :=
  ⟨s*x.a, s*x.b, s*x.c, s*x.d⟩
def Mat2.mul (x y : Mat2) : Mat2 :=
  ⟨x.a*y.a+x.b*y.c, x.a*y.b+x.b*y.d,
   x.c*y.a+x.d*y.c, x.c*y.b+x.d*y.d⟩
def Mat2.det (x : Mat2) : Int := x.a*x.d-x.b*x.c
def Mat2.pow (x : Mat2) : Nat → Mat2
  | 0 => Mat2.id
  | n+1 => Mat2.mul (Mat2.pow x n) x
def Mat2.mod (x : Mat2) (m : Int) : Mat2 :=
  ⟨x.a%m, x.b%m, x.c%m, x.d%m⟩

theorem det_mul (x y : Mat2) : (Mat2.mul x y).det = x.det*y.det := by
  cases x
  cases y
  simp only [Mat2.mul, Mat2.det]
  grind

theorem cassini (n : Nat) : (Mat2.pow Mat2.Q n).det = (-1 : Int)^n := by
  induction n with
  | zero => decide
  | succ n ih =>
    rw [Mat2.pow, det_mul, ih, Int.pow_succ]
    rfl

theorem mul_assoc (x y z : Mat2) :
    (x.mul y).mul z = x.mul (y.mul z) := by
  cases x
  cases y
  cases z
  simp only [Mat2.mul, Mat2.mk.injEq]
  grind

theorem mul_id (x : Mat2) : x.mul Mat2.id = x := by
  cases x
  simp [Mat2.mul, Mat2.id]

theorem pow_add (x : Mat2) (m n : Nat) :
    x.pow (m+n) = (x.pow m).mul (x.pow n) := by
  induction n with
  | zero => simp [Mat2.pow, mul_id]
  | succ n ih =>
    rw [Nat.add_succ, Mat2.pow, ih, Mat2.pow, mul_assoc]

theorem square_scaled (t : Int) (A : Mat2) :
    (Mat2.id.add (Mat2.scale (2*t) A)).mul (Mat2.id.add (Mat2.scale (2*t) A))
      = Mat2.id.add (Mat2.scale (4*t) (A.add (Mat2.scale t (A.mul A)))) := by
  cases A
  simp only [Mat2.mul, Mat2.add, Mat2.scale, Mat2.id, Mat2.mk.injEq]
  grind

theorem hensel_square (n : Nat) (A : Mat2) :
    (Mat2.id.add (Mat2.scale (2^(n+1)) A)).mul
      (Mat2.id.add (Mat2.scale (2^(n+1)) A))
      = Mat2.id.add (Mat2.scale (2^(n+2)) (A.add (Mat2.scale (2^n) (A.mul A)))) := by
  have h1 : (2 : Int)^(n+1) = 2*2^n := by
    rw [Int.pow_succ]
    grind
  have h2 : (2 : Int)^(n+2) = 4*2^n := by
    rw [Int.pow_succ, h1]
    grind
  rw [h2,h1]
  exact square_scaled (2^n) A

theorem pisano_pow2_lift (n : Nat) :
    ∃ A : Mat2, Mat2.Q.pow (3*2^n) = Mat2.id.add (Mat2.scale (2^(n+1)) A) := by
  induction n with
  | zero => exact ⟨Mat2.Q, by decide⟩
  | succ n ih =>
    obtain ⟨A,hA⟩ := ih
    refine ⟨A.add (Mat2.scale (2^n) (A.mul A)), ?_⟩
    have h : 3*2^(n+1) = 3*2^n+3*2^n := by
      rw [Nat.pow_succ]
      omega
    rw [h,pow_add,hA]
    exact hensel_square n A

theorem mod_one_plus_mul (m a : Int) (hm : 1 < m) :
    (1+m*a)%m = 1 := by
  rw [Int.add_mul_emod_self_left]
  exact Int.emod_eq_of_lt (by decide) hm

theorem mod_mul (m a : Int) : (m*a)%m = 0 := by
  simp

theorem mod_lift (m : Int) (A : Mat2) (hm : 1 < m) :
    (Mat2.id.add (Mat2.scale m A)).mod m = Mat2.id := by
  have h : (1 : Int) % m = 1 := Int.emod_eq_of_lt (by decide) hm
  cases A
  simp [Mat2.mod, Mat2.add, Mat2.scale, Mat2.id, h]

theorem pow2_gt_one (n : Nat) : 1 < (2 : Int)^(n+1) := by
  induction n with
  | zero => decide
  | succ n ih =>
    rw [Int.pow_succ]
    omega

theorem pisano_pow2_mod (k : Nat) (hk : 1 ≤ k) :
    (Mat2.Q.pow (3*2^(k-1))).mod (2^k) = Mat2.id := by
  obtain ⟨n, rfl⟩ : ∃ n : Nat, k = n+1 := ⟨k-1, by omega⟩
  have h : n+1-1 = n := by omega
  obtain ⟨A,hA⟩ := pisano_pow2_lift n
  rw [h,hA]
  exact mod_lift (2^(n+1)) A (pow2_gt_one n)

end GoldenFold
