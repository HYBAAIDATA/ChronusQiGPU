"""Layer 5. Two or more modules on one path. Iris rows are the real input."""

import sqlite3

from toe.unified import UnifiedAnalyticsPlatform
from toe.unified.catalog import CATALOG

from test_toe_unified_invariants import SEED, load_iris

TOUCHED = {"A1", "A4", "C1", "C5", "C7", "C12", "E3", "F4", "G5", "I1", "I4"}
assert SEED == 1517


def test_int_1_ingest_train_ask():
    iris = load_iris()
    platform = UnifiedAnalyticsPlatform()
    receipt = platform.ingest_rows("uci", "iris", iris)
    trained = platform.train(
        "setosa",
        [{"petal_length": row["petal_length"], "setosa": row["setosa"]} for row in iris],
        ["petal_length"],
        "setosa",
    )
    answer = platform.ask("count iris")
    assert receipt["receipt"].operator_digest
    assert trained.record.model.model_family == "exact_linear"
    assert receipt["receipt"].received == 150
    assert answer["rows"][0]["count"] == receipt["receipt"].inserted
    assert receipt["receipt"].inserted < 150


def test_int_2_drift_retrain_crosses_monitor_and_models():
    iris = load_iris()
    rows = [{"petal_length": row["petal_length"], "setosa": row["setosa"]} for row in iris]
    platform = UnifiedAnalyticsPlatform()
    platform.train("setosa", rows, ["petal_length"], "setosa")
    flipped = [{**row, "setosa": 1 - row["setosa"]} for row in rows]
    platform.watch("setosa", flipped)
    platform.monitor.tick_once()
    assert platform.drift_retrains == 1
    assert platform.models.get("setosa").version == 2


def test_int_3_heal_quarantines_a_dirty_batch():
    platform = UnifiedAnalyticsPlatform()
    platform.connect("confluent.cloud", {"events": [{"entity": "Event", "petal_length": None}]})
    platform.govern("Event", "internal", 30, "ops", max_null_rate=0.0)
    platform.integrate("confluent.cloud", "Event")
    kinds = {action.kind for action in platform.heal()}
    assert "quarantine" in kinds
    assert platform.ask("count event")["rows"][0]["count"] == 0


def test_int_4_recognize_value_reaches_three_shares():
    platform = UnifiedAnalyticsPlatform(allocation_rate=0.1)
    platform.recognize_value(1000, "iris-contract")
    shares = platform.ledger.by_institution()
    assert len(shares) == 3
    assert abs(sum(shares.values()) - 100) < 1e-9


def test_int_5_case_opens_the_roi_gate():
    platform = UnifiedAnalyticsPlatform()
    platform.case_financial_services()
    gate = next(item for item in platform.phases() if item.name == "roi_400")
    assert gate.passed is True


def test_int_6_sqlite_extract_of_iris_carries_a_digest(tmp_path):
    iris = load_iris()
    database = tmp_path / "iris.db"
    with sqlite3.connect(database) as conn:
        conn.execute("create table iris (row_id integer, petal_length real, setosa integer)")
        conn.executemany(
            "insert into iris values (?, ?, ?)",
            [(index, row["petal_length"], row["setosa"]) for index, row in enumerate(iris)],
        )
    spec = next(item for item in CATALOG if item.protocol == "jdbc")
    platform = UnifiedAnalyticsPlatform()
    platform.connect(
        spec.id,
        {"dsn": f"sqlite:{database}", "entities": {spec.entities[0]: "iris"}},
    )
    receipt = platform.integrate(spec.id, spec.entities[0])
    assert receipt["receipt"].inserted == 150
    assert receipt["receipt"].operator_digest
    assert len(receipt["receipt"].operator_digest) == 64
