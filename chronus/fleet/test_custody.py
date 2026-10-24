"""Fleet qualification test - custody failure blocks completion."""
from __future__ import annotations

from datetime import datetime

from chronus.fleet.custody import FleetCustody
from chronus.fleet.native_worker import ExecutionResult


def test_custody_blocks_unauthorized():
    """Custody failure blocks unauthorized completion."""
    print("[TEST 6] Custody blocks unauthorized")
    custody = FleetCustody()

    # Unauthorized tenant should be blocked
    bad = ExecutionResult(
        lease_id="",
        work_id="bad",
        tenant="unauthorized",
        operation="op",
        output_digest="x" * 64,
        partition=(0, 4),
        success=True,
        timestamp=datetime.now(),
    )
    blocked = not custody.verify_and_commit(bad, "authorized_tenant")
    assert blocked is True
    print(f"  Unauthorized tenant blocked: {blocked}")

    # Authorized tenant should be allowed
    good = ExecutionResult(
        lease_id="",
        work_id="good",
        tenant="authorized_tenant",
        operation="op",
        output_digest="y" * 64,
        partition=(0, 4),
        success=True,
        timestamp=datetime.now(),
    )
    allowed = custody.verify_and_commit(good, "authorized_tenant")
    assert allowed is True
    print(f"  Authorized tenant allowed: {allowed}")

    print("  [PASS] Custody failure blocks unauthorized completion demonstrated")
