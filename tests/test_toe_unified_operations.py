"""Re-probe, quarantine, release, and the worker formula."""

from toe.unified import UnifiedAnalyticsPlatform


def test_worker_formula():
    platform = UnifiedAnalyticsPlatform(max_workers=8)
    platform.operations.batch_size = 1000
    platform.operations.queue_depth = 0
    assert platform.scale().workers == 1
    platform.operations.queue_depth = 2500
    assert platform.scale().workers == 3
    platform.operations.queue_depth = 100000
    assert platform.scale().workers == 8


def test_reprobe_and_quarantine():
    platform = UnifiedAnalyticsPlatform()
    platform.connect("confluent.cloud", {"events": [{"entity": "Event", "kwh": None}]})
    platform.govern("Event", "internal", 30, "ops", max_null_rate=0.0)
    platform.integrate("confluent.cloud", "Event")
    actions = platform.heal()
    kinds = {action.kind for action in actions}
    assert "reprobe" in kinds
    assert "quarantine" in kinds
    assert platform.ask("count event")["rows"][0]["count"] == 0


def test_quarantine_is_reversible():
    platform = UnifiedAnalyticsPlatform()
    receipt = platform.ingest_rows("source", "event", [{"kwh": None}])
    platform.govern("event", "internal", 30, "ops", max_null_rate=0.0)
    platform.heal()
    assert platform.ask("count event")["rows"][0]["count"] == 0
    released = platform.release(receipt["receipt"].batch_id)
    assert released == 1
    assert platform.ask("count event")["rows"][0]["count"] == 1
