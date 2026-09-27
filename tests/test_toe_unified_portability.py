"""Records export and re-import with the same digests."""

from toe.unified import UnifiedAnalyticsPlatform


def test_export_import_round_trip():
    source = UnifiedAnalyticsPlatform()
    source.ingest_rows("billing", "invoice", [{"id": 1, "amount": 5}])
    source.ingest_rows("crm", "account", [{"id": 9, "region": "emea"}])
    exported = source.export_records()
    target = UnifiedAnalyticsPlatform()
    target.import_records(exported)
    again = target.export_records()
    assert [(row["digest"], row["operator_digest"], row["entity"]) for row in again] == [
        (row["digest"], row["operator_digest"], row["entity"]) for row in exported
    ]
