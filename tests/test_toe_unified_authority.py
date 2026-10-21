"""Enterprise facade enforcement and the real ingest-to-TOE receipt path.

Fixtures establish bounded in-process behaviour, not deployed enterprise readiness.
"""

from concurrent.futures import ThreadPoolExecutor

import pytest

from toe.operator_compilers import compile_operator
from toe.receipts import digest
from toe.unified import UnifiedAnalyticsPlatform
from toe.unified.data_layer import Policy
from toe.unified.platform import AnalysisUnavailable, GateUnavailable
from toe.unified.security import AccessDenied, SecurityModel


def secured(**kwargs):
    platform = UnifiedAnalyticsPlatform(security_enforced=True, **kwargs)
    platform.security.grant("root", "admin")
    platform.security.authenticate("root")
    return platform


@pytest.mark.parametrize(
    "method,args,kwargs",
    [
        ("start", (), {}),
        ("connect", ("missing", {}), {}),
        ("connections", (), {}),
        ("operations_note", (True,), {}),
        ("entities", (), {}),
        ("quality", ("events",), {}),
        ("null_policy", ("events",), {}),
        ("batches", ("events",), {}),
        ("batch_null_rate", ("b1",), {}),
        ("quarantine", ("b1",), {}),
        ("release", ("b1",), {}),
        ("integrate", ("missing", "events"), {}),
        ("ingest_rows", ("s", "events", []), {}),
        ("export_records", (), {}),
        ("import_records", ([],), {}),
        ("govern", ("events", "internal", 30, "ops"), {}),
        ("train", ("m", [], ["x"], "y"), {}),
        ("retrain", ("m", []), {}),
        ("predict", ("m", []), {}),
        ("transfer", ("m", [], ["x"]), {}),
        ("ask", ("count events",), {}),
        ("analyze", ("events",), {}),
        ("analysis_receipts", (), {}),
        ("feedback", ("u", "w"), {}),
        ("dashboard_for", ("u", "d", []), {}),
        ("health", (), {}),
        ("phases", (), {}),
        ("heal", (), {}),
        ("reload", ("missing", {}), {}),
        ("watch", ("m", [{"x": 1}]), {}),
        ("benchmark_processing", (), {}),
        ("optimize", ([], []), {}),
        ("file_patent", ("title",), {}),
        ("case_financial_services", (), {}),
        ("scale", (), {}),
        ("displacement", (), {}),
        ("retire", ("missing",), {}),
        ("economics", (None, None), {}),
        ("scenario", (), {}),
        ("recognize_value", (100, "s"), {}),
        ("industry", ("missing",), {}),
        ("run_application", ("missing",), {}),
    ],
)
def test_unknown_actor_denied_before_work(method, args, kwargs):
    platform = secured()
    platform.security.authenticate("unknown")
    with pytest.raises(AccessDenied):
        getattr(platform, method)(*args, **kwargs)
    assert platform.data.snapshot() == []
    assert platform._analysis_ledger.records == []
    assert platform.operations.probes == 0
    assert platform.started is False


def test_identity_does_not_leak_into_another_thread():
    security = SecurityModel(enforced=True)
    security.grant("root", "admin")
    security.authenticate("root")

    def other_thread():
        assert security.actor == "anonymous"
        with pytest.raises(AccessDenied):
            security.authorize("ingest")
        with security.as_actor("root"):
            security.authorize("ingest")
        assert security.actor == "anonymous"

    with ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(other_thread).result()
    assert security.actor == "root"


def test_scoped_identity_restores_after_failure_and_cannot_escalate():
    security = SecurityModel(enforced=True)
    security.grant("root", "admin")
    security.authenticate("root")
    security.grant("reader", "reader")
    with pytest.raises(AccessDenied):
        with security.as_actor("reader"):
            security.grant("reader", "admin")
    assert security.actor == "root"
    security.authorize("grant")


def test_reader_can_query_but_not_predict_or_mutate_governance():
    platform = secured()
    platform.ingest_rows("s", "events", [{"reading": 1}])
    platform.security.grant("reader", "reader")
    with platform.security.as_actor("reader"):
        assert platform.ask("count events")["rows"][0]["count"] == 1
        assert platform.health()["rows"] == 1
        with pytest.raises(AccessDenied):
            platform.predict("absent", [])
        with pytest.raises(AccessDenied):
            platform.govern("events", "public", 0, "reader")
        with pytest.raises(AccessDenied):
            platform.release("b1")


def test_monitor_uses_explicit_service_identity_and_rechecks_roles():
    platform = secured(monitor_actor="health-service")
    platform.security.grant("health-service", "operator")
    platform.govern("events", "internal", 30, "root", max_null_rate=0)
    platform.ingest_rows("s", "events", [{"reading": None}])
    platform.security.authenticate("unknown")
    platform.monitor.tick_once()
    assert platform.data.quality().quarantined == 1
    assert platform.security.actor == "unknown"
    with platform.security.as_actor("root"):
        platform.security.grant("health-service", "reader")
    audit_count = len(platform.data.audit)
    with pytest.raises(AccessDenied):
        platform.monitor.tick_once()
    assert len(platform.data.audit) == audit_count


def test_anonymous_monitor_cannot_inherit_the_admin_in_another_thread():
    platform = secured()
    with ThreadPoolExecutor(max_workers=1) as executor:
        with pytest.raises(AccessDenied):
            executor.submit(platform.monitor.tick_once).result()


@pytest.mark.parametrize("rate", [float("nan"), float("inf"), -0.1, 1.1, True, "0.2"])
def test_invalid_quality_policy_is_rejected(rate):
    with pytest.raises(ValueError, match="max_null_rate"):
        Policy("events", "internal", 30, "root", rate)


def test_availability_without_probes_is_unknown_not_a_pass():
    platform = UnifiedAnalyticsPlatform()
    assert platform.health()["availability"] is None
    with pytest.raises(GateUnavailable):
        platform.require_gate("availability")
    platform.operations.note_probe(False)
    assert platform.require_gate("availability").passed is False
    platform.operations = type(platform.operations)()
    platform.operations.note_probe(True)
    assert platform.require_gate("availability").passed is True
    assert platform.require_gate("availability").evidence_kind == "probe_ratio"
    platform.case_financial_services()
    assert platform.require_gate("roi_400").evidence_kind == "modeled"


def test_retirement_removes_a_live_binding_and_reconnect_clears_retired_state():
    platform = secured()
    credentials = {"events": [{"entity": "Event", "reading": 1}]}
    platform.connect("confluent.cloud", credentials)
    platform.retire("confluent.cloud")
    assert "confluent.cloud" not in platform.connections()
    with pytest.raises(KeyError):
        platform.integrate("confluent.cloud", "Event")
    with pytest.raises(KeyError):
        platform.retire("absent")
    platform.connect("confluent.cloud", credentials)
    assert "confluent.cloud" not in platform._retired


def test_ingestion_to_real_toe_tomography_and_bound_receipt():
    platform = secured()
    rows = [{"reading": 1, "time": 0}, {"reading": 2, "time": 1}]
    ingest = platform.ingest_rows("sensor", "events", rows)["receipt"]
    platform.govern("events", "internal", 30, "root", max_null_rate=0)
    platform.heal()
    answer = platform.analyze("events")
    assert answer["result"]["available"] is True
    assert answer["result"]["diagnostics"]["norm"] == pytest.approx(1.0)
    assert answer["truth_class"] == "descriptive_state_tomography"
    receipt = answer["receipt"]
    snapshot = platform.export_records()
    inputs = {"events": [row["payload"] for row in snapshot]}
    assert receipt["input_sha256"] == digest(inputs)
    assert receipt["config"]["operator_digest"] == compile_operator(inputs).input_digest
    assert {row["operator_digest"] for row in receipt["config"]["lineage"]} == {
        ingest.operator_digest
    }
    assert receipt["config"]["actor"] == "root"
    assert receipt["output_sha256"] == digest(answer["result"])
    assert receipt["receipt_sha256"] == digest(
        {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    )
    answer["result"]["available"] = False
    assert platform.analysis_receipts()[0]["output"]["available"] is True
    assert platform._analysis_ledger.verify()["ok"] is True
    replayed = platform.analyze("events")["receipt"]
    assert replayed["output_sha256"] == receipt["output_sha256"]
    assert replayed["prev_sha256"] == receipt["receipt_sha256"]
    platform.quarantine(ingest.batch_id)
    with pytest.raises(AnalysisUnavailable):
        platform.analyze("events")
    assert len(platform.analysis_receipts()) == 2


def test_failed_tomography_issues_no_success_receipt(monkeypatch):
    from types import SimpleNamespace
    from toe.bridge import TOEBridge

    platform = secured()
    platform.ingest_rows("s", "events", [{"reading": 1}])
    monkeypatch.setattr(
        TOEBridge,
        "state_tomography",
        lambda *args: SimpleNamespace(as_dict=lambda: {"available": False}),
    )
    with pytest.raises(AnalysisUnavailable):
        platform.analyze("events")
    assert platform.analysis_receipts() == []
