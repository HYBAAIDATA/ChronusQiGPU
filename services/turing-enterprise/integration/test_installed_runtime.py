"""Non-skipping canonical-runtime gate; run ONLY after installing actual VQC/Kellogg.

A mock is deliberately not an alternative here. Missing dependencies fail CI.
This is a service integration smoke test, not full mathematical qualification.
"""

from importlib.metadata import version
from hyba_turing_service.runtime import ProcessRuntime, DurableRuntime, ResultCustody


def test_installed_canonical_runtime_and_durable_report(tmp_path):
    assert version("hyba-turing-vqc")
    assert version("hyba-kellogg-tensor")
    custody = ResultCustody(tmp_path / "custody")
    runtime = DurableRuntime(ProcessRuntime(timeout=60), custody, "canonical-tenant", "bell")
    report = runtime.run(
        {
            "qasm": 'OPENQASM 2.0; include "qelib1.inc"; qreg q[2]; h q[0]; cx q[0],q[1];',
            "shots": 32,
            "seed": 7,
        }
    )
    assert report["schema"] == "turing.vqc.pipeline_report.v1"
    assert report["verdict"] == "PASS"
    assert report["certificate"] and report["witness"]
    stages = {s["stage"]: s["state"] for s in report["stages"]}
    assert stages["execution"] == stages["verification"] == "PASS"
    assert len(list((tmp_path / "custody").rglob("*.json"))) == 1
