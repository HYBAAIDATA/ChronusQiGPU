"""Real signed AL HARAS and OIDC tokens. HTTP/runtime peers are explicit doubles."""

from contextlib import contextmanager
import base64
import hashlib
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa, ed25519
from cryptography.hazmat.primitives import serialization
from fastapi.testclient import TestClient
import jwt
import pytest

from hyba_turing_service.api import Dependencies, create_app
from hyba_turing_service.control import Conflict, Denied, Unavailable, digest, canonical
from hyba_turing_service.enterprise import EnterprisePlane
from hyba_turing_service.identity import OIDCVerifier, Identity
from hyba_turing_service.runtime import ProcessRuntime, ResultCustody
from hyba_turing_service.sessions import Sessions
from hyba_turing_service.supervisor import Supervisor
from hyba_turing_service.release import verify_bundle, GATES
from hyba_turing_service.billing import HermittenClient, deliver_commercial
from test_control import AUTH, RuntimeDouble, REQUEST, BillingDouble


@pytest.fixture
def service(tmp_path):
    now = int(time.time())
    customer = AUTH.SubscriptionAuthority({"test": b"c" * 32}, "customer")
    operator = AUTH.SubscriptionAuthority({"test": b"o" * 32}, "operator")
    database = str(tmp_path / "service.db")

    def factory():
        return EnterprisePlane(
            database, customer_authority=customer, operator_authority=operator, capacity_slots=3
        )

    def issue(tenant, actor, capabilities, ops=False):
        authority = operator if ops else customer
        return authority.issue(
            AUTH.SubscriptionClaims(
                subscription_id=tenant,
                tenant_id="__service_ops__" if ops else tenant,
                issuer=authority.issuer,
                key_id="test",
                capabilities=tuple(capabilities),
                actors=(actor,),
                not_before=now - 1,
                expires_at=now + 3600,
            )
        )

    op = issue(
        "__service_ops__",
        "operator",
        ["turing.ops.manage", "turing.ops.approve", "turing.ops.execute", "turing.ops.billing"],
        True,
    )
    admin = issue(
        "a", "alice", ["turing.customer.admin", "turing.customer.read", "turing.jobs.submit"]
    )
    analyst = issue("a", "bob", ["turing.customer.read", "turing.jobs.submit"])
    p = factory()
    terms = dict(
        tenant="a",
        billing_account="billing-a",
        contract="contract-a",
        starts=now - 1,
        expires=now + 1000,
        contracted=3,
        allowance=10,
    )
    p.register_approval(
        op,
        "operator",
        approval="approval-a",
        tenant="a",
        contract="contract-a",
        terms_hash=digest(terms),
        expires=now + 1000,
    )
    p.approve_customer(op, "operator", **terms, approval="approval-a", command="create-a")
    p.provision(op, "operator", tenant="a", slots=3, command="slots-a")
    for member, role in [("alice", "admin"), ("bob", "analyst"), ("eve", "viewer")]:
        p.set_member(op, "operator", tenant="a", member=member, role=role, operator=True)
    p.set_project(admin, "alice", tenant="a", project="p", slots=1, allowance=10, members=["bob"])
    p.set_project(admin, "alice", tenant="a", project="private", slots=1, allowance=10, members=[])
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    keys = SimpleNamespace(
        get_signing_key_from_jwt=lambda _: SimpleNamespace(key=private.public_key())
    )
    verifier = OIDCVerifier(
        "https://identity.test", "api", "https://identity.test/keys", key_client=keys
    )

    def identity_token(subject, **overrides):
        claims = dict(iss="https://identity.test", aud="api", sub=subject, iat=now, exp=now + 1000)
        claims.update(overrides)
        return jwt.encode(claims, private, algorithm="RS256", headers={"kid": "test"})

    sessions = Sessions(
        database,
        origin="https://turing.test",
        issuer="https://identity.test",
        client_id="client",
        redirect_uri="https://turing.test/auth/callback",
        authorization_url="https://identity.test/authorize",
        token_url="https://identity.test/token",
        verifier=verifier,
        encryption_key=Fernet.generate_key(),
    )
    deps = Dependencies(
        factory,
        verifier,
        customer,
        operator,
        AUTH.SubscriptionClaims,
        "test",
        frozenset({"operator"}),
        frozenset({"approver"}),
        "https://turing.test",
        sessions,
    )
    client = TestClient(create_app(deps), base_url="https://turing.test")
    yield SimpleNamespace(
        plane=p,
        op=op,
        admin=admin,
        analyst=analyst,
        factory=factory,
        issue=issue,
        identity_token=identity_token,
        client=client,
        sessions=sessions,
        deps=deps,
        private=private,
        now=now,
        tmp=tmp_path,
    )
    client.close()
    p.close()


def headers(s, actor="alice", **kwargs):
    return {"Authorization": "Bearer " + s.identity_token(actor, **kwargs)}


def test_api_authentication_privilege_and_request_bounds(service):
    s = service
    c = s.client
    assert c.get("/api/customer/a/overview").status_code == 403
    assert c.get("/api/customer/a/overview", headers=headers(s)).status_code == 200
    assert c.get("/api/customer/b/overview", headers=headers(s)).status_code == 403
    assert c.get("/api/ops/customers", headers=headers(s)).status_code == 403
    assert c.get("/api/ops/customers", headers=headers(s, "operator")).status_code == 200
    assert c.get("/api/customer/a/members", headers=headers(s, "bob")).status_code == 403
    assert c.get("/api/customer/a/overview", headers=headers(s, exp=s.now - 1)).status_code == 403
    assert c.get("/api/customer/a/overview", headers=headers(s, aud="wrong")).status_code == 403
    assert (
        c.post("/api/customer/a/jobs", headers=headers(s), json={"actor": "operator"}).status_code
        == 422
    )
    assert (
        c.post("/api/customer/a/jobs", headers=headers(s), content="x" * 131073).status_code == 415
    )
    assert (
        c.post(
            "/api/customer/a/jobs",
            headers={**headers(s), "Content-Type": "application/json"},
            content="x" * 131073,
        ).status_code
        == 413
    )
    assert c.get("/health/ready").status_code == 503
    assert c.get("/health/live").status_code == 200


def test_api_projects_submit_isolation_and_immediate_revocation(service):
    s = service
    c = s.client
    p = s.plane
    assert (
        c.post(
            "/api/customer/a/jobs",
            headers=headers(s, "bob"),
            json=dict(project="private", job="forbidden", request=REQUEST),
        ).status_code
        == 403
    )
    response = c.post(
        "/api/customer/a/jobs",
        headers=headers(s, "bob"),
        json=dict(project="p", job="j", request=REQUEST),
    )
    assert response.status_code == 200, response.text
    assert (
        c.post(
            "/api/customer/a/jobs",
            headers=headers(s, "bob"),
            json=dict(project="p", job="j2", request=REQUEST),
        ).status_code
        == 409
    )
    p.submit_project(s.admin, "alice", tenant="a", project="private", job="secret", request=REQUEST)
    assert c.get("/api/customer/a/jobs/secret", headers=headers(s, "bob")).status_code == 403
    assert [
        r["job"] for r in c.get("/api/customer/a/jobs", headers=headers(s, "bob")).json()["jobs"]
    ] == ["j"]
    p.set_member(
        s.op, "operator", tenant="a", member="bob", role="analyst", active=False, operator=True
    )
    assert c.get("/api/customer/a/overview", headers=headers(s, "bob")).status_code == 403
    runtime = RuntimeDouble()
    with pytest.raises(Denied):
        p.execute(s.op, "operator", tenant="a", job="j", runtime=runtime)
    assert runtime.calls == 0


def test_last_admin_project_budget_and_global_capacity(service):
    s = service
    p = s.plane
    with pytest.raises(Conflict):
        p.set_member(s.admin, "alice", tenant="a", member="alice", role="viewer")
    with pytest.raises(Conflict):
        p.set_project(
            s.admin,
            "alice",
            tenant="a",
            project="oversubscribed",
            slots=2,
            allowance=10,
            members=[],
        )
    with pytest.raises(Conflict):
        p.provision(s.op, "operator", tenant="a", slots=1, command="shrink")
    terms = dict(
        tenant="b",
        billing_account="billing-b",
        contract="contract-b",
        starts=s.now - 1,
        expires=s.now + 1000,
        contracted=1,
        allowance=10,
    )
    p.register_approval(
        s.op,
        "operator",
        tenant="b",
        contract="contract-b",
        approval="b",
        terms_hash=digest(terms),
        expires=s.now + 1000,
    )
    p.approve_customer(s.op, "operator", **terms, approval="b", command="create-b")
    with pytest.raises(Conflict):
        p.provision(s.op, "operator", tenant="b", slots=1, command="slots-b")


def test_commercial_approval_exact_terms_are_required(service):
    s = service
    p = s.plane
    with pytest.raises(Denied):
        p.approve_customer(
            s.op,
            "operator",
            tenant="x",
            billing_account="x",
            contract="x",
            approval="arbitrary-reference",
            starts=0,
            expires=s.now + 500,
            contracted=1,
            allowance=5,
            command="x",
        )
    response = s.client.post(
        "/api/ops/customers/a/approval",
        headers=headers(s, "operator"),
        json=dict(approval="x", contract="x", terms_hash="x", expires=s.now + 100),
    )
    assert response.status_code == 403


def test_session_csrf_logout_and_pkce(service):
    s = service
    c = s.client
    handle = s.sessions.create(Identity("alice", "https://identity.test"))
    c.cookies.set("turing_session", handle, domain="turing.test", path="/")
    session = c.get("/api/session").json()
    assert session["subject"] == "alice"
    payload = dict(member="new", role="viewer", active=True)
    assert c.post("/api/customer/a/members", json=payload).status_code == 403
    valid = {"Origin": "https://turing.test", "X-CSRF-Token": session["csrf"]}
    assert c.post("/api/customer/a/members", json=payload, headers=valid).status_code == 200
    assert (
        c.post(
            "/api/customer/a/members",
            json=payload,
            headers={**valid, "Origin": "https://evil.test"},
        ).status_code
        == 403
    )
    login = c.get("/login", follow_redirects=False)
    assert login.status_code == 303 and "code_challenge_method=S256" in login.headers["location"]
    assert "HttpOnly" in login.headers["set-cookie"] and "Secure" in login.headers["set-cookie"]
    assert c.get("/auth/callback?state=wrong&code=fake").status_code == 403
    assert c.post("/api/logout", json={}, headers=valid).status_code == 200
    assert c.get("/api/session").status_code == 401


def test_queue_custody_outbox_backup_and_restore(service):
    s = service
    p = s.plane
    p.submit_project(s.analyst, "bob", tenant="a", project="p", job="j", request=REQUEST)
    runtime = RuntimeDouble()
    worker = Supervisor(
        s.factory,
        lambda: s.op,
        "operator",
        s.tmp / "custody",
        runtime_factory=lambda cancel: runtime,
    )
    assert worker.run_once() is True
    assert worker.run_once() is False
    assert runtime.calls == 1
    assert p.scoped_job(s.analyst, "bob", tenant="a", job="j")["state"] == "completed"
    assert len(list((s.tmp / "custody").rglob("*.json"))) == 1
    sink = BillingDouble()
    assert p.deliver_usage(s.op, "operator", sink=sink) == 1
    assert deliver_commercial(p, s.op, "operator", sink) == 2
    assert deliver_commercial(p, s.op, "operator", sink) == 0
    p.adjust_usage(
        s.op,
        "operator",
        tenant="a",
        event=p.usage(s.admin, "alice", tenant="a")[0]["event_id"],
        quantity=-1,
        reason="approved credit",
        approval="credit-reference",
        command="credit-1",
    )
    assert deliver_commercial(p, s.op, "operator", sink) == 1
    backup = s.tmp / "backup.db"
    p.backup(s.op, "operator", str(backup))
    restored = EnterprisePlane(
        str(backup),
        customer_authority=s.deps.customer_issuer,
        operator_authority=s.deps.operator_issuer,
        capacity_slots=3,
    )
    try:
        assert restored.reconcile(s.op, "operator")["issues"] == []
    finally:
        restored.close()


def test_renewal_preserves_history_and_resets_only_current_allowance(service):
    s = service
    p = s.plane
    p.submit_project(s.admin, "alice", tenant="a", project="p", job="old", request=REQUEST)
    with pytest.raises(Conflict):
        p.renew(
            s.op,
            "operator",
            tenant="a",
            contract="next",
            approval="not-yet",
            starts=s.now - 1,
            expires=s.now + 1000,
            allowance=1,
            command="premature",
        )
    p.execute(s.op, "operator", tenant="a", job="old", runtime=RuntimeDouble())
    terms = dict(
        tenant="a",
        billing_account="billing-a",
        contract="next",
        starts=s.now - 1,
        expires=s.now + 1000,
        contracted=3,
        allowance=1,
    )
    p.register_approval(
        s.op,
        "operator",
        tenant="a",
        contract="next",
        approval="next",
        terms_hash=digest(terms),
        expires=s.now + 1000,
    )
    p.renew(
        s.op,
        "operator",
        tenant="a",
        contract="next",
        approval="next",
        starts=s.now - 1,
        expires=s.now + 1000,
        allowance=1,
        command="renew",
    )
    p.lifecycle(
        s.op, "operator", tenant="a", state="active", reason="new term approved", command="activate"
    )
    assert p.overview(s.admin, "alice", tenant="a")["consumed"] == 0
    p.submit_project(s.admin, "alice", tenant="a", project="p", job="new", request=REQUEST)
    assert p.db.execute("SELECT COUNT(*) FROM contract_history").fetchone()[0] == 1


@pytest.mark.parametrize(
    "script",
    [
        "import time; time.sleep(10)",
        "import sys;sys.stdout.write('x'*100000)",
        "raise RuntimeError('failure')",
    ],
)
def test_worker_time_output_and_failure_limits(script):
    with pytest.raises(Unavailable):
        ProcessRuntime(timeout=1, output_bytes=1024, command=[sys.executable, "-c", script]).run({})


def test_worker_clears_secrets_and_obeys_cancellation(monkeypatch):
    monkeypatch.setenv("SENSITIVE_TEST_SECRET", "must-not-leak")
    command = [
        sys.executable,
        "-c",
        "import json,os;print(json.dumps({'leaked':'SENSITIVE_TEST_SECRET' in os.environ}))",
    ]
    assert ProcessRuntime(command=command).run({}) == {"leaked": False}
    with pytest.raises(Unavailable):
        ProcessRuntime(
            command=[sys.executable, "-c", "import time;time.sleep(10)"], cancel_check=lambda: True
        ).run({})


def test_custody_is_idempotent_and_tenant_scoped(tmp_path):
    store = ResultCustody(tmp_path / "results")
    assert store.commit("a", "j", {"result": 1}) == store.commit("a", "j", {"result": 1})
    store.commit("b", "j", {"result": 2})
    with pytest.raises(Unavailable):
        store.commit("a", "j", {"result": 3})
    assert len(list((tmp_path / "results").rglob("*.json"))) == 2


def test_signed_release_gate_requires_fresh_complete_evidence(tmp_path):
    key = ed25519.Ed25519PrivateKey.generate()
    public = base64.b64encode(
        key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    ).decode()
    now = int(time.time())
    (tmp_path / "test.txt").write_text("retained test evidence")
    entry = dict(
        state="PASS",
        reviewer="independent-reviewer",
        executed_at=now,
        artifact="test.txt",
        sha256=hashlib.sha256((tmp_path / "test.txt").read_bytes()).hexdigest(),
    )
    manifest = dict(
        schema="turing.promotion.v1",
        billing_scope="deferred",
        commit="commit-test",
        issued_at=now,
        expires_at=now + 100,
        gates={g: entry for g in GATES},
    )

    def write():
        (tmp_path / "approval.json").write_text(
            json.dumps(
                dict(
                    manifest=manifest,
                    signature=base64.b64encode(key.sign(canonical(manifest).encode())).decode(),
                )
            )
        )

    write()
    assert verify_bundle(tmp_path, public, "commit-test")["commit"] == "commit-test"
    with pytest.raises(Unavailable):
        verify_bundle(tmp_path, public, "different")
    with pytest.raises(Unavailable):
        verify_bundle(tmp_path, public, "commit-test", publication=True)
    with pytest.raises(Unavailable):
        verify_bundle(tmp_path, public, "commit-test", now=now + 101)
    (tmp_path / "test.txt").write_text("tampered")
    with pytest.raises(Unavailable):
        verify_bundle(tmp_path, public, "commit-test")


def test_billing_transport_authorization_capability_and_identity():
    class Response:
        status = 200

        def __init__(self, data):
            self.data = data

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, n):
            return json.dumps(self.data).encode()

    class TransportDouble:
        requests = []

        def open(self, request, timeout):
            self.requests.append(request)
            if request.full_url.endswith("capabilities"):
                return Response(dict(atomic_event_deduplication=True, schemas=["turing.usage.v1"]))
            return Response(dict(event_id="event", receipt_id="receipt"))

    transport = TransportDouble()
    client = HermittenClient("https://billing.test", "test-fixture-only", opener=transport)
    assert (
        client.accept_usage(dict(schema="turing.usage.v1"), idempotency_key="event")["event_id"]
        == "event"
    )
    assert transport.requests[-1].get_header("Idempotency-key") == "event"
    assert transport.requests[-1].get_header("Authorization") == "Bearer test-fixture-only"
    with pytest.raises(Unavailable):
        client.accept_usage(dict(schema="unsupported"), idempotency_key="event")
    with pytest.raises(ValueError):
        HermittenClient("http://billing.test", "key")


def test_portal_headers_assets_and_unavailable_billing(service):
    s = service
    for page in ("ops", "admin", "workspace"):
        result = s.client.get("/" + page)
        assert result.status_code == 200
        assert "frame-ancestors 'none'" in result.headers["content-security-policy"]
    assert s.client.get("/assets/../../main.py").status_code == 404
    assert s.client.get("/assets/portal.js").status_code == 200
    assert s.client.get("/api/customer/a/billing", headers=headers(s)).status_code == 503


class SpendPeer:
    def __init__(self):
        self.calls = []
        self.approved = True

    def capabilities(self):
        return {"spend_authorisation": True}

    def _call(self, method, path, payload, key):
        self.calls.append((method, path, payload, key))
        return dict(
            account_id="billing-a",
            job_key=payload["job_key"],
            request_digest=payload["request_digest"],
            authorization_id="auth-" + key,
            expires_at=int(time.time()) + 600,
            approved=self.approved,
        )


def test_spend_saga_atomic_admission_replay_and_cancellation(service):
    s = service
    p = s.plane
    p.require_spend = True
    with pytest.raises(Denied):
        p.submit_project(s.analyst, "bob", tenant="a", project="p", job="unfunded", request=REQUEST)
    peer = SpendPeer()
    result = p.submit_with_spend(
        s.analyst, "bob", tenant="a", project="p", job="funded", request=REQUEST, billing=peer
    )
    assert result["state"] == "admitted"
    assert p.db.execute("SELECT state FROM spend_intents").fetchone()[0] == "admitted"
    p._before_dispatch("a", "bob", "funded")
    assert (
        p.submit_with_spend(
            s.analyst, "bob", tenant="a", project="p", job="funded", request=REQUEST, billing=peer
        )
        == result
    )
    assert len(peer.calls) == 1
    p.request_cancel(s.analyst, "bob", tenant="a", job="funded")
    assert p.db.execute("SELECT state FROM spend_intents").fetchone()[0] == "release_pending"
    assert any(
        json.loads(r[0])["schema"] == "turing.spend_release.v1"
        for r in p.db.execute("SELECT payload FROM commercial_events")
    )
    assert p.reconcile(s.op, "operator")["pending_commercial_billing"] > 0


def test_spend_success_never_compensated_and_denial_is_not_execution(service):
    s = service
    p = s.plane
    p.require_spend = True
    peer = SpendPeer()
    peer.approved = False
    with pytest.raises(Denied):
        p.submit_with_spend(
            s.analyst, "bob", tenant="a", project="p", job="denied", request=REQUEST, billing=peer
        )
    assert not p.db.execute("SELECT 1 FROM jobs WHERE job='denied'").fetchone()
    peer.approved = True
    p.submit_with_spend(
        s.analyst, "bob", tenant="a", project="p", job="ok", request=REQUEST, billing=peer
    )
    p.execute(s.op, "operator", tenant="a", job="ok", runtime=RuntimeDouble())
    p._spend_release("a", "ok", "unsafe_retry")
    assert (
        p.db.execute("SELECT state FROM spend_intents WHERE job='ok'").fetchone()[0] == "admitted"
    )
    assert json.loads(p.db.execute("SELECT payload FROM usage").fetchone()[0])[
        "spend_authorization"
    ].startswith("auth-")


def test_spend_failed_admission_emits_compensation(service):
    s = service
    peer = SpendPeer()
    s.plane.submit_project(s.analyst, "bob", tenant="a", project="p", job="busy", request=REQUEST)
    with pytest.raises(Conflict):
        s.plane.submit_with_spend(
            s.analyst, "bob", tenant="a", project="p", job="no-room", request=REQUEST, billing=peer
        )
    assert s.plane.db.execute("SELECT state FROM spend_intents").fetchone()[0] == "release_pending"


def test_retirement_retention_purges_live_custody_not_audit(service):
    s = service
    p = s.plane
    custody = ResultCustody(s.tmp / "purge-custody")
    custody.commit("a", "stored", {"sensitive": "result"})
    p.lifecycle(
        s.op, "operator", tenant="a", state="retired", reason="contract ended", command="retire"
    )
    with pytest.raises(Conflict):
        p.purge_data(s.op, "operator", tenant="a", reason="retention", custody=custody)
    p.db.execute("UPDATE retirement SET purge_after=?", (s.now - 1,))
    result = p.purge_data(s.op, "operator", tenant="a", reason="retention", custody=custody)
    assert result["state"] == "live_data_purged"
    assert not list((s.tmp / "purge-custody").rglob("*.json"))
    assert p.db.execute("SELECT COUNT(*) FROM audit").fetchone()[0] > 0


def test_pkce_success_nonce_and_single_use_state(service, monkeypatch):
    import urllib.parse

    s = service
    state, url = s.sessions.start()
    nonce = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["nonce"][0]
    token = s.identity_token("alice", nonce=nonce)

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def read(self, _):
            return json.dumps({"id_token": token}).encode()

    class Opener:
        def open(self, request, timeout):
            fields = urllib.parse.parse_qs(request.data.decode())
            assert fields["code_verifier"] and fields["code"] == ["verified-code"]
            return Response()

    monkeypatch.setattr(
        "hyba_turing_service.sessions.urllib.request.build_opener", lambda *_: Opener()
    )
    handle = s.sessions.finish(state, "verified-code", state)
    assert s.sessions.get(handle)[0].subject == "alice"
    with pytest.raises(Denied):
        s.sessions.finish(state, "verified-code", state)


@pytest.mark.parametrize(
    "amount,currency",
    [
        (1.5, "GBP"),
        ("NaN", "GBP"),
        ("Infinity", "GBP"),
        ("-1", "GBP"),
        ("1E6", "GBP"),
        ("10", "ÄÄÄ"),
        ("10", "gbp"),
    ],
)
def test_spend_ceiling_rejects_inexact_or_invalid_values(amount, currency):
    from hyba_turing_service.billing import set_spend_limit

    with pytest.raises(ValueError):
        set_spend_limit(SpendPeer(), "billing-a", amount=amount, currency=currency, command="one")


def test_billing_statement_and_ceiling_bind_exact_account(monkeypatch):
    from hyba_turing_service.billing import set_spend_limit

    client = HermittenClient("https://billing.test", "test-fixture-only")
    monkeypatch.setattr(client, "_call", lambda *_: {"account_id": "someone-else"})
    with pytest.raises(Unavailable):
        client.account("billing-a")
    monkeypatch.setattr(client, "capabilities", lambda: {"spend_authorisation": True})
    with pytest.raises(Unavailable):
        set_spend_limit(client, "billing-a", amount="100.00", currency="GBP", command="one")
    monkeypatch.setattr(client, "_call", lambda *_: {"account_id": "billing-a"})
    assert (
        set_spend_limit(client, "billing-a", amount="100.00", currency="GBP", command="two")[
            "account_id"
        ]
        == "billing-a"
    )


def test_single_use_spend_token_consumed_once_not_twice(service):
    s = service
    token = s.deps.customer_issuer.issue(
        AUTH.SubscriptionClaims(
            subscription_id="a",
            tenant_id="a",
            issuer=s.deps.customer_issuer.issuer,
            key_id="test",
            capabilities=("turing.jobs.submit",),
            actors=("bob",),
            not_before=s.now - 1,
            expires_at=s.now + 600,
            jti="spend-single",
        )
    )
    assert (
        s.plane.submit_with_spend(
            token,
            "bob",
            tenant="a",
            project="p",
            job="single",
            request=REQUEST,
            billing=SpendPeer(),
        )["state"]
        == "admitted"
    )
    with pytest.raises(Denied):
        s.plane.submit_with_spend(
            token,
            "bob",
            tenant="a",
            project="p",
            job="single",
            request=REQUEST,
            billing=SpendPeer(),
        )
