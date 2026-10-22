"""Uptime pack + multi-cloud certificate packs — INTERNAL production proof."""

from __future__ import annotations

import json
import traceback
from pathlib import Path

from hyba_data.claim_closures import availability_measurement_pack, issue_multi_cloud_certificates
from hyba_data.sealed_claims import ClaimLane, get_claim, may_leave_ecosystem


def test_uptime_pack_internal():
    pack = availability_measurement_pack(window_hours=1.0)
    assert pack["lane"] == "INTERNAL"
    assert pack["external_ok"] is False
    assert pack["claim_id"] == "TECH_99999"
    art = Path("artifacts/hyba_data")
    art.mkdir(parents=True, exist_ok=True)
    # long-window method card (still INTERNAL — no fake 30-day production)
    sealed = {
        **pack,
        "title": "Uptime Measurement Pack",
        "status": "INTERNAL_METHOD_SEALED",
        "long_window_requirement_hours": 24 * 30,
        "note": "Method implemented; EXTERNAL 99.999% requires long-window evidence",
        "ci_test": "test_uptime_and_multicloud_packs.py",
    }
    (art / "UPTIME_PACK.json").write_text(json.dumps(sealed, indent=2))
    c = get_claim("TECH_99999")
    assert c.lane == ClaimLane.INTERNAL


def test_multicloud_certs_strategy_not_proven():
    certs = issue_multi_cloud_certificates()
    assert certs["unblocked"] is True
    assert len(certs["certificates"]) == 3
    for c in certs["certificates"]:
        assert c["status"] == "IMPLEMENTED_STUB"
        assert c["evidence"]["proven_production"] is False
    assert may_leave_ecosystem("TECH_MULTICLOUD_STRATEGY") is True
    assert may_leave_ecosystem("TECH_MULTICLOUD_PROVEN") is False
    art = Path("artifacts/hyba_data")
    art.mkdir(parents=True, exist_ok=True)
    pack = {
        "title": "Multi-cloud Certificate Pack",
        "strategy_lane": "EXTERNAL",
        "production_lane": "INTERNAL",
        "providers": certs["certificates"],
        "ci_evidence": "doctrine_enforcement + hyba-data-engineering-standard workflows",
        "named_provider_requirements": [
            "Cluster ID + region",
            "Deploy manifest hash",
            "Healthcheck log window",
            "Board seal of PROVEN status",
        ],
        "status": "INTERNAL_PRODUCTION_PROOF",
    }
    (art / "MULTICLOUD_CERTIFICATE_PACK.json").write_text(json.dumps(pack, indent=2))


def main() -> int:
    failed = 0
    for name in sorted(n for n in globals() if n.startswith("test_")):
        try:
            globals()[name]()
            print("PASS", name)
        except Exception as e:
            failed += 1
            print("FAIL", name, type(e).__name__, e)
            traceback.print_exc()
    print(f"summary failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
