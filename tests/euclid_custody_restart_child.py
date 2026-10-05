"""Child process for the THESEUS custody restart-verification test.

Run as ``python tests/euclid_custody_restart_child.py <custody_root> <record_id> <key_hex> <state_dir>``.

Restart evidence must come from a genuinely separate interpreter: an
in-process "reload" proves nothing about durable state, because the same
process may still hold live objects that the next read quietly trusts.
This child opens THESEUS enterprise custody fresh, reads the custodied
checkpoint, restores the runtime through the production restore path, and
reports what the restored organism actually reaches. It exits nonzero on
any verification failure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "chronus" / "mla1517_platform" / "python"))


def main() -> int:
    custody_root, record_id, key_hex, state_dir = sys.argv[1:5]

    from aethel.enterprise.custody import EnterpriseCustody
    from euclid.runtime import EuclidRuntime

    custody = EnterpriseCustody(custody_root, hmac_key=bytes.fromhex(key_hex))
    try:
        runtime = EuclidRuntime.restore_from_custody(custody, record_id, state_dir=state_dir)
    finally:
        custody.close()

    try:
        organism = runtime.startup_report()["organism"]
        readiness = runtime.startup_report()["intelligence_readiness"]
        restart_record = next(
            record for record in runtime.evidence.records if record.kind == "custody-restart"
        )
        result = {
            "organs": sorted(item["organ_id"] for item in runtime.registry.report()),
            "specialists": organism["specialists"],
            "evidence_head": runtime.evidence.head,
            "restored_evidence_head": restart_record.payload["restored_evidence_head"],
            "restart_stage": (
                runtime.reachability.stage("euclid.runtime").name
                if runtime.reachability.stage("euclid.runtime") is not None
                else None
            ),
            "readiness": readiness,
        }
        # The restored organism must still dispatch, not just report organs.
        out = runtime.dispatch_specialist(
            "turing",
            {"operation": "capability-matrix"},
            tenant_id="tenant-a",
            actor="user-1",
        )
        result["post_restart_dispatch"] = {
            "allowed": out["allowed"],
            "owner": out.get("result", {}).get("owner"),
        }
    finally:
        runtime.close()
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
