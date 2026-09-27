"""Data layer: one record, reject before write, append-only audit, one policy."""

import threading

import pytest

from toe.unified import UnifiedAnalyticsPlatform


def test_batch_and_stream_dedup():
    platform = UnifiedAnalyticsPlatform()
    platform.connect("confluent.cloud", {"events": [{"entity": "Event", "id": 1}]})
    first = platform.integrate("confluent.cloud", "Event", mode="batch")
    second = platform.integrate("confluent.cloud", "Event", mode="stream")
    assert first["receipt"].inserted == 1
    assert second["receipt"].duplicates == 1
    assert len(platform.export_records()) == 1


def test_concurrent_ingest_one_record():
    platform = UnifiedAnalyticsPlatform()
    errors = []

    def write():
        try:
            platform.ingest_rows("source", "entity", [{"id": 1}])
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=write) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert len(platform.export_records()) == 1


def test_malformed_row_rejected():
    platform = UnifiedAnalyticsPlatform()
    with pytest.raises(TypeError):
        platform.ingest_rows("source", "entity", [{"id": 1}, "bad"])
    assert platform.export_records() == []


def test_audit_is_append_only():
    platform = UnifiedAnalyticsPlatform()
    platform.ingest_rows("source", "entity", [{"id": 1}])
    platform.ingest_rows("source", "entity", [{"id": 2}])
    actions = [entry["action"] for entry in platform.data.audit]
    assert actions == ["ingest", "ingest"]
    assert not hasattr(platform.data, "delete_audit")


def test_policy_recorded():
    platform = UnifiedAnalyticsPlatform()
    platform.govern("entity", "restricted", 7, "owner", max_null_rate=0.1)
    policy = platform.data.policy_for("entity")
    assert policy.classification == "restricted"
    assert policy.max_null_rate == 0.1
    assert platform.data.audit[-1]["action"] == "policy"
