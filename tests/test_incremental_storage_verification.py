"""Incremental per-lease verification of the THESEUS/OVID file plane.

Every lease verifies rows appended since the last pass; the full pass
(every older row) runs on the owner-set interval. A failure found by either
stays failed until a later full pass succeeds.
"""

from __future__ import annotations

from hyba_db import OntologyStore, Quota, TheseusFileCustody

from chronus.mla1517.mining.storage_recorder import MiningStorageRecorder

KEY = b"incremental-verify-test-key-32-bytes"
CUSTODY_KEY = b"incremental-verify-custody-key-0123456"


def _store(tmp_path):
    custody = TheseusFileCustody(tmp_path / "custody", hmac_key=CUSTODY_KEY)
    return OntologyStore(tmp_path / "ontology.db", KEY, custody=custody)


def _put(store, tid, root, i):
    return store.files.put_file(
        tid, root, logical_name=f"f{i}.json", file_class="report", semantic_owner="pythia",
        domain="audit", content=b'{"i":%d}' % i, producer="stratum",
    )[1]


def _tamper_provenance(store, tid, version_id):
    store._db.execute(
        "UPDATE file_provenance SET provenance_sha256=? WHERE tenant_id=? AND file_version_id=?",
        ("0" * 64, tid, version_id),
    )
    store._db.commit()


def test_incremental_pass_verifies_only_new_rows_and_catches_tampered_new_row(tmp_path):
    with _store(tmp_path) as store:
        tid = store.provision_client("alpha", Quota(10_000, 10_000_000)).tenant_id
        root = tmp_path / "objects"
        for i in range(3):
            _put(store, tid, root, i)
        full = store.files.verify_database(tid)
        assert full["passed"] and not full["incremental"]
        mark = full["watermark"]
        assert mark["file_versions"] >= 3
        empty = store.files.verify_database(tid, since=mark)
        assert empty["passed"] and empty["incremental"] and empty["watermark"] == mark
        new = _put(store, tid, root, 99)
        _tamper_provenance(store, tid, new)
        inc = store.files.verify_database(tid, since=mark)
        assert not inc["passed"]
        assert any(new in e for e in inc["errors"])


def test_old_row_tamper_is_caught_by_the_full_pass(tmp_path):
    with _store(tmp_path) as store:
        tid = store.provision_client("alpha", Quota(10_000, 10_000_000)).tenant_id
        root = tmp_path / "objects"
        old = _put(store, tid, root, 0)
        mark = store.files.verify_database(tid)["watermark"]
        _tamper_provenance(store, tid, old)
        assert store.files.verify_database(tid, since=mark)["passed"]  # not re-read
        assert not store.files.verify_database(tid)["passed"]  # full pass sees it


class _Files:
    def __init__(self):
        self.results = []
        self.calls = []

    def verify_database(self, tenant_id, since=None):
        self.calls.append(since)
        passed = self.results.pop(0)
        return {"passed": passed, "file_plane_ok": passed, "watermark": {"file_versions": len(self.calls)}}

    def verify_mining(self, tenant_id):
        return True


def _recorder(files):
    rec = MiningStorageRecorder.__new__(MiningStorageRecorder)
    rec.files, rec.tenant_id, rec.root = files, "t", None
    rec.strict, rec.errors, rec.last_error, rec._last_health = True, 0, None, None
    return rec


def test_recorder_incremental_failure_is_sticky_until_full_pass():
    files = _Files()
    rec = _recorder(files)
    files.results = [True, True, False, True, True]
    assert rec.health(reconcile=False, full=False)["verification"] == "full"  # no prior full pass
    assert rec.health(reconcile=False, full=False)["file_plane_ok"]
    assert files.calls[1] == {"file_versions": 1}  # incremental from the watermark
    assert not rec.health(reconcile=False, full=False)["file_plane_ok"]  # new rows fail
    assert not rec.health(reconcile=False, full=False)["file_plane_ok"]  # still failed
    assert rec.health(reconcile=False, full=True)["file_plane_ok"]  # full pass clears
    assert files.calls[-1] is None
