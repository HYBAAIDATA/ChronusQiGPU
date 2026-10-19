"""Real AL HARAS signatures + real SQLite; runtime/billing doubles are labelled.

Load the owning entitlements module without AL HARAS's unrelated package-level
imports. This is conformance to its real signature verifier, not an auth stand-in.
"""

import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from hyba_turing_service import ControlPlane, Conflict, Denied, Unavailable

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "service_test_entitlements", ROOT / "al_haras/entitlements.py"
)
AUTH = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AUTH
SPEC.loader.exec_module(AUTH)

NOW = 1000
OPS = ("turing.ops.manage", "turing.ops.execute", "turing.ops.billing")
CUSTOMER = ("turing.jobs.submit", "turing.customer.read")
REQUEST = {"qasm": "OPENQASM 2.0; qreg q[2]; h q[0]; cx q[0],q[1];", "shots": 8, "seed": 3}


def token(authority, tenant, actor, capabilities, *, expiry=2000, payload=100000):
    return authority.issue(
        AUTH.SubscriptionClaims(
            subscription_id=tenant,
            tenant_id=tenant,
            issuer=authority.issuer,
            key_id="test",
            capabilities=capabilities,
            actors=(actor,),
            not_before=0,
            expires_at=expiry,
            max_payload_bytes=payload,
        )
    )


class RuntimeDouble:
    """Transport contract only: NOT real mathematical execution evidence."""

    def __init__(self, verdict="PASS"):
        self.calls = 0
        self.verdict = verdict

    def run(self, request):
        self.calls += 1
        return dict(
            schema="turing.vqc.pipeline_report.v1",
            verdict=self.verdict,
            program_digest="test-program-digest",
            certificate={"test": True},
            witness={"test": True},
            stages=[
                dict(stage="execution", state="PASS"),
                dict(stage="verification", state="PASS"),
            ],
        )


class BillingDouble:
    """An idempotent receiver test double, NOT the Hermitten service."""

    def __init__(self):
        self.events = {}

    def accept_usage(self, event, *, idempotency_key):
        assert idempotency_key == event["event_id"]
        self.events.setdefault(idempotency_key, event)
        return dict(event_id=idempotency_key, receipt_id="test-import-ack")


@pytest.fixture
def env(tmp_path):
    customer = AUTH.SubscriptionAuthority({"test": b"c" * 32}, "customer-test")
    operator = AUTH.SubscriptionAuthority({"test": b"o" * 32}, "operator-test")
    path = str(tmp_path / "service.db")
    clock = [NOW]

    def open_plane():
        return ControlPlane(
            path, customer_authority=customer, operator_authority=operator, clock=lambda: clock[0]
        )

    plane = open_plane()
    ops = token(operator, "__service_ops__", "operator", OPS)
    a = token(customer, "a", "alice", CUSTOMER)
    b = token(customer, "b", "bob", CUSTOMER)

    def onboard(tenant="a", slots=2, allowance=10):
        plane.approve_customer(
            ops,
            "operator",
            tenant=tenant,
            billing_account=f"bill-{tenant}",
            contract=f"contract-{tenant}",
            approval="approved-record-42",
            starts=0,
            expires=1500,
            contracted=slots,
            allowance=allowance,
            command=f"approve-{tenant}",
        )
        plane.provision(ops, "operator", tenant=tenant, slots=slots, command=f"provision-{tenant}")

    yield plane, ops, a, b, onboard, open_plane, customer, clock
    plane.close()


def test_lifecycle_capacity_audit_and_idempotency(env):
    p, ops, a, _, onboard, _, _, _ = env
    onboard()
    assert p.overview(a, "alice", tenant="a")["available"] == 2
    kwargs = dict(tenant="a", slots=1, command="resize-a")
    assert p.provision(ops, "operator", **kwargs) == p.provision(ops, "operator", **kwargs)
    with pytest.raises(Conflict):
        p.provision(ops, "operator", tenant="a", slots=2, command="resize-a")
    for state in ("suspended", "active", "retired"):
        p.lifecycle(ops, "operator", tenant="a", state=state, reason="test", command=state)
    with pytest.raises(Denied):
        p.provision(ops, "operator", tenant="a", slots=1, command="resurrect")
    assert p.reconcile(ops, "operator")["issues"] == []
    assert len(p.audit(a, "alice", tenant="a")) == 6


@pytest.mark.parametrize("bad", ["", "not-a-token", "aaa.bbb"])
def test_missing_bad_tokens_fail_closed(env, bad):
    p, _, _, _, onboard, *_ = env
    onboard()
    with pytest.raises(Denied):
        p.overview(bad, "alice", tenant="a")


def test_tenant_actor_and_operator_separation(env):
    p, ops, a, b, onboard, _, customer, _ = env
    onboard("a")
    onboard("b")
    p.submit(a, "alice", tenant="a", job="j", request=REQUEST)
    for call in [
        lambda: p.overview(a, "alice", tenant="b"),
        lambda: p.job(b, "bob", tenant="a", job="j"),
        lambda: p.overview(a, "bob", tenant="a"),
        lambda: p.provision(a, "alice", tenant="a", slots=1, command="x"),
    ]:
        with pytest.raises(Denied):
            call()
    # Even a customer-issued ops capability cannot cross the operator key/issuer boundary.
    forged_role = token(customer, "__service_ops__", "alice", OPS)
    with pytest.raises(Denied):
        p.provision(forged_role, "alice", tenant="a", slots=1, command="y")
    assert {x["tenant"] for x in p.audit(a, "alice", tenant="a")} == {"a"}
    assert p.usage(b, "bob", tenant="b") == []


def test_token_expiry_revocation_and_limits(env):
    p, _, a, _, onboard, _, customer, clock = env
    onboard()
    revoked = token(customer, "a", "alice", CUSTOMER, expiry=1000)
    with pytest.raises(Denied):
        p.overview(revoked, "alice", tenant="a")
    small = token(customer, "a", "alice", CUSTOMER, payload=10)
    with pytest.raises(Denied):
        p.submit(small, "alice", tenant="a", job="limited", request=REQUEST)
    # Contract expiry, even while the independently issued token remains valid.
    clock[0] = 1500
    with pytest.raises(Denied):
        p.submit(a, "alice", tenant="a", job="expired", request=REQUEST)


def test_signature_tampering_is_rejected(env):
    p, _, a, _, onboard, *_ = env
    onboard()
    body, signature = a.split(".")
    modified = AUTH._b64encode(
        json.dumps({**json.loads(AUTH._b64decode(body)), "tenant_id": "b"}).encode()
    )
    with pytest.raises(Denied):
        p.overview(f"{modified}.{signature}", "alice", tenant="b")


@pytest.mark.parametrize("slots", [0, -1, True, 1.0, "2", 2**40])
def test_bad_capacity_rejected(env, slots):
    p, ops, _, _, onboard, *_ = env
    onboard()
    with pytest.raises(ValueError):
        p.provision(ops, "operator", tenant="a", slots=slots, command="bad")


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"qasm": ""},
        {"qasm": "x", "custody_dir": "/tmp"},
        {"qasm": "x", "shots": True},
        {"qasm": "x", "shots": 0},
        {"qasm": "x", "seed": -1},
        {"qasm": "x" * 65537},
    ],
)
def test_request_allowlist_and_bounds(env, payload):
    p, _, a, _, onboard, *_ = env
    onboard()
    with pytest.raises(ValueError):
        p.submit(a, "alice", tenant="a", job="invalid", request=payload)


def test_capacity_allowance_retry_cancel_and_resize(env):
    p, ops, a, _, onboard, *_ = env
    onboard(slots=1, allowance=1)
    assert p.submit(a, "alice", tenant="a", job="j", request=REQUEST)["state"] == "admitted"
    assert p.submit(a, "alice", tenant="a", job="j", request=REQUEST)["state"] == "admitted"
    with pytest.raises(Conflict):
        p.submit(a, "alice", tenant="a", job="j", request={"qasm": "different"})
    with pytest.raises(Conflict):
        p.submit(a, "alice", tenant="a", job="j2", request=REQUEST)
    p.cancel(a, "alice", tenant="a", job="j")
    p.cancel(a, "alice", tenant="a", job="j")
    p.submit(a, "alice", tenant="a", job="j2", request=REQUEST)
    runtime = RuntimeDouble()
    p.execute(ops, "operator", tenant="a", job="j2", runtime=runtime)
    p.execute(ops, "operator", tenant="a", job="j2", runtime=runtime)
    assert runtime.calls == 1
    with pytest.raises(Conflict):
        p.submit(a, "alice", tenant="a", job="j3", request=REQUEST)
    assert len(p.usage(a, "alice", tenant="a")) == 1


@pytest.mark.parametrize("verdict", ["FAIL", "GATED", "REFUSED", "SKIPPED"])
def test_unsuccessful_results_never_become_billable(env, verdict):
    p, ops, a, _, onboard, *_ = env
    onboard()
    p.submit(a, "alice", tenant="a", job="j", request=REQUEST)
    p.execute(ops, "operator", tenant="a", job="j", runtime=RuntimeDouble(verdict))
    assert p.usage(a, "alice", tenant="a") == []
    assert p.job(a, "alice", tenant="a", job="j")["state"] == "failed"


@pytest.mark.parametrize(
    "missing", ["schema", "program_digest", "certificate", "witness", "stages"]
)
def test_incomplete_evidence_never_becomes_billable(env, missing):
    p, ops, a, _, onboard, *_ = env
    onboard()

    class Incomplete(RuntimeDouble):
        def run(self, request):
            report = super().run(request)
            report.pop(missing)
            return report

    p.submit(a, "alice", tenant="a", job="j", request=REQUEST)
    p.execute(ops, "operator", tenant="a", job="j", runtime=Incomplete())
    assert p.usage(a, "alice", tenant="a") == []


def test_suspend_blocks_dispatch_but_preserves_audit_and_usage_access(env):
    p, ops, a, _, onboard, *_ = env
    onboard()
    p.submit(a, "alice", tenant="a", job="j", request=REQUEST)
    p.lifecycle(ops, "operator", tenant="a", state="suspended", reason="hold", command="s")
    runtime = RuntimeDouble()
    with pytest.raises(Denied):
        p.execute(ops, "operator", tenant="a", job="j", runtime=runtime)
    assert runtime.calls == 0
    assert p.overview(a, "alice", tenant="a")["state"] == "suspended"
    p.cancel(a, "alice", tenant="a", job="j")


def test_unknown_execution_survives_restart_and_never_auto_retries(env):
    p, ops, a, _, onboard, open_plane, *_ = env
    onboard(slots=1)
    p.submit(a, "alice", tenant="a", job="j", request=REQUEST)

    class Broken:
        def run(self, request):
            raise OSError("lost result")

    with pytest.raises(Unavailable):
        p.execute(ops, "operator", tenant="a", job="j", runtime=Broken())
    p2 = open_plane()
    try:
        assert p2.reconcile(ops, "operator")["issues"] == [
            dict(tenant="a", job="j", state="unknown")
        ]
        with pytest.raises(Conflict):
            p2.execute(ops, "operator", tenant="a", job="j", runtime=RuntimeDouble())
        with pytest.raises(Conflict):
            p2.lifecycle(ops, "operator", tenant="a", state="retired", reason="x", command="ret")
        p2.resolve_unknown(
            ops, "operator", tenant="a", job="j", reason="worker fenced, no evidence recovered"
        )
        assert p2.overview(a, "alice", tenant="a")["available"] == 1
        assert p2.usage(a, "alice", tenant="a") == []
    finally:
        p2.close()


def test_operator_resolution_fences_late_success(env):
    p, ops, a, _, onboard, open_plane, *_ = env
    onboard()
    p.submit(a, "alice", tenant="a", job="j", request=REQUEST)

    class Late(RuntimeDouble):
        def run(self, request):
            p2 = open_plane()
            try:
                p2.resolve_unknown(
                    ops, "operator", tenant="a", job="j", reason="worker fencing decision"
                )
            finally:
                p2.close()
            return super().run(request)

    with pytest.raises(Conflict):
        p.execute(ops, "operator", tenant="a", job="j", runtime=Late())
    assert p.usage(a, "alice", tenant="a") == []


def test_atomic_capacity_under_parallel_connections(env):
    p, _, a, _, onboard, open_plane, *_ = env
    onboard(slots=1)

    def submit(index):
        plane = open_plane()
        try:
            plane.submit(a, "alice", tenant="a", job=str(index), request=REQUEST)
            return True
        except Conflict:
            return False
        finally:
            plane.close()

    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(submit, range(8)))
    assert sum(outcomes) == 1
    assert p.overview(a, "alice", tenant="a")["in_flight"] == 1


def test_billing_retry_ack_and_immutability(env):
    p, ops, a, _, onboard, open_plane, *_ = env
    onboard()
    p.submit(a, "alice", tenant="a", job="j", request=REQUEST)
    p.execute(ops, "operator", tenant="a", job="j", runtime=RuntimeDouble())
    with pytest.raises(Unavailable):
        p.deliver_usage(ops, "operator", sink=None)

    class LostAck(BillingDouble):
        def accept_usage(self, event, *, idempotency_key):
            super().accept_usage(event, idempotency_key=idempotency_key)
            raise OSError("network loss after receiver commit")

    sink = LostAck()
    with pytest.raises(OSError):
        p.deliver_usage(ops, "operator", sink=sink)
    assert p.reconcile(ops, "operator")["pending_billing"] == 1
    p2 = open_plane()
    try:
        recovered_sink = BillingDouble()
        recovered_sink.events = sink.events
        assert p2.deliver_usage(ops, "operator", sink=recovered_sink) == 1
        assert p2.deliver_usage(ops, "operator", sink=recovered_sink) == 0
        assert len(recovered_sink.events) == 1
        assert p2.reconcile(ops, "operator") == dict(issues=[], pending_billing=0)
        with pytest.raises(sqlite3.IntegrityError):
            p2.db.execute("UPDATE usage SET payload='{}'")
        with pytest.raises(sqlite3.IntegrityError):
            p2.db.execute("DELETE FROM audit")
    finally:
        p2.close()


def test_wrong_event_billing_ack_remains_pending(env):
    p, ops, a, _, onboard, *_ = env
    onboard()
    p.submit(a, "alice", tenant="a", job="j", request=REQUEST)
    p.execute(ops, "operator", tenant="a", job="j", runtime=RuntimeDouble())

    class BadAck:
        def accept_usage(self, event, *, idempotency_key):
            return dict(event_id="different", receipt_id="ack")

    with pytest.raises(Unavailable):
        p.deliver_usage(ops, "operator", sink=BadAck())
    assert p.reconcile(ops, "operator")["pending_billing"] == 1


def test_atomic_completion_rolls_back_usage_and_state_on_audit_failure(env, monkeypatch):
    p, ops, a, _, onboard, *_ = env
    onboard()
    p.submit(a, "alice", tenant="a", job="j", request=REQUEST)
    original = p._audit

    def broken(tenant, actor, action, detail):
        if action == "complete":
            raise OSError("audit disk failure")
        return original(tenant, actor, action, detail)

    monkeypatch.setattr(p, "_audit", broken)
    with pytest.raises(OSError):
        p.execute(ops, "operator", tenant="a", job="j", runtime=RuntimeDouble())
    assert p.usage(a, "alice", tenant="a") == []
    assert p.job(a, "alice", tenant="a", job="j")["state"] == "running"
    assert p.reconcile(ops, "operator")["pending_billing"] == 0


def test_missing_runtime_leaves_job_undispatched(env):
    p, ops, a, _, onboard, *_ = env
    onboard()
    p.submit(a, "alice", tenant="a", job="j", request=REQUEST)
    with pytest.raises(Unavailable):
        p.execute(ops, "operator", tenant="a", job="j", runtime=None)
    assert p.job(a, "alice", tenant="a", job="j")["state"] == "admitted"


def test_same_job_identifier_is_scoped_by_tenant(env):
    p, ops, a, b, onboard, *_ = env
    onboard("a")
    onboard("b")
    p.submit(a, "alice", tenant="a", job="j", request=REQUEST)
    p.submit(b, "bob", tenant="b", job="j", request=REQUEST)
    p.execute(ops, "operator", tenant="a", job="j", runtime=RuntimeDouble())
    assert p.job(b, "bob", tenant="b", job="j")["state"] == "admitted"
    assert p.usage(b, "bob", tenant="b") == []


def test_resize_cannot_drop_below_reserved_inflight_jobs(env):
    p, ops, a, _, onboard, *_ = env
    onboard()
    for job in ("1", "2"):
        p.submit(a, "alice", tenant="a", job=job, request=REQUEST)
    with pytest.raises(Conflict):
        p.provision(ops, "operator", tenant="a", slots=1, command="shrink")
    with pytest.raises(Conflict):
        p.provision(ops, "operator", tenant="a", slots=3, command="expand")


def test_unsupported_database_schema_fails_closed(env):
    p, _, _, _, _, open_plane, *_ = env
    p.db.execute("PRAGMA user_version=99")
    with pytest.raises(Unavailable):
        open_plane()


@pytest.mark.parametrize(
    "patch",
    [
        dict(stages=None),
        dict(stages={}),
        dict(certificate=True),
        dict(witness="not-an-envelope"),
        dict(program_digest=12),
        dict(
            stages=[
                dict(stage="execution", state="PASS"),
                dict(stage="execution", state="PASS"),
                dict(stage="verification", state="PASS"),
            ]
        ),
    ],
)
def test_malformed_transport_reports_never_become_billable(env, patch):
    p, ops, a, _, onboard, *_ = env
    onboard()

    class Malformed(RuntimeDouble):
        def run(self, request):
            return {**super().run(request), **patch}

    p.submit(a, "alice", tenant="a", job="j", request=REQUEST)
    p.execute(ops, "operator", tenant="a", job="j", runtime=Malformed())
    assert p.usage(a, "alice", tenant="a") == []
    assert p.job(a, "alice", tenant="a", job="j")["state"] == "failed"


def test_single_use_token_is_not_silently_treated_as_reusable(env):
    p, _, _, _, onboard, _, customer, _ = env
    onboard()
    single_use = customer.issue(
        AUTH.SubscriptionClaims(
            subscription_id="a",
            tenant_id="a",
            issuer=customer.issuer,
            key_id="test",
            capabilities=CUSTOMER,
            actors=("alice",),
            not_before=0,
            expires_at=2000,
            jti="one-use",
        )
    )
    assert p.overview(single_use, "alice", tenant="a")["tenant"] == "a"
    restarted = env[5]()
    try:
        with pytest.raises(Denied):
            restarted.overview(single_use, "alice", tenant="a")
    finally:
        restarted.close()
