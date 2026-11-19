/-
  GL2Mod256.lean — Formal Verification of the Lossless GL(2, Z/256Z) Transform
  Verifies:
    1. det(M15) = -1 (mod 256) and Cayley-Hamilton inverse M15^-1 = M15 - 84*I.
    2. Strict two-sided bijectivity of `foldPair` / `unfoldPair` on (UInt8 × UInt8).
    3. Principal congruence subgroup Gamma(2) LSB invariance.
    4. Exact canonical zero-padding characterization for odd-length inputs.
    5. Exact 256-element affine fiber parameterization for `foldTruncatedPair`.
-/

-- [REVIEW FIX L1] `decide` over the 2^16 / 2^24 / 2^32 finite domains exceeds the elaborator's
-- heartbeat budget (and kernel `decide` runs out of memory on this box). The universally quantified
-- statements are proved instead with `grind` (commutative-ring normalisation in Z/256) and `omega`
-- over `toNat`, core Lean only, no Mathlib, no native_decide: kernel-checked, axioms limited to
-- propext / Classical.choice / Quot.sound. Statements unchanged except L2 below.

namespace GL2Mod256

structure Mat2 where
  m00 : UInt8
  m01 : UInt8
  m10 : UInt8
  m11 : UInt8
  deriving DecidableEq, Repr

def M15 : Mat2 := ⟨219, 98, 98, 121⟩

def Mat2.tr (m : Mat2) : UInt8 := m.m00 + m.m11

def Mat2.det (m : Mat2) : UInt8 := m.m00 * m.m11 - m.m01 * m.m10

/-- Cayley-Hamilton inverse when det(M) = -1 (mod 256): M^-1 = M - tr(M)*I. -/
def Mat2.invCH (m : Mat2) : Mat2 :=
  let t := m.tr
  ⟨m.m00 - t, m.m01, m.m10, m.m11 - t⟩

def Mat2.mul (a b : Mat2) : Mat2 :=
  ⟨ a.m00 * b.m00 + a.m01 * b.m10, a.m00 * b.m01 + a.m01 * b.m11,
    a.m10 * b.m00 + a.m11 * b.m10, a.m10 * b.m01 + a.m11 * b.m11 ⟩

def Mat2.id : Mat2 := ⟨1, 0, 0, 1⟩

def M15_INV : Mat2 := M15.invCH

theorem m15_det_neg_one : M15.det = 255 := by decide

theorem m15_left_inv : Mat2.mul M15_INV M15 = Mat2.id := by decide

theorem m15_right_inv : Mat2.mul M15 M15_INV = Mat2.id := by decide

def foldPair (p : UInt8 × UInt8) : UInt8 × UInt8 :=
  (M15.m00 * p.1 + M15.m01 * p.2, M15.m10 * p.1 + M15.m11 * p.2)

def unfoldPair (q : UInt8 × UInt8) : UInt8 × UInt8 :=
  (M15_INV.m00 * q.1 + M15_INV.m01 * q.2, M15_INV.m10 * q.1 + M15_INV.m11 * q.2)

def foldTruncatedPair (p : UInt8 × UInt8) : UInt8 :=
  (foldPair p).1

/-- 1. Two-sided bijection on (Z/256Z)^2. -/
theorem unfold_fold_id (p : UInt8 × UInt8) : unfoldPair (foldPair p) = p := by
  rcases p with ⟨x, y⟩
  simp only [unfoldPair, foldPair, M15_INV, M15, Mat2.invCH, Mat2.tr, Prod.mk.injEq]
  constructor <;> grind

theorem fold_unfold_id (q : UInt8 × UInt8) : foldPair (unfoldPair q) = q := by
  rcases q with ⟨u, v⟩
  simp only [unfoldPair, foldPair, M15_INV, M15, Mat2.invCH, Mat2.tr, Prod.mk.injEq]
  constructor <;> grind

/-- 2. Gamma(2) principal congruence invariant: per-byte LSBs are preserved identically. -/
theorem gamma2_lsb_invariant (p : UInt8 × UInt8) :
    ((foldPair p).1 &&& 1 = p.1 &&& 1) ∧ ((foldPair p).2 &&& 1 = p.2 &&& 1) := by
  rcases p with ⟨x, y⟩
  have hx := x.toNat_lt
  have hy := y.toNat_lt
  simp only [foldPair, M15]
  constructor <;>
    (apply UInt8.toNat_inj.mp
     simp only [UInt8.toNat_and, UInt8.toNat_add, UInt8.toNat_mul]
     simp
     omega)

/-- 3. Odd-length canonical padding characterization: pad lane is 0 iff block came from (x, 0). -/
theorem odd_padding_canonical (q : UInt8 × UInt8) :
    (unfoldPair q).2 = 0 ↔ q = foldPair ((unfoldPair q).1, 0) := by
  constructor
  · intro h
    have hq : unfoldPair q = ((unfoldPair q).1, 0) := Prod.ext rfl h
    calc q = foldPair (unfoldPair q) := (fold_unfold_id q).symm
      _ = foldPair ((unfoldPair q).1, 0) := congrArg foldPair hq
  · intro h
    rw [h, unfold_fold_id]

/-- 4. Quotient fiber parameterization (audit only: `foldTruncatedPair` is not a production path).
       For any output byte u and parameter t in Z/256Z, (83*u - 98*t, 219*t) maps into lane 0 = u,
       and is injective in t. [REVIEW FIX L2] 219^-1 = 83 mod 256 (219*83 = 18177 = 71*256 + 1);
       the original 59 gives 219*59 = 121 mod 256, and Lean's `decide` reports the statement false. -/
def fiberPoint (u t : UInt8) : UInt8 × UInt8 :=
  (83 * u - 98 * t, 219 * t)

theorem inv219 : (83 : UInt8) * 219 = 1 := by decide

theorem fiberPoint_projects_to_u (u t : UInt8) :
    foldTruncatedPair (fiberPoint u t) = u := by
  simp only [foldTruncatedPair, foldPair, fiberPoint, M15]
  grind

theorem fiberPoint_injective (u t1 t2 : UInt8) :
    fiberPoint u t1 = fiberPoint u t2 → t1 = t2 := by
  intro h
  have h2 : (219 : UInt8) * t1 = 219 * t2 := congrArg Prod.snd h
  have h3 : (83 : UInt8) * (219 * t1) = 83 * (219 * t2) := by rw [h2]
  grind

/-! ## 5. FoldedReg7: 7-generator register folded by M15; collapse commutes with fold. -/

structure FoldedReg7 where
  base : UInt8 × UInt8
  gens : Fin 7 → UInt8 × UInt8
  resolvedMask : UInt8
  resolvedBits : UInt8

def vecAdd (p q : UInt8 × UInt8) : UInt8 × UInt8 := (p.1 + q.1, p.2 + q.2)

def foldReg7 (r : FoldedReg7) : FoldedReg7 :=
  { r with base := foldPair r.base, gens := fun k => foldPair (r.gens k) }

def unfoldReg7 (r : FoldedReg7) : FoldedReg7 :=
  { r with base := unfoldPair r.base, gens := fun k => unfoldPair (r.gens k) }

def collapseReg7 (r : FoldedReg7) (idx : Fin 7) (bitVal : Bool) : FoldedReg7 :=
  let flag : UInt8 := 1 <<< idx.val.toUInt8
  let newBase := if bitVal then vecAdd r.base (r.gens idx) else r.base
  let newGens := fun k => if k = idx then ((0 : UInt8), (0 : UInt8)) else r.gens k
  { base := newBase, gens := newGens,
    resolvedMask := r.resolvedMask ||| flag,
    resolvedBits := if bitVal then r.resolvedBits ||| flag else r.resolvedBits &&& ~~~flag }

theorem foldPair_add (p q : UInt8 × UInt8) : foldPair (vecAdd p q) = vecAdd (foldPair p) (foldPair q) := by
  rcases p with ⟨x1, y1⟩
  rcases q with ⟨x2, y2⟩
  simp only [foldPair, vecAdd, M15, Prod.mk.injEq]
  constructor <;> grind

theorem foldPair_zero : foldPair (0, 0) = (0, 0) := by decide

theorem fold_collapse_commute (r : FoldedReg7) (idx : Fin 7) (bitVal : Bool) :
    foldReg7 (collapseReg7 r idx bitVal) = collapseReg7 (foldReg7 r) idx bitVal := by
  cases bitVal <;>
    simp only [foldReg7, collapseReg7, foldPair_add, Bool.false_eq_true, ite_true, ite_false,
      FoldedReg7.mk.injEq, true_and, and_true] <;>
    (funext k; split <;> simp [foldPair_zero])

theorem unfold_fold_reg7_id (r : FoldedReg7) : unfoldReg7 (foldReg7 r) = r := by
  simp only [unfoldReg7, foldReg7, unfold_fold_id]

theorem fold_unfold_reg7_id (r : FoldedReg7) : foldReg7 (unfoldReg7 r) = r := by
  simp only [unfoldReg7, foldReg7, fold_unfold_id]

end GL2Mod256

