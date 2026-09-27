"""Ingest digests are stable and change when the payload changes."""

from toe.unified import UnifiedAnalyticsPlatform


def test_digest_stable_and_tamper_evident():
    first = UnifiedAnalyticsPlatform()
    second = UnifiedAnalyticsPlatform()
    left = first.ingest_rows("source", "entity", [{"id": 1, "amount": 2}])
    right = second.ingest_rows("source", "entity", [{"id": 1, "amount": 2}])
    assert left["receipt"].operator_digest == right["receipt"].operator_digest
    assert left["truth_class"] == "compiled_observation"
    changed = UnifiedAnalyticsPlatform().ingest_rows("source", "entity", [{"id": 1, "amount": 3}])
    assert changed["receipt"].operator_digest != left["receipt"].operator_digest
    assert first.data.audit[0]["action"] == "ingest"
    assert first.export_records()[0]["operator_digest"] == left["receipt"].operator_digest
