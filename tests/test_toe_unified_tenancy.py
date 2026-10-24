"""Real per-tenant facade state and live authorization, not a network audit."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
import threading

import pytest

from toe.receipts import digest
from toe.unified import TenantGateway, UnifiedAnalyticsPlatform
from toe.unified.security import AccessDenied, SecurityModel
from toe.unified.tenancy import TENANT_OPERATIONS


@pytest.fixture
def gateway():
    gateway = TenantGateway()
    for tenant in ("alpha", "beta"):
        gateway.provision(tenant)
        gateway.grant(tenant, "owner", "admin")
    return gateway


def session(gateway, tenant="alpha", actor="owner"):
    return gateway.session(tenant_id=tenant, verified_actor=actor)


def rows(flipped=False):
    return [{"x": i, "label": int(i > 5) ^ int(flipped)} for i in range(12)]


def test_same_entity_source_and_batch_ids_do_not_mix_tenant_records(gateway):
    alpha, beta = session(gateway), session(gateway, "beta")
    for client, value in ((alpha, 11), (beta, 99)):
        result = client.call("ingest_rows", "same-source", "events", [{"value": value}])
        assert result.tenant_id == client.tenant_id
        assert result.value["receipt"].batch_id == "b1"
    assert alpha.call("export_records").value[0]["payload"] == {"value": 11}
    assert beta.call("export_records").value[0]["payload"] == {"value": 99}
    assert (
        alpha.call("ask", "count events").value
        == beta.call("ask", "count events").value
    )
    alpha.call("quarantine", "b1")
    assert alpha.call("export_records").value[0]["quarantined"] is True
    assert beta.call("export_records").value[0]["quarantined"] is False


def test_policy_and_governance_mutation_is_tenant_local(gateway):
    alpha, beta = session(gateway), session(gateway, "beta")
    alpha.call("govern", "events", "restricted", 7, "alpha-owner", max_null_rate=0.01)
    assert alpha.call("null_policy", "events").value == 0.01
    assert beta.call("null_policy", "events").value == 0.2
    alpha.call("file_patent", "alpha-only-title")
    assert gateway._tenants["beta"].platform.patents.titles() == ()


def test_same_model_name_uses_separate_real_exact_linear_models(gateway):
    alpha, beta = session(gateway), session(gateway, "beta")
    alpha.call("train", "same-model", rows(), ["x"], "label")
    beta.call("train", "same-model", rows(True), ["x"], "label")
    assert alpha.call("predict", "same-model", [{"x": 0}]).value == [0]
    assert beta.call("predict", "same-model", [{"x": 0}]).value == [1]
    alpha.call("train", "alpha-only", rows(), ["x"], "label")
    with pytest.raises(KeyError):
        beta.call("predict", "alpha-only", [{"x": 0}])


def test_model_result_mutation_cannot_edit_the_live_registry(gateway):
    client = session(gateway)
    result = client.call("train", "model", rows(), ["x"], "label")
    live_model = gateway._tenants["alpha"].platform.models.get("model").model
    assert result.value.record.model is not live_model
    original_weights = live_model.weights_exact_
    result.value.record.model.weights_exact_ = ()
    assert live_model.weights_exact_ == original_weights
    result.value.record.version = 9000
    result.value.record.features = ("not-x",)
    result.value.record.model = None
    actual = gateway._tenants["alpha"].platform.models.get("model")
    assert actual.version == 1 and actual.features == ("x",)
    assert client.call("predict", "model", [{"x": 0}]).value == [0]


def test_export_payloads_and_result_scope_are_detached(gateway):
    client = session(gateway)
    client.call("ingest_rows", "s", "events", [{"nested": {"x": [1, 2]}}])
    result = client.call("export_records")
    result.value[0]["payload"]["nested"]["x"].append(3)
    assert client.call("export_records").value[0]["payload"]["nested"]["x"] == [1, 2]
    with pytest.raises(FrozenInstanceError):
        result.tenant_id = "beta"


def test_actual_tomography_receipts_are_tenant_bound_and_separate(gateway):
    alpha, beta = session(gateway), session(gateway, "beta")
    # Identical content is deliberate: tenant binding must not rely on different inputs.
    for client in (alpha, beta):
        client.call("ingest_rows", "s", "events", [{"x": 1.0}, {"x": 2.0}])
        result = client.call("analyze", "events")
        receipt = result.value["receipt"]
        assert receipt["config"]["tenant_id"] == client.tenant_id
        assert receipt["config"]["actor"] == "owner"
        assert receipt["receipt_sha256"] == digest(
            {k: v for k, v in receipt.items() if k != "receipt_sha256"}
        )
    a = alpha.call("analysis_receipts").value
    b = beta.call("analysis_receipts").value
    assert len(a) == len(b) == 1
    assert a[0]["receipt_sha256"] != b[0]["receipt_sha256"]
    a[0]["config"]["tenant_id"] = "beta"
    assert alpha.call("analysis_receipts").value[0]["config"]["tenant_id"] == "alpha"


def test_unknown_and_ungranted_tenants_deny_without_work(gateway):
    gateway.grant("alpha", "reader-a", "reader")
    for tenant in ("beta", "missing"):
        with pytest.raises(AccessDenied, match="tenant access denied"):
            session(gateway, tenant, "reader-a")
    assert session(gateway, "beta").call("health").value["rows"] == 0


def test_shared_actor_roles_are_independent_per_tenant(gateway):
    gateway.grant("alpha", "shared", "reader")
    gateway.grant("beta", "shared", "operator")
    with pytest.raises(AccessDenied):
        session(gateway, "alpha", "shared").call(
            "ingest_rows", "s", "events", [{"x": 1}]
        )
    session(gateway, "beta", "shared").call("ingest_rows", "s", "events", [{"x": 1}])
    assert session(gateway).call("health").value["rows"] == 0


@pytest.mark.parametrize(
    "operation",
    ["ingest_rows", "export_records", "predict", "analysis_receipts", "health"],
)
def test_existing_session_is_denied_after_revocation(gateway, operation):
    gateway.grant("alpha", "revoked", "operator")
    client = session(gateway, actor="revoked")
    gateway.revoke("alpha", "revoked")
    with pytest.raises(AccessDenied, match="tenant access denied"):
        client.call(operation)


def test_existing_session_observes_role_downgrade_and_own_tenant_only(gateway):
    gateway.grant("alpha", "shared", "operator")
    gateway.grant("beta", "shared", "operator")
    a, b = session(gateway, actor="shared"), session(gateway, "beta", "shared")
    gateway.grant("alpha", "shared", "reader")
    with pytest.raises(AccessDenied):
        a.call("ingest_rows", "s", "events", [{"x": 1}])
    b.call("ingest_rows", "s", "events", [{"x": 1}])


@pytest.mark.parametrize(
    "operation",
    [
        "connect",
        "connections",
        "reload",
        "security",
        "data",
        "models",
        "__dict__",
        "_monitor_tick",
        "session",
        "grant",
        "revoke",
        "configure_connector",
    ],
)
def test_tenant_calls_cannot_reach_host_controls_or_live_runtime(gateway, operation):
    with pytest.raises(AccessDenied, match="not a tenant API"):
        session(gateway).call(operation)


def test_connector_credentials_and_bindings_stay_in_host_and_tenant_scope(gateway):
    configured = gateway.configure_connector(
        "alpha",
        "confluent.cloud",
        {"events": [{"entity": "Event", "x": 1}], "token": "fixture-not-a-secret"},
    )
    assert set(configured) == {"tenant_id", "connector_id", "protocol", "entities"}
    a, b = session(gateway), session(gateway, "beta")
    assert a.call("health").value["connectors_bound"] == 1
    assert b.call("health").value["connectors_bound"] == 0
    with pytest.raises(KeyError):
        b.call("integrate", "confluent.cloud", "Event")
    a.call("integrate", "confluent.cloud", "Event")
    assert a.call("health").value["rows"] == 1
    assert b.call("health").value["rows"] == 0


def test_atomic_import_failure_does_not_touch_other_tenants(gateway):
    a, b = session(gateway), session(gateway, "beta")
    b.call("ingest_rows", "s", "events", [{"x": 99}])
    before = b.call("export_records").value
    with pytest.raises((TypeError, ValueError)):
        a.call(
            "import_records",
            [
                {"source": "s", "entity": "good", "payload": {"x": 1}},
                {"source": "s", "entity": "bad", "payload": "bad"},
            ],
        )
    assert a.call("export_records").value == []
    assert b.call("export_records").value == before


def test_parallel_sessions_keep_same_named_actors_and_data_in_their_tenant(gateway):
    def write(tenant):
        client = session(gateway, tenant)
        for i in range(10):
            client.call("ingest_rows", "s", "events", [{"x": i, "tenant": tenant}])
        return client.call("export_records").value

    with ThreadPoolExecutor(max_workers=2) as pool:
        alpha, beta = list(pool.map(write, ("alpha", "beta")))
    assert len(alpha) == len(beta) == 10
    assert {r["payload"]["tenant"] for r in alpha} == {"alpha"}
    assert {r["payload"]["tenant"] for r in beta} == {"beta"}
    assert gateway._tenants["alpha"].platform.security.actor == "anonymous"
    assert gateway._tenants["beta"].platform.security.actor == "anonymous"


def test_revoke_serializes_after_inflight_call_and_blocks_next_call(
    gateway, monkeypatch
):
    gateway.grant("alpha", "worker", "operator")
    client = session(gateway, actor="worker")
    entered, finish, revoking = threading.Event(), threading.Event(), threading.Event()
    platform = gateway._tenants["alpha"].platform
    original = platform.ingest_rows

    def paused(*args, **kwargs):
        entered.set()
        assert finish.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(platform, "ingest_rows", paused)

    def revoke():
        revoking.set()
        gateway.revoke("alpha", "worker")

    with ThreadPoolExecutor(max_workers=2) as pool:
        call = pool.submit(client.call, "ingest_rows", "s", "events", [{"x": 1}])
        try:
            assert entered.wait(5)
            revocation = pool.submit(revoke)
            assert revoking.wait(5)
            assert not revocation.done()
        finally:
            finish.set()
        call.result(timeout=5)
        revocation.result(timeout=5)
    with pytest.raises(AccessDenied):
        client.call("export_records")


def test_a_blocked_tenant_does_not_hold_another_tenants_lock(gateway, monkeypatch):
    entered, finish = threading.Event(), threading.Event()
    platform = gateway._tenants["alpha"].platform
    original = platform.health

    def paused():
        entered.set()
        assert finish.wait(5)
        return original()

    monkeypatch.setattr(platform, "health", paused)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(session(gateway).call, "health")
        try:
            assert entered.wait(5)
            b = pool.submit(session(gateway, "beta").call, "health")
            assert b.result(timeout=2).value["rows"] == 0
        finally:
            finish.set()
        a.result(timeout=5)


def test_actor_context_restored_after_authorized_method_failure(gateway):
    platform = gateway._tenants["alpha"].platform
    with pytest.raises(KeyError):
        session(gateway).call("predict", "missing-model", [])
    assert platform.security.actor == "anonymous"


def test_only_grant_authority_can_revoke_roles():
    security = SecurityModel(enforced=True)
    security.grant("root", "admin")
    with security.as_actor("root"):
        security.grant("reader", "reader")
    with security.as_actor("reader"), pytest.raises(AccessDenied):
        security.revoke("root")
    with security.as_actor("root"):
        security.revoke("reader")
    with security.as_actor("reader"), pytest.raises(AccessDenied):
        security.authorize("export")


@pytest.mark.parametrize(
    "bad", ["", " alpha", "alpha ", "__unified_tenant_host__", None, 7, "x" * 129]
)
def test_invalid_or_reserved_identifiers_are_rejected(bad):
    with pytest.raises(ValueError):
        TenantGateway().provision(bad)


def test_duplicate_provision_cannot_erase_existing_state(gateway):
    client = session(gateway)
    client.call("ingest_rows", "s", "events", [{"x": 1}])
    with pytest.raises(ValueError, match="already provisioned"):
        gateway.provision("alpha")
    assert len(client.call("export_records").value) == 1


def test_allowlist_only_names_existing_public_facade_methods():
    assert all(
        not name.startswith("_")
        and callable(getattr(UnifiedAnalyticsPlatform, name, None))
        for name in TENANT_OPERATIONS
    )


def test_role_denial_precedes_payload_copy_or_processing(gateway):
    class PayloadNotToBeRead:
        def __deepcopy__(self, memo):
            raise AssertionError("denied request processed its payload")

        def __iter__(self):
            raise AssertionError("denied request read its payload")

    gateway.grant("alpha", "reader", "reader")
    with pytest.raises(AccessDenied):
        session(gateway, actor="reader").call(
            "ingest_rows", "s", "events", PayloadNotToBeRead()
        )
