"""Real installed VQC, subprocess, AL HARAS signatures, SQLite and service receipt.

The isolated TEST custody/signing keys are not production credentials. The
injected failure is after genuine computation and durability, not a fake result.
This proves service-report recovery, not canonical shared-custody actuation.
"""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from test_control import env, REQUEST  # noqa: E402,F401
from hyba_turing_service.runtime import ProcessRuntime, DurableRuntime, ResultCustody  # noqa: E402


class ObservedProcessRuntime(ProcessRuntime):
    """Instrumentation only: execution delegates to the actual installed worker."""

    calls = 0

    def run(self, request):
        self.calls += 1
        return super().run(request)


def test_real_worker_completion_recovers_after_database_audit_interruption(
    env, tmp_path, monkeypatch
):
    p, ops, customer, _, onboard, reopen, *_ = env
    onboard()
    p.submit(customer, "alice", tenant="a", job="real-recovery", request=REQUEST)
    key = b"ISOLATED-TEST-RECOVERY-AUTHORITY-NOT-PRODUCTION" * 2
    root = tmp_path / "actual-service-custody"
    custody = ResultCustody(root, integrity_key=key)
    runtime = ObservedProcessRuntime(timeout=60)
    durable = DurableRuntime(
        runtime,
        custody,
        "a",
        "real-recovery",
        admission_hash=p._job("a", "real-recovery")["request_hash"],
    )
    original_audit = p._audit

    def fail_completion_audit(tenant, actor, action, detail):
        if action == "complete":
            raise OSError("TEST durable completion interruption")
        return original_audit(tenant, actor, action, detail)

    with monkeypatch.context() as change:
        change.setattr(p, "_audit", fail_completion_audit)
        with pytest.raises(OSError):
            p.execute(ops, "operator", tenant="a", job="real-recovery", runtime=durable)
    assert p._job("a", "real-recovery")["state"] == "running"
    assert p.usage(customer, "alice", tenant="a") == []
    assert runtime.calls == 1
    recovered = reopen()
    try:
        report = recovered.recover_result(
            ops,
            "operator",
            tenant="a",
            job="real-recovery",
            reason="TEST after retained real execution",
            source=ResultCustody(root, integrity_key=key),
        )
        assert report["verdict"] == "PASS"
        assert report["certificate"] and report["witness"] and report["result"]
        stages = {item["stage"]: item["state"] for item in report["stages"]}
        assert stages["execution"] == stages["verification"] == "PASS"
        assert recovered._job("a", "real-recovery")["state"] == "completed"
        assert recovered.reconcile(ops, "operator")["issues"] == []
        facts = recovered.usage(customer, "alice", tenant="a")
        assert len(facts) == 1 and facts[0]["chargeable"] is False
        assert runtime.calls == 1
    finally:
        recovered.close()


def test_actual_process_exit_after_receipt_then_fresh_process_recovers(env, tmp_path):
    """Exit the dispatcher inside its completion transaction; recover elsewhere."""
    import json
    import os
    import subprocess

    p, _, customer, _, onboard, *_ = env
    onboard()
    p.submit(customer, "alice", tenant="a", job="process-recovery", request=REQUEST)
    database = p.db.execute("PRAGMA database_list").fetchone()[2]
    script = r"""
import importlib.util, json, sys, os
from pathlib import Path
from hyba_turing_service.control import ControlPlane
from hyba_turing_service.runtime import ProcessRuntime, DurableRuntime, ResultCustody
settings = json.loads(sys.stdin.read())
spec = importlib.util.spec_from_file_location("actual_recovery_test_authority", settings["authority"])
auth = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = auth
spec.loader.exec_module(auth)
customer = auth.SubscriptionAuthority({"test": b"c" * 32}, "customer-test")
operator = auth.SubscriptionAuthority({"test": b"o" * 32}, "operator-test")
token = operator.issue(auth.SubscriptionClaims(
    subscription_id="process-test", tenant_id="__service_ops__", issuer=operator.issuer,
    key_id="test", capabilities=("turing.ops.manage", "turing.ops.execute"),
    actors=("operator",), not_before=0, expires_at=2000,
))
plane = ControlPlane(settings["database"], customer_authority=customer,
    operator_authority=operator, clock=lambda: 1000)
custody = ResultCustody(settings["custody"], integrity_key=b"ISOLATED-PROCESS-RECOVERY-TEST-KEY" * 2)
try:
    if settings["action"] == "execute":
        previous = plane._audit
        def abrupt_exit(tenant, actor, action, detail):
            if action == "complete":
                os._exit(73)
            return previous(tenant, actor, action, detail)
        plane._audit = abrupt_exit
        row = plane._job("a", "process-recovery")
        runtime = DurableRuntime(ProcessRuntime(timeout=60), custody, "a", "process-recovery",
            admission_hash=row["request_hash"])
        plane.execute(token, "operator", tenant="a", job="process-recovery", runtime=runtime)
        raise RuntimeError("expected injected abrupt exit was not reached")
    else:
        report = plane.recover_result(token, "operator", tenant="a", job="process-recovery",
            reason="TEST new-process recovery", source=custody)
        print(json.dumps({"verdict": report["verdict"],
            "state": plane._job("a", "process-recovery")["state"],
            "events": plane.db.execute("SELECT COUNT(*) FROM usage").fetchone()[0]}))
finally:
    plane.close()
"""
    settings = dict(
        database=database,
        custody=str(tmp_path / "cross-process-custody"),
        authority=str(Path(__file__).resolve().parents[3] / "al_haras/entitlements.py"),
    )
    clean_env = {
        key: os.environ[key] for key in ("PATH", "LANG", "SYSTEMROOT") if key in os.environ
    }
    clean_env["PYTHONNOUSERSITE"] = "1"
    first = subprocess.run(
        [sys.executable, "-c", script],
        input=json.dumps({**settings, "action": "execute"}),
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=clean_env,
        timeout=90,
    )
    assert first.returncode == 73, first.stderr
    assert p._job("a", "process-recovery")["state"] == "running"
    second = subprocess.run(
        [sys.executable, "-c", script],
        input=json.dumps({**settings, "action": "recover"}),
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=clean_env,
        timeout=30,
    )
    assert second.returncode == 0, second.stderr
    assert json.loads(second.stdout) == {"verdict": "PASS", "state": "completed", "events": 1}
