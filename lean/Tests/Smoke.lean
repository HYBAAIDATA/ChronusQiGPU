import Chronus.Cyclotomic

open Chronus.Cyclotomic5

-- Importing and applying the results checks the public theorem names/types.
example : mul phi phi = add phi one := phi_squared_eq_phi_plus_one
example : mul phi phiInv = one := phi_mul_phi_inv_eq_one
example : mul (mul (mul (mul zeta zeta) zeta) zeta) zeta = one := zeta_fifth_eq_one
-- An intentionally false identity remains false; this is not a general
-- non-vacuity or mutation test for the full library.
example : mul phi phi ≠ one := by decide

#print axioms phi_squared_eq_phi_plus_one
#print axioms phi_mul_phi_inv_eq_one
#print axioms zeta_fifth_eq_one
