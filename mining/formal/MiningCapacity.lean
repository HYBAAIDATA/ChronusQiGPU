/-!
Mining-owned exact capacity predicates and witnesses.

These theorems preserve the historical formal work removed from TURING's
release claim set. They prove arithmetic design identities only; they are not
measurements of executed mining throughput.
-/

namespace MiningCapacity

/--
Cross-multiplied exact capacity predicate. `throughputNumerator` is M*N*f,
`initiationInterval` is I, and `floor` is the required result rate.
-/
def capacityFloorMet
    (throughputNumerator initiationInterval floor : Nat) : Prop :=
  floor * initiationInterval ≤ throughputNumerator

theorem capacity_floor_from_witness
    (throughputNumerator initiationInterval floor : Nat)
    (h : floor * initiationInterval ≤ throughputNumerator) :
    capacityFloorMet throughputNumerator initiationInterval floor := by
  exact h

theorem ten_eh_canonical_floor :
    capacityFloorMet
      (1000001 * 10000 * 1000000000)
      1
      10000000000000000000 := by
  decide

end MiningCapacity
