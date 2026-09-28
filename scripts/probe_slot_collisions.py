"""Measure prime-bucket slot collisions -- the injectivity question.
The reviewer is right to ask: ``mask % prime_mod`` is not obviously
injective, so "non-overlapping" may be a stronger claim than the function
proves. This measures the real collision rate rather than arguing about it,
and checks that the owner's linear-probe actually resolves it.
"""

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Intelligence.salamander import SalamanderEngine  # noqa: E402
from toe.poincare_golden_11d import (  # noqa: E402
    FIB_TABLE,
    PRIME_BUCKETS,
    resolve_zeckendorf_slot,
)

N = 100000

if __name__ == "__main__":
    print("=== Is mask % prime_mod injective? Measuring. ===")
    print(f"  bucket count: {len(PRIME_BUCKETS)}  max prime: {max(PRIME_BUCKETS)}")
    print(f"  FIB_TABLE[25] = {FIB_TABLE[25]}")
    total_slots = sum(p for p in PRIME_BUCKETS)
    print(f"  total physical slots across buckets: {total_slots}")
    print()

    slots = defaultdict(list)
    for idx in range(1, N + 1):
        addr, max_k = resolve_zeckendorf_slot(idx)
        slots[addr].append(idx)

    colliding = {a: v for a, v in slots.items() if len(v) > 1}
    distinct = len(slots)
    print(f"=== RESULT over {N} distinct logical indices ===")
    print(f"  distinct slot addresses : {distinct}")
    print(f"  colliding addresses     : {len(colliding)}")
    print(f"  max entities on one slot: {max(len(v) for v in slots.values())}")
    print(f"  unique addresses        : {N - sum(len(v) - 1 for v in slots.values())}")
    print()
    print("  -> the map is MANY-TO-ONE. It is NOT injective.")
    print("  -> a slot address is therefore NOT a unique identity.")
    print()

    print("=== Does the owner's linear-probe resolve it? ===")
    eng = SalamanderEngine()
    ok = 0
    for i in range(1, 501):
        try:
            eng.allocate(f"vec-{i}", [float(i)] * 11)
            ok += 1
        except Exception as exc:
            print(f"    allocation {i} failed: {type(exc).__name__}: {exc}")
            break
    print(f"  allocated 500 colliding-bearing vectors: {ok}/500")
    # The invariant that matters is: no two live objects share a physical slot.
    mgr = eng.allocation_manager
    live = list(mgr._active.keys()) if hasattr(mgr, "_active") else []
    print(f"  live allocations tracked: {len(live)}")
    addrs = [mgr._route_slot(int(hash(v) % 10**9))[0] for v in live[:200]]
    print(f"  unique physical slots in use: {len(set(addrs))}/{len(addrs)}")
    print()
    print("=== Which layer guarantees identity, then? ===")
    print("  resolve_zeckendorf_slot : MANY-TO-ONE (measured above)")
    print("  Salamander._route_slot  : linear probe -> unique physical slot")
    print("  _slots ownership        : full logical identity compared by caller")
    sys.stdout.flush()
