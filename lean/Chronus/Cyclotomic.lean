import Std

/-!
A concrete four-coefficient representation of Z[x]/(x^4+x^3+x^2+x+1).
The closed identities below are kernel-checked computations. They do not yet
establish the ring axioms, a quotient isomorphism, or software/RTL equivalence.
-/
namespace Chronus

structure Cyclotomic5 where
  c0 : Int
  c1 : Int
  c2 : Int
  c3 : Int
  deriving DecidableEq, Repr

namespace Cyclotomic5

def one : Cyclotomic5 := ⟨1, 0, 0, 0⟩
def zeta : Cyclotomic5 := ⟨0, 1, 0, 0⟩
def phi : Cyclotomic5 := ⟨0, 0, -1, -1⟩
def phiInv : Cyclotomic5 := ⟨-1, 0, -1, -1⟩

def add (a b : Cyclotomic5) : Cyclotomic5 :=
  ⟨a.c0 + b.c0, a.c1 + b.c1, a.c2 + b.c2, a.c3 + b.c3⟩

/-- Polynomial multiplication reduced using x^4 = -1-x-x^2-x^3,
    x^5 = 1 and x^6 = x. -/
def mul (a b : Cyclotomic5) : Cyclotomic5 :=
  let t0 := a.c0*b.c0
  let t1 := a.c0*b.c1 + a.c1*b.c0
  let t2 := a.c0*b.c2 + a.c1*b.c1 + a.c2*b.c0
  let t3 := a.c0*b.c3 + a.c1*b.c2 + a.c2*b.c1 + a.c3*b.c0
  let t4 := a.c1*b.c3 + a.c2*b.c2 + a.c3*b.c1
  let t5 := a.c2*b.c3 + a.c3*b.c2
  let t6 := a.c3*b.c3
  ⟨t0-t4+t5, t1-t4+t6, t2-t4, t3-t4⟩

theorem phi_squared_eq_phi_plus_one : mul phi phi = add phi one := by
  decide

theorem phi_mul_phi_inv_eq_one : mul phi phiInv = one := by
  decide

theorem zeta_fifth_eq_one : mul (mul (mul (mul zeta zeta) zeta) zeta) zeta = one := by
  decide

end Cyclotomic5
end Chronus
