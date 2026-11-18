"""Focused regression tests for mining-admin defects 1 and 3 (2026-11-17 review).

Defect 1 - anomaly state was unreachable: ``inject_anomaly()`` set instance
state that ``get_status()`` ignored, so an injected anomaly still reported
``HARMONIC_CONSENSUS`` and ``h1 = 0.0``. Fixed by initialising the state in
``__init__`` and reading it in ``get_status()``.

Defect 3 - a new ``DurableTheseusService`` was built per admitted request,
including GETs: every ``/status`` poll appended an admission event (unbounded
journal growth from read traffic) and re-ran bootstrap plus full store
verification. Fixed by one cached handle per audit path, continuity
verification on every request, and admission appends on mutations only.

Defect 2 - the import-time singleton with process-global, unpersisted config
(a restart silently reverts hashrate/warps/voltage/fan/stealth) is NOT covered
here; it needs a persisted-config design and remains open.
"""
import json
from types import SimpleNamespace

import pytest

from chronus.execution.mining_admin import MiningAdminEngine
from chronus.service import mining_operator
from chronus.service.auth_middleware import AuthenticatedIdentity, Role


@pytest.fixture
def admin_env(tmp_path, monkeypatch):
    mining_operator._reset_custody_cache()
    monkeypatch.setenv("CHRONUS_MINING_ADMIN_SUBJECTS", json.dumps(["op-1"]))
    monkeypatch.setenv("CHRONUS_MINING_ADMIN_TENANT_ID", "tenant-1")
    monkeypatch.setenv(
        "CHRONUS_MINING_ADMIN_CUSTODY_PATH", str(tmp_path / "custody.sqlite3")
    )
    monkeypatch.setenv("CHRONUS_JWT_SECRET", "k" * 32)
    monkeypatch.setenv("CHRONUS_DEV_JWT_PERMISSIVE", "0")
    monkeypatch.setattr(
        mining_operator,
        "auth_service",
        SimpleNamespace(check_rate_limit=lambda tenant_id: None),
    )
    yield tmp_path / "custody.sqlite3"
    mining_operator._reset_custody_cache()


def _identity() -> AuthenticatedIdentity:
    return AuthenticatedIdentity(
        tenant_id="tenant-1",
        user_id="op-1",
        roles={Role.SYSTEM_ADMIN},
        claims={"sub": "op-1", "tenant_id": "tenant-1"},
        is_jwt=True,
    )


def _request(method: str, path: str = "/v1/mining/admin/status") -> SimpleNamespace:
    return SimpleNamespace(method=method, url=SimpleNamespace(path=path))


def _journal_entries(custody_path) -> int:
    custody = mining_operator._get_custody(str(custody_path))
    return int(custody.stats()["journal_entries"])


def test_anomaly_state_is_reachable():
    engine = MiningAdminEngine.get_instance()
    engine.execute_dsw_heal()
    status = engine.get_status()
    assert status["consensus_status"] == "HARMONIC_CONSENSUS"
    assert status["sheaf_cohomology_h1"] == 0.0

    engine.inject_anomaly()
    status = engine.get_status()
    assert status["consensus_status"] == "OBSTRUCTED"
    assert status["sheaf_cohomology_h1"] == 1.0

    engine.execute_dsw_heal()
    status = engine.get_status()
    assert status["consensus_status"] == "HARMONIC_CONSENSUS"
    assert status["sheaf_cohomology_h1"] == 0.0


def test_custody_handle_is_reused_per_path(admin_env, tmp_path):
    first = mining_operator._get_custody(str(tmp_path / "a.sqlite3"))
    second = mining_operator._get_custody(str(tmp_path / "a.sqlite3"))
    other = mining_operator._get_custody(str(tmp_path / "b.sqlite3"))
    assert first is second
    assert first is not other


def test_get_does_not_append_but_post_does(admin_env):
    identity = _identity()
    get_request = _request("GET")
    post_request = _request("POST", "/v1/mining/admin/start")

    assert mining_operator.get_mining_admin_operator(get_request, identity) == "tenant-1"
    after_get = _journal_entries(admin_env)
    assert mining_operator.get_mining_admin_operator(get_request, identity) == "tenant-1"
    after_get_again = _journal_entries(admin_env)
    assert after_get == after_get_again  # read traffic does not grow the journal

    mining_operator.get_mining_admin_operator(post_request, identity)
    after_post = _journal_entries(admin_env)
    assert after_post == after_get + 1  # mutations append exactly one event


def test_get_fails_closed_when_custody_unavailable(admin_env, tmp_path, monkeypatch):
    blocker = tmp_path / "blocker.txt"
    blocker.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv(
        "CHRONUS_MINING_ADMIN_CUSTODY_PATH", str(blocker / "custody.sqlite3")
    )
    mining_operator._reset_custody_cache()
    with pytest.raises(Exception) as excinfo:
        mining_operator.get_mining_admin_operator(_request("GET"), _identity())
    assert "durable audit unavailable" in str(excinfo.value)
