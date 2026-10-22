"""Real local API -> durable queue -> canonical worker -> report workflow.

Identity/JWKS/contract approvals use explicit cryptographic TEST fixtures.
Execution, SQLite, subprocess isolation and file custody use actual owner code.
No real enterprise SSO, SharedTuring-wide custody or production actuation is claimed.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from test_enterprise import service, headers  # noqa: E402,F401
from test_control import REQUEST  # noqa: E402
from hyba_turing_service.supervisor import Supervisor  # noqa: E402


def test_actual_api_worker_result_recovery_and_scope(service):
    s = service
    body = {"project": "p", "job": "real-bell", "request": REQUEST}
    path = "/api/customer/a/jobs"
    h = headers(s, "bob")
    admitted = s.client.post(path, headers=h, json=body)
    assert admitted.status_code == 200 and admitted.json()["state"] == "admitted"
    # Same-key retries do not create another durable job.
    assert s.client.post(path, headers=h, json=body).status_code == 200
    worker = Supervisor(s.factory, lambda: s.op, "operator", s.tmp / "custody-real")
    assert worker.run_once() is True
    assert worker.run_once() is False
    result = s.client.get(path + "/real-bell", headers=h)
    assert result.status_code == 200
    value = result.json()
    assert value["state"] == "completed"
    report = value["report"]
    assert report["verdict"] == "PASS"
    assert report["certificate"] and report["witness"]
    stages = {stage["stage"]: stage["state"] for stage in report["stages"]}
    assert stages["execution"] == stages["verification"] == "PASS"
    assert len(list((s.tmp / "custody-real").rglob("*.json"))) == 1
    facts = s.plane.usage(s.admin, "alice", tenant="a")
    assert len(facts) == 1 and facts[0]["chargeable"] is False
    # Recovery retrieves retained evidence, never another execution/charge.
    assert s.client.get(path + "/real-bell", headers=h).json() == value
    assert s.client.get("/api/customer/foreign/jobs/real-bell", headers=h).status_code == 403
    s.plane.set_member(s.admin, "alice", tenant="a", member="bob", role="analyst", active=False)
    assert s.client.get(path + "/real-bell", headers=h).status_code == 403
    assert s.plane.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1
