/-
  Seam invariant *statements*.
  Status: specification artifact.
  Machine-checked counterpart: standard/check_invariants.py
  Lean 4 kernel verification in CI is a partnership gap
  (toolchain + model of the Python seam). This file has no `sorry`
  because it does not claim kernel-checked proofs.
-/
namespace Seam.Invariants

-- T3  landauer_bound bits T = bits * k_B * T * LN2
-- R2  pebble_count n k = k * (n - 1) + 1
-- R1  inverse (forward x) = x  for involutive Bennett steps
-- K6  reversible kernel declares inverse
-- K8  reversible result reports garbage_uncomputed
-- AC2 merkle_root is permutation-invariant
-- S1  public seam functions return Result
-- P4  routing consumes a named policy quantile
-- T1  ThermodynamicMeasurement has four energy components

end Seam.Invariants
