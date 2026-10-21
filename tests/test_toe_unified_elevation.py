"""Mechanisms that were missing from the first register."""

import time

import pytest

from toe.unified import UnifiedAnalyticsPlatform
from toe.unified.catalog import CATALOG
from toe.unified.productivity import REFERENCE
from toe.unified.risks import DEFAULTS
from toe.unified.security import AccessDenied


def _gate(platform, name):
    return next(gate for gate in platform.phases() if gate.name == name)


def test_indexed_reads_are_two_orders_faster():
    platform = UnifiedAnalyticsPlatform()
    measured = platform.benchmark_processing(entities=100, per_entity=20)
    assert measured["ratio"] >= 100
    assert measured["reduction"] >= 0.90
    assert _gate(platform, "processing_reduction").passed is True


def test_storage_round_trip_compresses():
    platform = UnifiedAnalyticsPlatform()
    payload = {"note": "meter " * 500, "id": 1}
    platform.ingest_rows("plant", "sensor", [payload])
    stored = platform.export_records()[0]
    assert platform.data.storage_ratio() >= 2
    assert platform.data.restore_payload(stored["digest"]) == payload


def test_consciousness_reorders_from_actions():
    platform = UnifiedAnalyticsPlatform()
    platform.consciousness.observe("ada", "risk", depth=3)
    assert platform.consciousness.rank(["energy", "risk"], "ada") == ["risk", "energy"]


def test_corrections_raise_accuracy():
    platform = UnifiedAnalyticsPlatform()
    rows = [(-0.5, 1), (-0.2, 1), (1.0, 1), (-2.0, 0)]
    before = platform.consciousness.accuracy("ada", rows, learned=False)
    for score, label in rows:
        platform.consciousness.correct("ada", score, label)
    after = platform.consciousness.accuracy("ada", rows, learned=True)
    assert after > before
    assert after == 1.0


def test_monitor_runs_without_a_manual_heal():
    platform = UnifiedAnalyticsPlatform()
    platform.monitor.start()
    try:
        deadline = time.time() + 2
        while platform.monitor.ticks < 1 and time.time() < deadline:
            time.sleep(0.01)
    finally:
        platform.monitor.stop()
    assert platform.monitor.ticks >= 1


def test_drift_retrains_without_calling_retrain():
    platform = UnifiedAnalyticsPlatform()
    rows = [{"amount": float(i), "defaulted": int(i > 5)} for i in range(12)]
    platform.train("risk", rows, ["amount"], "defaulted")
    flipped = [{**row, "defaulted": 1 - row["defaulted"]} for row in rows]
    held_out = [{"amount": float(i) + 0.25, "defaulted": int(i <= 5)} for i in range(12)]
    platform.watch("risk", flipped, eval_rows=held_out)
    platform.monitor.tick_once()
    assert platform.drift_retrains == 1
    assert platform.models.get("risk").version == 2


def test_selective_filter_runs_first():
    rows = [{"region": "amer" if index == 0 else "emea", "amount": index} for index in range(100)]
    plan = UnifiedAnalyticsPlatform().optimize(rows, [("region", "=", "amer"), ("amount", ">", 0)])
    assert plan["filters"][0]["field"] == "region"
    assert plan["cost"] < plan["naive_cost"]


def test_predict_during_swap():
    platform = UnifiedAnalyticsPlatform()
    rows = [{"amount": float(i), "defaulted": int(i > 5)} for i in range(12)]
    platform.train("risk", rows, ["amount"], "defaulted")
    platform.connect("confluent.cloud", {"events": [{"entity": "Event", "id": 1}]})
    platform.integrate("confluent.cloud", "Event")
    errors = []

    def read():
        try:
            for _ in range(20):
                assert platform.predict("risk", [{"amount": 9.0}])[0] in (0, 1)
        except Exception as exc:
            errors.append(exc)

    import threading
    threads = [threading.Thread(target=read) for _ in range(4)]
    for thread in threads:
        thread.start()
    platform.retrain("risk", rows)
    platform.reload("confluent.cloud", {"events": [{"entity": "Event", "id": 2}]})
    for thread in threads:
        thread.join()
    assert errors == []
    assert len(platform.export_records()) == 1


def test_reference_workloads():
    meter = UnifiedAnalyticsPlatform().productivity
    assert meter.reference("data_scientist")["increase"] == 3.0
    assert meter.reference("business_analyst")["increase"] == 2.5
    assert meter.reference("operations_overhead")["reduction"] == 0.8
    assert meter.reference("time_to_insight")["faster"] == 4.0
    assert meter.reference("risk_model_development")["reduction"] == 0.75
    assert meter.reference("regulatory_reporting")["reduction"] == 0.90
    assert set(REFERENCE) >= {
        "data_scientist",
        "business_analyst",
        "operations_overhead",
        "time_to_insight",
        "risk_model_development",
        "regulatory_reporting",
    }
    meter.record("data_scientist", 0.25)
    assert meter.mean("data_scientist") == 0.25


def test_one_security_check_denies_then_allows():
    platform = UnifiedAnalyticsPlatform()
    platform.security.enforced = True
    with pytest.raises(AccessDenied):
        platform.ingest_rows("source", "entity", [{"id": 1}])
    assert platform.data.snapshot() == []
    platform.security.grant("ada", "operator")
    platform.security.authenticate("ada")
    platform.ingest_rows("source", "entity", [{"id": 1}])
    assert len(platform.export_records()) == 1


def test_financial_case_saves_45m():
    result = UnifiedAnalyticsPlatform().case_financial_services()
    assert result.annual_savings == 45_000_000
    assert result.current_annual == 55_000_000


def test_fraud_lift_on_separable_fixture():
    platform = UnifiedAnalyticsPlatform()
    rows = [{"amount": 0.0, "fraud": 0}, {"amount": 0.0, "fraud": 0}, {"amount": 0.0, "fraud": 0}, {"amount": 10.0, "fraud": 1}]
    lift = platform.run_application("fraud_lift", rows=rows)
    assert lift["baseline_precision"] == 0.25
    assert lift["model_precision"] == 1.0
    assert lift["improvement"] == 3.0


def test_sensor_batch_carries_operator():
    platform = UnifiedAnalyticsPlatform()
    first = platform.run_application("sensor", rows=[{"reading": 1.0}, {"reading": 2.0}, {"reading": 4.0}])
    second = platform.run_application("sensor", rows=[{"reading": 1.0}, {"reading": 2.0}, {"reading": 4.0}])
    assert first["direction"] == "rising"
    assert first["channel"] == "opcua"
    assert first["operator_digest"] == second["operator_digest"]


def test_scholarship_outcomes():
    platform = UnifiedAnalyticsPlatform(allocation_rate=1.0)
    platform.recognize_value(150_000, "contract-9")
    outcomes = platform.ledger.outcomes()
    assert outcomes["scholarships"] == 3
    assert outcomes["partnerships"] == 3
    assert outcomes["regions"] == ("Caribbean", "Africa")


def test_five_hundred_systems_gate():
    platform = UnifiedAnalyticsPlatform()
    assert _gate(platform, "enterprise_systems").passed is False
    specs = [spec for spec in CATALOG if spec.protocol in ("rest", "odata")][:500]
    assert len(specs) == 500
    for spec in specs:
        platform.connect(spec.id, {"transport": lambda spec, entity, mode: []})
    assert _gate(platform, "enterprise_systems").passed is True


def test_roi_gate_opens_at_400_percent():
    platform = UnifiedAnalyticsPlatform()
    assert _gate(platform, "roi_400").passed is False
    platform.case_financial_services()
    assert _gate(platform, "roi_400").passed is True


def test_patent_gate_opens_at_ten():
    platform = UnifiedAnalyticsPlatform()
    assert _gate(platform, "patents").passed is False
    for index in range(10):
        platform.file_patent(f"analytics-{index}")
    assert platform.patents.count() == 10
    assert _gate(platform, "patents").passed is True


def test_risk_defaults_and_observed_rate():
    platform = UnifiedAnalyticsPlatform()
    assert platform.risks.probability("integration_complexity") == DEFAULTS["integration_complexity"] == "Low"
    assert platform.risks.probability("performance_scalability") == "Very Low"
    assert platform.risks.probability("user_adoption") == "Low"
    assert platform.risks.probability("competitive_response") == "High"
    for _ in range(100):
        platform.risks.observe("integration_complexity", failed=False)
    assert platform.risks.probability("integration_complexity") == "Very Low"
