"""M3 §11 bootstrap/import + §9 module adapters + §16 observability."""

from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path

import pytest

from hyba_db.models import InvalidRecord, Quota
from hyba_db.module_adapter import MODULES, ModuleEvidenceAdapter
from hyba_db.store import OntologyStore
from hyba_db.theseus_custody import TheseusFileCustody

INTEGRITY_KEY = b"m3-bootstrap-integrity-key-012345678"
CUSTODY_KEY = b"m3-bootstrap-theseus-key-01234567890"


def _root() -> Path:
    return Path(tempfile.gettempdir()) / f"m3b-{uuid.uuid4().hex[:8]}"


def _plane(tmp_path):
    custody = TheseusFileCustody(tmp_path / "custody", hmac_key=CUSTODY_KEY)
    store = OntologyStore(tmp_path / "store.db", INTEGRITY_KEY, custody=custody)
    client = store.provision_client("m3-boot", Quota(max_records=10**7, max_blob_bytes=10**9))
    return store, custody, client.tenant_id


def test_import_existing_marks_and_custodies(tmp_path):
    store, custody, tenant_id = _plane(tmp_path)
    root = _root()
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "a.json").write_text('{"old":1}')
    (legacy / "b.bin").write_bytes(b"\x00\x01")
    result = store.files.import_existing(
        tenant_id, root, legacy, links=(("external:bootstrap", "batch1", "imported_from"),)
    )
    assert result["count"] == 2
    for item in result["imported"]:
        assert Path(item["source_path"]).is_file()
        row = store._db.execute(
            "SELECT custody_record_id FROM file_versions WHERE tenant_id=? AND file_version_id=?",
            (tenant_id, item["file_version_id"]),
        ).fetchone()
        assert custody.verify(tenant_id, row["custody_record_id"])
        ev = store._db.execute(
            "SELECT detail_json FROM file_events WHERE tenant_id=? AND file_version_id=? "
            "AND event_type='REGISTERED' ORDER BY sequence DESC LIMIT 1",
            (tenant_id, item["file_version_id"]),
        ).fetchone()
        assert json.loads(ev["detail_json"])["imported_existing"] is True
    report = store.files.reconcile_files(tenant_id, root)
    assert report.passed, report.unresolved
    store.close()
    custody.close()


def test_module_adapters_emit_under_real_producers(tmp_path):
    store, custody, tenant_id = _plane(tmp_path)
    root = _root()
    for module in ("turing", "euclid", "salamander", "toe"):
        adapter = ModuleEvidenceAdapter(store.files, module)
        obj, ver = adapter.emit(
            tenant_id,
            root,
            logical_name=f"{module}-evidence.json",
            content=b'{"module":"' + module.encode() + b'"}',
            detail={"adapter": "test"},
            links=(("external:adapter-test", module, "produced_by"),),
        )
        row = store._db.execute(
            "SELECT producer, custody_record_id FROM file_versions WHERE tenant_id=? AND file_version_id=?",
            (tenant_id, ver),
        ).fetchone()
        assert row["producer"] == module
        assert custody.verify(tenant_id, row["custody_record_id"])
    # A name custody would refuse is refused here too — fail closed.
    with pytest.raises(InvalidRecord):
        ModuleEvidenceAdapter(store.files, "not_a_real_module")
    # Canonical + file-plane producers are all buildable.
    for module in MODULES:
        ModuleEvidenceAdapter(store.files, module)
    report = store.files.reconcile_files(tenant_id, root)
    assert report.passed, report.unresolved
    store.close()
    custody.close()


def test_stats_surfaces_measured_numbers(tmp_path):
    store, custody, tenant_id = _plane(tmp_path)
    root = _root()
    adapter = ModuleEvidenceAdapter(store.files, "chronus")
    adapter.emit(tenant_id, root, logical_name="e.json", content=b"1")
    stats = store.files.stats(tenant_id)["tenants"][tenant_id]
    assert stats["file_objects_by_class"]["durable_evidence"] >= 1
    assert stats["custody_checked"] >= 1
    assert stats["custody_unverified"] == 0
    assert stats["uncustodied_versions"] == 0
    assert stats["events"] >= 3  # CREATED + REGISTERED + CUSTODIED + ...
    assert stats["quota_used_records"] >= 1
    # Whole-plane call covers every tenant.
    assert tenant_id in store.files.stats()["tenants"]
    store.close()
    custody.close()
