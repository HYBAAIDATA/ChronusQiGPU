"""Local elevation runner — IDE agent entrypoint.

Runs Phases 1–3 code elevation tests and writes production readiness report.
Does not download datasets or LLMs (procured separately).

Usage:
  export PYTHONPATH=python_backend
  python3 -m hyba_data.local_elevation_runner
"""

from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts" / "hyba_data" / "elevation"


def _run(name: str, fn: Callable[[], Any]) -> Tuple[str, bool, Any]:
    try:
        out = fn()
        return name, True, out
    except Exception as e:
        traceback.print_exc()
        return name, False, {"error": type(e).__name__, "message": str(e)}


def phase1_reconciliation() -> Dict[str, Any]:
    from hyba_data.external_metrics import (
        M1_RATIO,
        SENSITIVITY_M,
        assert_external_ratio_allowed,
        claim_lane_snapshot,
        external_copy_ok,
        external_metric_pack,
    )

    assert abs(M1_RATIO - 2.62) < 1e-9
    assert tuple(SENSITIVITY_M) == (1.5, 2.0, 2.6)
    assert_external_ratio_allowed(2.0)
    assert_external_ratio_allowed(2.62)
    try:
        assert_external_ratio_allowed(6.94)
        raise AssertionError("M2 should not pass external without measured")
    except PermissionError:
        pass
    bad = external_copy_ok("We deliver 6.94× SaaS seats with maintenance fee")
    assert bad["allowed"] is False
    good = external_copy_ok("Fold eligible sets, measure, gain-share. Geometry of information.")
    assert good["allowed"] is True
    pack = external_metric_pack()
    snap = claim_lane_snapshot()
    return {"pack": pack, "lanes": snap, "copy_gate": {"bad": bad, "good": good}}


def phase2_code_elevation() -> Dict[str, Any]:
    from hyba_data.gpuizer import run_gpuizer_benchmark
    from hyba_data.sdk_core import VERSION, demo_m1
    from hyba_data.storage_engine import run_storage_spike

    gpu = run_gpuizer_benchmark(n=2048, artifact_dir=ART)
    demo = demo_m1(n=256)
    assert demo["passed_gate"] is True
    store = run_storage_spike(artifact_dir=ART)
    assert store["passed"] is True
    return {
        "sdk_version": VERSION,
        "gpuizer": {k: gpu[k] for k in gpu if k != "sensitivity"} | {"sensitivity": gpu.get("sensitivity")},
        "sdk_demo": demo,
        "storage": store,
    }


def phase3_ciaas() -> Dict[str, Any]:
    from hyba_data.pricing_dashboard import write_dashboard_artifact
    from hyba_data.savings_metering import compute_savings

    dash = write_dashboard_artifact(s_memory=1_000_000.0, f=0.4, artifact_dir=ART)
    un = compute_savings(s_memory=1e6, f=0.4, m_eff=2.0, measured=False)
    me = compute_savings(s_memory=1e6, f=0.4, m_eff=2.0, measured=True)
    assert un.hyba_fee == 0.0
    assert me.hyba_fee > 0.0
    # unmeasured M2 blocked
    try:
        compute_savings(s_memory=1e6, f=0.4, m_eff=6.94, measured=False)
        raise AssertionError("M2 unmeasured should fail")
    except PermissionError:
        pass
    return {"dashboard": dash, "fee_unmeasured": un.hyba_fee, "fee_measured": me.hyba_fee}


def phase_existing_suite() -> Dict[str, Any]:
    """Run critical existing modules (summary only)."""
    import hyba_data.test_doctrine_compliance as tdc
    import hyba_data.test_elevation_standard as tes
    import hyba_data.test_fold_fidelity as tff
    import hyba_data.test_phi1_runtime as tpr

    results = {}
    for name, mod in [
        ("doctrine", tdc),
        ("fold_fidelity", tff),
        ("elevation_standard", tes),
        ("phi1_runtime", tpr),
    ]:
        rc = mod.main()
        results[name] = {"rc": rc, "passed": rc == 0}
        if rc != 0:
            raise RuntimeError(f"{name} suite failed rc={rc}")
    return results


def main() -> int:
    ART.mkdir(parents=True, exist_ok=True)
    steps: List[Tuple[str, Callable[[], Any]]] = [
        ("phase1_reconciliation", phase1_reconciliation),
        ("phase2_code_elevation", phase2_code_elevation),
        ("phase3_ciaas", phase3_ciaas),
        ("phase_existing_suite", phase_existing_suite),
    ]
    report: Dict[str, Any] = {
        "title": "HYBA PHI-1 Local Elevation Runner",
        "doctrine": "geometry + measure + gain-share",
        "elevation_rule": "We elevate code to meet documentation, always.",
        "phases": {},
        "failed": [],
    }
    for name, fn in steps:
        print(f"=== {name} ===")
        n, ok, out = _run(name, fn)
        report["phases"][n] = {"ok": ok, "result": out if ok else out}
        if ok:
            print("PASS", name)
        else:
            print("FAIL", name, out)
            report["failed"].append(name)
    report["passed"] = len(report["failed"]) == 0
    report["summary"] = (
        "HYBA PHI-1 Portfolio — Geometry of Information. "
        "Fold. Never Truncate. Eligible sets → measure → gain-share. "
        "CIaaS = measured truth, not seats. Quantum stays the moat, not the cold open."
    )
    out_path = ART / "LOCAL_ELEVATION_REPORT.json"
    out_path.write_text(json.dumps(report, indent=2, default=str))
    # production readiness marker
    ready = {
        "production_ready_local": report["passed"],
        "pythonpath": "python_backend",
        "entrypoints": [
            "python3 -m hyba_data.local_elevation_runner",
            "bash scripts/run_local_elevation.sh",
            "bash scripts/zip_local_production.sh",
        ],
        "procure_separately": ["LLM weights", "large datasets", "customer T3 telemetry"],
        "report": str(out_path),
    }
    (ART / "LOCAL_PRODUCTION_READY.json").write_text(json.dumps(ready, indent=2))
    print(json.dumps({"passed": report["passed"], "failed": report["failed"], "report": str(out_path)}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
