"""Local scope/security regressions. No real IdP, billing or runtime is contacted."""

import base64
import importlib
import json
from pathlib import Path
import sys

import pytest

from hyba_turing_service.api import create_app
from hyba_turing_service.commercial import validate_scope
from hyba_turing_service.control import Unavailable
from test_control import REQUEST
from test_enterprise import service, headers


def test_scope_defaults_to_deferred():
    config = {}
    validate_scope(config)
    assert config == {"billing_scope": "deferred"}


@pytest.mark.parametrize(
    "change",
    [
        {"billing_scope": "active"},
        {"billing_scope": "hermitten"},
        {"billing_url": "https://billing.invalid"},
        {"billing_token_file": "/secret"},
        {"billing_import_path": "/v1/import"},
        {"require_spend": True},
    ],
)
def test_unapproved_commercial_wiring_is_rejected(change):
    with pytest.raises(ValueError):
        validate_scope(change)


def test_scope_preserves_real_contract_and_membership_gates(service):
    s = service
    assert s.deps.require_spend is False
    # Deferred charging never grants an analyst commercial-admin access.
    assert s.client.get("/api/customer/a/billing", headers=headers(s, "bob")).status_code == 403
    assert s.client.get("/api/customer/a/billing", headers=headers(s)).status_code == 503
    assert (
        s.client.post("/api/customer/a/spend-limit", json={}, headers=headers(s)).status_code == 503
    )
    assert (
        s.client.post(
            "/api/ops/billing/deliver", json={}, headers=headers(s, "operator")
        ).status_code
        == 503
    )
    assert (
        s.client.post("/api/ops/billing/deliver", json={}, headers=headers(s, "bob")).status_code
        == 403
    )
    assert s.plane.db.execute("SELECT COUNT(*) FROM spend_intents").fetchone()[0] == 0
    s.plane.lifecycle(
        s.op, "operator", tenant="a", state="suspended", command="pause", reason="approved test"
    )
    result = s.client.post(
        "/api/customer/a/jobs",
        headers=headers(s, "bob"),
        json={"project": "p", "job": "denied", "request": REQUEST},
    )
    assert result.status_code == 403
    assert s.plane.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0


@pytest.mark.parametrize("billing,spend", [(object(), False), (None, True)])
def test_api_refuses_unapproved_provider_even_if_injected(service, billing, spend):
    service.deps.billing = billing
    service.deps.require_spend = spend
    with pytest.raises(ValueError):
        create_app(service.deps)


def test_real_sql_history_search_filter_cursor_and_project_isolation(service):
    s = service
    for job in ("alpha", "beta", "gamma"):
        s.plane.submit_project(s.analyst, "bob", tenant="a", project="p", job=job, request=REQUEST)
        s.plane.request_cancel(s.analyst, "bob", tenant="a", job=job)
    s.plane.submit_project(
        s.admin, "alice", tenant="a", project="private", job="secret", request=REQUEST
    )
    base = "/api/customer/a/jobs"
    h = headers(s, "bob")
    first = s.client.get(base, params={"limit": 1}, headers=h).json()
    assert [r["job"] for r in first["jobs"]] == ["alpha"]
    assert first["next_cursor"] == "alpha"
    second = s.client.get(
        base, params={"limit": 1, "after": first["next_cursor"]}, headers=h
    ).json()
    assert [r["job"] for r in second["jobs"]] == ["beta"]
    third = s.client.get(
        base, params={"limit": 1, "after": second["next_cursor"]}, headers=h
    ).json()
    assert [r["job"] for r in third["jobs"]] == ["gamma"]
    assert third["next_cursor"] is None
    assert [
        r["job"]
        for r in s.client.get(
            base, params={"q": "ALP", "state": "cancelled", "project": "p"}, headers=h
        ).json()["jobs"]
    ] == ["alpha"]
    for params in ({"project": "private"}, {"q": "%' OR 1=1 --"}, {"q": "%"}, {"state": "running"}):
        assert s.client.get(base, params=params, headers=h).json()["jobs"] == []
    assert s.client.get(base, params={"state": "invented"}, headers=h).status_code == 422
    assert s.client.get(base, params={"q": "x" * 201}, headers=h).status_code == 422
    assert s.client.get("/api/customer/foreign/jobs", headers=h).status_code == 403
    # Current membership, not the previously issued identity or page state, governs access.
    s.plane.set_member(s.admin, "alice", tenant="a", member="bob", role="analyst", active=False)
    assert s.client.get(base, headers=h).status_code == 403


def config_file(tmp_path):
    config = json.loads((Path(__file__).parents[1] / "deploy/service.example.json").read_text())
    config.update(
        database=str(tmp_path / "service.db"),
        custody_root=str(tmp_path / "custody"),
        operator_subjects=["operator"],
        approver_subjects=["approver"],
        source_commit="a" * 40,
        build_identity_file=str(tmp_path / "commit"),
    )
    (tmp_path / "commit").write_text("a" * 40)
    for key, value in [("customer_key_file", b"c" * 32), ("operator_key_file", b"o" * 32)]:
        f = tmp_path / key
        f.write_text(base64.b64encode(value).decode())
        f.chmod(0o600)
        config[key] = str(f)
    from cryptography.fernet import Fernet

    f = tmp_path / "session-key"
    f.write_bytes(Fernet.generate_key())
    f.chmod(0o600)
    config["session_key_file"] = str(f)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    return path


def test_configuration_production_does_not_require_financial_authority(tmp_path):
    module = importlib.import_module("hyba_turing_service.main")
    config, customer, operator, claims, factory, tokens, billing = module.configuration(
        config_file(tmp_path)
    )
    assert config["mode"] == "production" and config["billing_scope"] == "deferred"
    assert billing is None
    plane = factory()
    try:
        assert plane.require_spend is False
    finally:
        plane.close()


def test_production_composition_readiness_independent_of_billing(tmp_path, monkeypatch):
    module = importlib.import_module("hyba_turing_service.main")
    config = config_file(tmp_path)
    captured = {}
    approval_calls = []
    # Composition-only doubles: not real runtime, IdP or deployment acceptance.
    monkeypatch.setattr(module, "OIDCVerifier", lambda *a: object())
    monkeypatch.setattr(module, "Sessions", lambda *a, **k: object())

    class Probe:
        def __init__(self, **kwargs):
            pass

        def run(self, request):
            return {"verdict": "PASS", "certificate": {"fixture": True}}

    monkeypatch.setattr(module, "ProcessRuntime", Probe)
    monkeypatch.setattr(module, "verify_bundle", lambda *a, **k: approval_calls.append(True))
    monkeypatch.setattr(module, "create_app", lambda deps: captured.setdefault("deps", deps))
    import uvicorn

    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: None)
    monkeypatch.setattr(sys, "argv", ["turing-service", "serve", "--config", str(config)])
    module.main()
    assert captured["deps"].billing is None and captured["deps"].require_spend is False
    assert captured["deps"].readiness() is True
    assert len(approval_calls) >= 2

    def deny(*args, **kwargs):
        raise Unavailable("missing promotion evidence")

    monkeypatch.setattr(module, "verify_bundle", deny)
    with pytest.raises(Unavailable):
        module.main()


def test_signed_release_preserves_every_nonfinancial_gate(tmp_path):
    import hashlib
    import time
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from hyba_turing_service.release import GATES, verify_bundle
    from hyba_turing_service.control import canonical

    assert GATES == frozenset(
        {
            "runtime_integration",
            "identity_security",
            "recovery_load",
            "package_qualification",
            "commercial_approval",
        }
    )
    key = Ed25519PrivateKey.generate()
    public = base64.b64encode(
        key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    ).decode()
    now = int(time.time())
    (tmp_path / "evidence.txt").write_text("TEST FIXTURE ONLY, NOT RELEASE APPROVAL")
    entry = dict(
        state="PASS",
        reviewer="fixture-reviewer",
        executed_at=now,
        artifact="evidence.txt",
        sha256=hashlib.sha256((tmp_path / "evidence.txt").read_bytes()).hexdigest(),
    )
    manifest = dict(
        schema="turing.promotion.v1",
        commit="test",
        billing_scope="deferred",
        issued_at=now,
        expires_at=now + 60,
        gates={g: entry for g in GATES},
    )

    def write(value):
        (tmp_path / "approval.json").write_text(
            json.dumps(
                {
                    "manifest": value,
                    "signature": base64.b64encode(key.sign(canonical(value).encode())).decode(),
                }
            )
        )

    write(manifest)
    assert verify_bundle(tmp_path, public, "test")["billing_scope"] == "deferred"
    for gate in GATES:
        bad = {**manifest, "gates": {k: v for k, v in manifest["gates"].items() if k != gate}}
        write(bad)
        with pytest.raises(Unavailable):
            verify_bundle(tmp_path, public, "test")
    for scope in (None, "active", "hermitten"):
        write({**manifest, "billing_scope": scope})
        with pytest.raises(Unavailable):
            verify_bundle(tmp_path, public, "test")
    write(manifest)
    with pytest.raises(Unavailable):
        verify_bundle(tmp_path, public, "test", publication=True)


def test_denied_operations_are_durably_audited_without_identity_leaks(service):
    import hashlib

    s = service
    result = s.client.get("/api/customer/foreign-sensitive-tenant/jobs", headers=headers(s, "bob"))
    assert result.status_code == 403
    rows = [json.loads(r["payload"]) for r in s.plane.db.execute("SELECT payload FROM audit")]
    denied = [r for r in rows if r["action"] == "authorization_denied"]
    assert len(denied) == 1
    event = denied[0]
    assert event["tenant"] == "__service_security__"
    assert event["actor"] == hashlib.sha256(b"bob").hexdigest()
    assert event["detail"]["request_id"] == result.headers["x-request-id"]
    assert (
        event["detail"]["target_digest"] == hashlib.sha256(b"foreign-sensitive-tenant").hexdigest()
    )
    assert "foreign-sensitive-tenant" not in json.dumps(event)
    assert '"bob"' not in json.dumps(event)
    assert "authorization" not in event["detail"]
    # No unrelated operation or charge is created by denial logging.
    assert s.plane.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
    assert s.plane.db.execute("SELECT COUNT(*) FROM spend_intents").fetchone()[0] == 0


def test_denial_audit_storage_failure_never_authorizes_operation(service, monkeypatch):
    s = service

    def fail(*a, **k):
        raise OSError("audit unavailable")

    monkeypatch.setattr(s.plane.__class__, "_audit", fail)
    response = s.client.get("/api/customer/foreign/jobs", headers=headers(s, "bob"))
    assert response.status_code == 503
    assert response.json()["error"] == "request unavailable"
    assert s.plane.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
