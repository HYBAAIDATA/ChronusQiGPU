import Chronus.Cyclotomic

open Chronus.Cyclotomic5

-- Importing and applying the results checks the public theorem names/types.
example : mul phi phi = add phi one := phi_squared_eq_phi_plus_one
example : mul phi phiInv = one := phi_mul_phi_inv_eq_one
example : mul (mul (mul (mul zeta zeta) zeta) zeta) zeta = one := zeta_fifth_eq_one
example (a b : Chronus.Cyclotomic5) : add a b = add b a := add_comm a b
example (a b c : Chronus.Cyclotomic5) : add (add a b) c = add a (add b c) := add_assoc a b c
example (a : Chronus.Cyclotomic5) : mul one a = a := one_mul a
example (a : Chronus.Cyclotomic5) : mul a one = a := mul_one a
example (a b : Chronus.Cyclotomic5) : mul a b = mul b a := mul_comm a b
-- An intentionally false identity remains false; this is not a general
-- non-vacuity or mutation test for the full library.
example : mul phi phi ≠ one := by decide

#print axioms phi_squared_eq_phi_plus_one
#print axioms phi_mul_phi_inv_eq_one
#print axioms zeta_fifth_eq_one

#print axioms add_comm
#print axioms add_assoc
#print axioms one_mul
#print axioms mul_one
#print axioms mul_comm
