"""Unified analytics platform: catalog, connectors, data, models, questions, operations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from toe.unified import UnifiedAnalyticsPlatform
from toe.unified.catalog import CATALOG, DISPLACED_CLASSES, search
from toe.unified.connectors import ConnectorUnavailable
from toe.unified.economics import CostBaseline, PlatformCost


def test_catalog_covers_a_thousand_systems_and_every_class():
    ids = [spec.id for spec in CATALOG]
    assert len(ids) >= 1000
    assert len(ids) == len(set(ids))
    assert set(DISPLACED_CLASSES) <= {spec.category for spec in CATALOG}
    for spec in CATALOG:
        assert spec.protocol
        assert spec.auth
        assert spec.entities


def test_unbound_connector_fails_closed():
    platform = UnifiedAnalyticsPlatform()
    with pytest.raises(ConnectorUnavailable):
        platform.connect("bloomberg.terminal", {})


def test_sqlite_ingest_query_and_operator(tmp_path: Path):
    database = tmp_path / "warehouse.db"
    with sqlite3.connect(database) as conn:
        conn.execute("create table accounts (region text, revenue real, segment text)")
        conn.executemany(
            "insert into accounts values (?, ?, ?)",
            [("emea", 10.0, "a"), ("emea", 5.0, "a"), ("amer", 7.0, "b")],
        )
    platform = UnifiedAnalyticsPlatform()
    platform.start()
    platform.connect(
        "postgresql.postgresql",
        {"dsn": f"sqlite:{database}", "entities": {"Table": "accounts"}},
    )
    first = platform.integrate("postgresql.postgresql", "Table")
    second = platform.integrate("postgresql.postgresql", "Table")
    assert first["receipt"].inserted == 3
    assert second["receipt"].duplicates == 3
    assert first["truth_class"] == "compiled_observation"
    answer = platform.ask("show revenue by region from table where revenue > 6")
    assert answer["rows"] == [{"region": "amer", "revenue": 7.0, "rows": 1}, {"region": "emea", "revenue": 10.0, "rows": 1}]


def test_stream_and_quarantine():
    platform = UnifiedAnalyticsPlatform()
    platform.connect(
        "confluent.cloud",
        {"events": [{"entity": "Event", "meter": "a", "kwh": 3.0}, {"entity": "Event", "meter": "a", "kwh": None}]},
    )
    platform.govern("Event", "restricted", 30, "ops", max_null_rate=0.1)
    platform.integrate("confluent.cloud", "Event", mode="stream")
    actions = platform.heal()
    assert any(action.kind == "quarantine" and action.ok for action in actions)
    assert platform.ask("count event")["rows"][0]["count"] == 0


def test_model_transfer_and_rollback():
    platform = UnifiedAnalyticsPlatform()
    rows = [{"amount": float(i), "tenure": float(i % 3), "defaulted": int(i > 5)} for i in range(12)]
    trained = platform.train("risk", rows, ["amount", "tenure"], "defaulted")
    assert trained.record.version == 1
    transferred = platform.transfer("risk", [{"amount": 9.0}], ["amount"])
    assert transferred["missing"] == ("tenure",)
    assert transferred["overlap_ratio"] == 0.5
    flipped = [{**row, "defaulted": 1 - row["defaulted"]} for row in rows]
    result = platform.retrain("risk", flipped, eval_rows=rows)
    assert result.rolled_back is True
    assert result.live_version == 1
    drivers = platform.ask("what drives risk")
    assert {row["feature"] for row in drivers["rows"]} == {"amount", "tenure"}


def test_adaptive_dashboard_and_industry_math():
    platform = UnifiedAnalyticsPlatform()
    platform.feedback("ada", "risk", depth=1)
    platform.feedback("ada", "risk", depth=1)
    platform.feedback("ada", "risk", depth=1)
    platform.feedback("ada", "energy", depth=4)
    spec = platform.dashboard_for(
        "ada",
        "ops",
        [{"id": "energy", "title": "Energy"}, {"id": "risk", "title": "Risk"}],
    )
    assert spec["widgets"][0]["id"] == "risk"
    assert spec["density"] == "compact"
    trend = platform.run_application("maintenance", rows=[{"reading": 1.0}, {"reading": 2.0}, {"reading": 4.0}])
    assert trend["direction"] == "rising"
    view = platform.run_application(
        "customer_360",
        tables={
            "accounts": [{"customer_id": "c1", "region": "emea"}],
            "tickets": [{"customer_id": "c1", "open": 2}],
        },
    )
    assert view[0]["entities"] == ["accounts", "tickets"]
    pack = platform.industry("financial_services")
    assert pack["connectors"] > 0
    assert "fraud" in pack["applications"]


def test_economics_match_the_program_draft_and_the_ledger_splits_three_ways():
    scenario = UnifiedAnalyticsPlatform().scenario()
    assert scenario["low"]["current_annual"] == 68_000_000
    assert scenario["low"]["annual_savings"] == 58_000_000
    assert scenario["high"]["current_annual"] == 165_000_000
    assert scenario["high"]["annual_savings"] == 145_000_000
    assert scenario["low"]["payback_months"] == pytest.approx(5_000_000 / (58_000_000 / 12))
    platform = UnifiedAnalyticsPlatform(allocation_rate=0.1)
    platform.economics(
        CostBaseline(2, 100.0, 0, 0, 0),
        PlatformCost(50.0, 10.0),
    )
    entry = platform.recognize_value(1000.0, "contract-7")
    assert entry.allocated == 100.0
    shares = platform.ledger.by_institution()
    assert set(shares) == {
        "University of Oxford",
        "Imperial College London",
        "University of Cambridge",
    }
    assert sum(shares.values()) == pytest.approx(100.0)


def test_phase_gates_open_only_on_measured_state():
    platform = UnifiedAnalyticsPlatform(allocation_rate=0.05)
    platform.start()
    before = {gate.name: gate.passed for gate in platform.phases()}
    assert before["started"] is True
    assert before["connectors_integrated"] is False
    crm = [spec.id for spec in search(category="crm")][:50]
    for connector_id in crm:
        spec_entity = next(spec.entities[0] for spec in CATALOG if spec.id == connector_id)
        platform.connect(connector_id, {"transport": lambda spec, entity, mode, _rows=[]: _rows})
        # transport ignores the entity; integration is optional for the count gate
        assert spec_entity
    platform.train("risk", [{"x": 0.0, "y": 0}, {"x": 1.0, "y": 1}], ["x"], "y")
    platform.feedback("ada", "risk", rating=0.97)
    platform.retire(crm[0])
    platform.economics(CostBaseline(1, 10, 0, 0, 0), PlatformCost(1, 0))
    after = {gate.name: gate.passed for gate in platform.phases()}
    assert after["connectors_integrated"] is True
    assert after["model_deployed"] is True
    assert after["self_serve"] is True
    assert after["legacy_retired"] is True
    assert after["satisfaction"] is True
    assert after["roi_positive"] is True
    assert after["scholarship_configured"] is True
    assert len(platform.displacement()["missing"]) < len(DISPLACED_CLASSES)
