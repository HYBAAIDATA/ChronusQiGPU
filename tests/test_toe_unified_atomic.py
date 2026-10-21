"""Atomic in-process import publication, rollback and quarantine visibility."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import threading

import pytest

from toe.unified.data_layer import IngestBatch, UnifiedDataLayer, normalize_snapshot


def batch(entity, rows):
    return IngestBatch("s", entity, rows, "operator-digest", "event_stream")


def store_state(layer):
    with layer._lock:
        return deepcopy(
            {
                "records": layer.snapshot(),
                "audit": layer.audit,
                "row_audit": layer.row_audit,
                "batch": layer._batch,
                "payloads": layer._batch_payloads,
                "blobs": layer._blobs,
                "index": layer._by_entity,
                "raw_bytes": layer.raw_bytes,
                "stored_bytes": layer.stored_bytes,
            }
        )


def test_bad_later_batch_leaves_every_live_store_field_unchanged():
    layer = UnifiedDataLayer()
    layer.ingest_atomic([batch("existing", [{"id": 0}])], [])
    before = store_state(layer)
    with pytest.raises(TypeError):
        layer.ingest_atomic([batch("good", [{"id": 1}]), batch("bad", ["bad"])], [])
    assert store_state(layer) == before
    receipt = layer.ingest_atomic([batch("next", [{"id": 2}])], [])[0]
    assert receipt.batch_id == "b2"


def test_failure_after_staged_quarantine_does_not_mutate_live_duplicates(monkeypatch):
    layer = UnifiedDataLayer()
    payload = {"id": 1}
    layer.ingest_atomic([batch("events", [payload])], [])
    before = store_state(layer)
    original = UnifiedDataLayer.quarantine_payloads

    def fail_after_quarantine(staged, rows):
        original(staged, rows)
        raise RuntimeError("injected quarantine failure")

    monkeypatch.setattr(UnifiedDataLayer, "quarantine_payloads", fail_after_quarantine)
    with pytest.raises(RuntimeError, match="injected"):
        layer.ingest_atomic([batch("events", [payload])], [("s", "events", payload)])
    assert store_state(layer) == before


def test_snapshot_readers_cannot_see_partially_imported_or_unquarantined_rows(monkeypatch):
    layer = UnifiedDataLayer()
    staged_first_batch = threading.Event()
    publish = threading.Event()
    reader_started = threading.Event()
    original = UnifiedDataLayer.ingest

    def pause_after_first(staged, *args, **kwargs):
        receipt = original(staged, *args, **kwargs)
        if staged is not layer and args[1] == "first":
            staged_first_batch.set()
            assert publish.wait(5)
        return receipt

    monkeypatch.setattr(UnifiedDataLayer, "ingest", pause_after_first)

    def read():
        reader_started.set()
        return layer.snapshot()

    with ThreadPoolExecutor(max_workers=2) as pool:
        writer = pool.submit(
            layer.ingest_atomic,
            [batch("first", [{"id": 1}]), batch("second", [{"id": 2}])],
            [("s", "first", {"id": 1}), ("s", "second", {"id": 2})],
        )
        try:
            assert staged_first_batch.wait(5)
            reader = pool.submit(read)
            assert reader_started.wait(5)
            assert not reader.done()
        finally:
            publish.set()
        writer.result(timeout=5)
        snapshot = reader.result(timeout=5)
    assert len(snapshot) == 2
    assert all(row["quarantined"] for row in snapshot)
    assert layer.rows("first") == []
    assert layer.rows("second") == []


def test_duplicate_import_cannot_clear_existing_quarantine():
    layer = UnifiedDataLayer()
    rows = [{"id": 1}]
    layer.ingest_atomic([batch("events", rows)], [("s", "events", rows[0])])
    receipt = layer.ingest_atomic([batch("events", rows)], [])[0]
    assert receipt.duplicates == 1
    assert layer.snapshot()[0]["quarantined"] is True


def test_snapshot_normalization_detaches_nested_payloads_and_checks_integrity():
    source = [{"source": "s", "entity": "e", "payload": {"values": [1]}}]
    normalized = normalize_snapshot(source)
    source[0]["payload"]["values"].append(2)
    assert normalized[0]["payload"] == {"values": [1]}
    with pytest.raises(ValueError, match="digest"):
        normalize_snapshot([{**source[0], "digest": "forged"}])
    with pytest.raises(ValueError, match="boolean"):
        normalize_snapshot([{**source[0], "quarantined": "false"}])


def test_import_detaches_nested_payloads_from_batch_callers():
    layer = UnifiedDataLayer()
    rows = [{"values": [1]}]
    layer.ingest_atomic([batch("events", rows)], [])
    rows[0]["values"].append(2)
    assert layer.snapshot()[0]["payload"] == {"values": [1]}


@pytest.mark.parametrize("bad_payload", ["bad", {"n": float("nan")}])
def test_facade_rejects_an_invalid_later_group_before_any_publish(bad_payload):
    from toe.unified import UnifiedAnalyticsPlatform

    platform = UnifiedAnalyticsPlatform()
    platform.ingest_rows("existing", "events", [{"id": 0}])
    before = store_state(platform.data)
    receipt_count = len(platform._receipts)
    incoming = [
        {"source": "a", "entity": "events", "payload": {"id": 1}},
        {"source": "z", "entity": "events", "payload": bad_payload},
    ]
    with pytest.raises((TypeError, ValueError)):
        platform.import_records(incoming)
    assert store_state(platform.data) == before
    assert len(platform._receipts) == receipt_count


def test_facade_atomic_import_preserves_flags_and_operator_bindings():
    from toe.operator_compilers import compile_operator
    from toe.unified import UnifiedAnalyticsPlatform

    platform = UnifiedAnalyticsPlatform()
    rows = [
        {"source": "a", "entity": "events", "payload": {"id": 1}, "quarantined": True},
        {"source": "b", "entity": "events", "payload": {"id": 2}, "quarantined": False},
    ]
    results = platform.import_records(rows)
    assert len(results) == 2
    assert sum(record["quarantined"] for record in platform.export_records()) == 1
    assert platform.ask("count events")["rows"][0]["count"] == 1
    for result, incoming in zip(results, rows):
        assert (
            result["receipt"].operator_digest
            == compile_operator({"events": [incoming["payload"]]}).input_digest
        )


def test_ingest_and_export_do_not_expose_mutable_nested_store_payloads():
    layer = UnifiedDataLayer()
    rows = [{"values": [1]}]
    receipt = layer.ingest("s", "events", rows, operator_digest="d", operator_kind="k")
    rows[0]["values"].append(2)
    exported = layer.snapshot()
    exported[0]["payload"]["values"].append(3)
    stored = layer.snapshot()[0]
    assert stored["payload"] == {"values": [1]}
    assert layer.restore_payload(stored["digest"]) == stored["payload"]
    assert receipt.received == 1
