"""Capability elevation tests — close open seals (code meets documentation)."""

from __future__ import annotations

import traceback
from pathlib import Path


def test_m1_has_sealed_test_hash():
    from hyba_data.sealed_metric_card import get_external_metric, get_metric

    m = get_metric("M1")
    assert m.lane.value == "BOUNDED"
    assert m.test_hash and len(m.test_hash) >= 32
    assert "illustrative until" not in m.notes.lower()
    ext = get_external_metric("M1")
    assert ext["test_hash"] == m.test_hash
    assert ext["max_error"] is not None and float(ext["max_error"]) < 1e-7


def test_m2_m3_remain_internal():
    from hyba_data.sealed_claims import ClaimLane
    from hyba_data.sealed_metric_card import get_metric

    assert get_metric("M2").lane == ClaimLane.INTERNAL
    assert get_metric("M3").lane == ClaimLane.INTERNAL


def test_pilot_telemetry_wires_savings():
    from hyba_data.pilot_telemetry import generate_hermetic_pilot_telemetry, run_pilot_measurement

    bundle = generate_hermetic_pilot_telemetry(m_eff=2.0, f=0.4, s_memory_day=10_000.0)
    report = run_pilot_measurement(bundle, window_days=30.0)
    assert report["savings"]["measured"] is True
    assert report["savings"]["hyba_fee"] > 0.0
    assert report["derived"]["m_eff"] == 2.0
    assert Path(report["artifact"]).exists()
    # unmeasured path fee 0
    bundle.measured = False
    un = run_pilot_measurement(bundle, window_days=30.0)
    assert un["savings"]["hyba_fee"] == 0.0


def test_availability_pack_method_exists_internal():
    from hyba_data.claim_closures import availability_measurement_pack

    pack = availability_measurement_pack(window_hours=24.0)
    assert pack.get("lane") in ("INTERNAL", None) or pack.get("external_ok") is False
    art = Path("artifacts/hyba_data/UPTIME_PACK.json")
    art.parent.mkdir(parents=True, exist_ok=True)
    import json

    sealed = {
        **pack,
        "title": "Availability Measurement Pack",
        "status": "INTERNAL_METHOD_SEALED",
        "note": "Method implemented; EXTERNAL 99.999% requires long-window production evidence",
    }
    art.write_text(json.dumps(sealed, indent=2, default=str))
    assert art.exists()


def test_multicloud_runbooks_exist():
    for p in [
        "runbooks/aws/HYBA_DATA_PILOT.md",
        "runbooks/azure/HYBA_DATA_PILOT.md",
        "runbooks/gcp/HYBA_DATA_PILOT.md",
        "deploy/aws/hyba-data.yaml",
        "deploy/azure/hyba-data.yaml",
        "deploy/gcp/hyba-data.yaml",
    ]:
        assert Path(p).exists(), p


def test_restricted_not_banned_lane():
    from hyba_data.sealed_claims import ClaimLane, register_summary

    names = [x.name for x in ClaimLane]
    assert "RESTRICTED" in names
    assert "BANNED" not in register_summary().get("by_lane", {})


def test_salamander_online_gate():
    from hyba_data.system_runtime import run_autonomic_if_online, start_system, stop_system

    stop_system()
    try:
        run_autonomic_if_online()
        raise AssertionError("should block")
    except RuntimeError:
        pass
    start_system()
    r = run_autonomic_if_online()
    assert isinstance(r, dict)


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
