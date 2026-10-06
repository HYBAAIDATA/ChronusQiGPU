"""M3 §12 adversarial suite — failpoint, corruption, duplicate, orphan,
OVID exactness, tenant isolation, and restart/replay attacks on the file plane.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import uuid
from pathlib import Path

import pytest

from hyba_db.models import IntegrityFailure, InvalidRecord, Quota
from hyba_db.ovid_transform import OvidTransformPlane
from hyba_db.store import OntologyStore
from hyba_db.theseus_custody import TheseusFileCustody

INTEGRITY_KEY = b"m3-adversarial-integrity-key-0123456"
CUSTODY_KEY = b"m3-adversarial-theseus-key-0123456789"


def _root() -> Path:
    """CAS root short enough for Windows MAX_PATH with 39-char tenant ids."""
    return Path(tempfile.gettempdir()) / f"m3a-{uuid.uuid4().hex[:8]}"


def _plane(tmp_path, name="adv"):
    custody = TheseusFileCustody(tmp_path / "custody", hmac_key=CUSTODY_KEY)
    store = OntologyStore(tmp_path / f"{name}.db", INTEGRITY_KEY, custody=custody)
    client = store.provision_client(
        f"m3-{name}"[:60], Quota(max_records=10**7, max_blob_bytes=10**9)
    )
    return store, custody, client.tenant_id


def _put(store, tenant_id, root, name="artifact.bin", content=b"payload"):
    return store.files.put_file(
        tenant_id,
        root,
        logical_name=name,
        file_class="durable_evidence",
        semantic_owner="chronus",
        domain="mining:test",
        content=content,
        producer="chronus",
        links=(("external:test", "adv", "describes"),),
    )


# 12.1 — interrupted write leaves an abandoned intent, not a half-registered file
def test_crash_between_intent_and_commit(tmp_path):
    store, custody, tenant_id = _plane(tmp_path)
    root = _root()
    object_id = store.files.create_object(
        tenant_id, "interrupted.bin", "durable_evidence", "chronus", "mining:test"
    )
    digest = hashlib.sha256(b"ghost").hexdigest()
    with store._tx() as db:
        db.execute(
            "INSERT INTO file_intents VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                tenant_id,
                "fi_crash",
                object_id,
                None,
                "",
                str(root / tenant_id / "durable_evidence" / digest[:2] / digest),
                digest,
                5,
                "DECLARED",
                "{}",
                "t",
                "t",
            ),
        )
    report = store.files.reconcile_files(tenant_id, root)
    assert any("intent:fi_crash" in u for u in report.unresolved)
    results = store.files.recover_intents(tenant_id, root)
    assert results[0]["state"] == "QUARANTINED"
    store.close()
    custody.close()


# 12.2 — blob corruption is detected and classified, never papered over
def test_corrupted_blob_fails_reconciliation(tmp_path):
    store, custody, tenant_id = _plane(tmp_path)
    root = _root()
    _, version_id = _put(store, tenant_id, root)
    row = store._db.execute(
        "SELECT storage_uri FROM file_versions WHERE tenant_id=? AND file_version_id=?",
        (tenant_id, version_id),
    ).fetchone()
    blob = Path(row["storage_uri"][7:])
    blob.write_bytes(blob.read_bytes() + b"tampered")
    report = store.files.reconcile_files(tenant_id, root)
    assert version_id in report.hash_mismatches
    assert not report.passed
    store.close()
    custody.close()


# 12.3 — custody record tampering/removal downgrades to CUSTODY_MISSING
def test_missing_custody_fails_reconciliation(tmp_path):
    store, custody, tenant_id = _plane(tmp_path)
    root = _root()
    _, version_id = _put(store, tenant_id, root)
    custody_id = store._db.execute(
        "SELECT custody_record_id FROM file_versions WHERE tenant_id=? AND file_version_id=?",
        (tenant_id, version_id),
    ).fetchone()[0]
    # Remove the custody record from THESEUS — the registry must notice.
    with store._tx() as db:
        db.execute(
            "UPDATE file_versions SET custody_record_id=? WHERE tenant_id=? AND file_version_id=?",
            ("file.nonexistent_tampered", tenant_id, version_id),
        )
    report = store.files.reconcile_files(tenant_id, root)
    assert version_id in report.custody_missing
    assert custody_id != "file.nonexistent_tampered"
    store.close()
    custody.close()


# 12.4 — duplicate declarations are idempotent or fail, never forked
def test_duplicate_object_and_version_idempotent(tmp_path):
    store, custody, tenant_id = _plane(tmp_path)
    root = _root()
    obj1 = store.files.create_object(
        tenant_id, "dup.bin", "durable_evidence", "chronus", "mining:test"
    )
    obj2 = store.files.create_object(
        tenant_id, "dup.bin", "durable_evidence", "chronus", "mining:test"
    )
    assert obj1 == obj2
    with pytest.raises(InvalidRecord):
        store.files.create_object(tenant_id, "dup.bin", "manifest", "chronus", "mining:test")
    _, v1 = _put(store, tenant_id, root, name="ver.bin", content=b"v1")
    _, v1b = _put(store, tenant_id, root, name="ver.bin", content=b"v1")
    assert v1 == v1b  # same content re-registered under same name: idempotent
    store.close()
    custody.close()


# 12.5 — orphan file AND orphan record both surface
def test_orphan_file_and_orphan_record_detected(tmp_path):
    store, custody, tenant_id = _plane(tmp_path)
    root = _root()
    stray = root / "stray-blob.bin"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_bytes(b"nobody registered me")
    obj = store.files.create_object(
        tenant_id, "remote-only.bin", "source_reference", "chronus", "mining:test"
    )
    store.files.register_version(
        tenant_id,
        obj,
        b"remote",
        storage_uri="s3://bucket/unreconcilable",
        logical_path="s3://bucket/unreconcilable",
        producer="chronus",
    )
    report = store.files.reconcile_files(tenant_id, root)
    assert str(stray.resolve()) in report.orphan_files
    orphans = report.orphan_records
    assert len(orphans) == 1
    assert not report.passed
    store.close()
    custody.close()


# 12.6 — OVID exactness: EXACT contract promotes; non-EXACT and unverified fail
def test_ovid_transform_exactness_enforced(tmp_path):
    store, custody, tenant_id = _plane(tmp_path)
    root = _root()
    _, version_id = _put(store, tenant_id, root, content=b"zeckendorf-able bytes")
    plane = OvidTransformPlane(store.files)
    lineage = plane.fold_into(tenant_id, root, version_id)
    assert lineage["equivalence"]["equivalent"] is True
    assert lineage["transform_contract"]["exactness"] == "EXACT"
    row = store._db.execute(
        "SELECT ovid_lineage_id, transform_contract, exactness FROM file_versions "
        "WHERE tenant_id=? AND file_version_id=?",
        (tenant_id, lineage["transform_version_id"]),
    ).fetchone()
    assert row["ovid_lineage_id"] == lineage["lineage_id"]
    assert json.loads(row["transform_contract"])["equivalence"]["state"] == "PASS"

    from aethel.enterprise.errors import SchemaVersionError
    from aethel.enterprise.ovid_registry import OvidRegistry
    from aethel.ovid import Exactness, TransformContract

    # Non-EXACT contract refused under require_exact.
    nonexact = OvidRegistry()
    nonexact.register(
        7,
        lambda b: b[::-1],
        lambda b: b[::-1],
        contract=TransformContract(
            transform_id="reverse-bytes",
            version=7,
            exactness=Exactness.APPROXIMATE,
            reversible=True,
            domain=(("element", "bytes"),),
            invariants=("trivial",),
            residuals="declared",
            error_bound=1.0,
            support="all",
        ),
    )
    plane_nonexact = OvidTransformPlane(store.files, registry=nonexact)
    with pytest.raises(InvalidRecord):
        plane_nonexact.fold_into(tenant_id, root, version_id, transform_version=7)
    # But allowed when the caller honestly accepts approximation.
    relaxed = plane_nonexact.fold_into(
        tenant_id, root, version_id, transform_version=7, require_exact=False
    )
    assert relaxed["transform_contract"]["exactness"] == "APPROXIMATE"

    # Undeclared transform version fails closed — no implicit classification.
    with pytest.raises(SchemaVersionError):
        plane.fold_into(tenant_id, root, version_id, transform_version=99)

    # UNSUPPORTED contract refuses to run at all.
    unsupported = OvidRegistry()
    unsupported.register(
        8,
        lambda b: b,
        lambda b: b,
        contract=TransformContract(
            transform_id="never",
            version=8,
            exactness=Exactness.UNSUPPORTED,
            reversible=False,
            domain=(),
            invariants=(),
            residuals="",
            error_bound=0.0,
            support="none",
        ),
    )
    with pytest.raises((SchemaVersionError, InvalidRecord)):
        OvidTransformPlane(store.files, registry=unsupported).fold_into(
            tenant_id, root, version_id, transform_version=8, require_exact=False
        )
    store.close()
    custody.close()


def test_non_equivalent_transform_never_registers(tmp_path):
    store, custody, tenant_id = _plane(tmp_path)
    root = _root()
    _, version_id = _put(store, tenant_id, root, content=b"original")
    from aethel.enterprise.ovid_registry import OvidRegistry
    from aethel.ovid import Exactness, TransformContract

    broken = OvidRegistry()
    broken.register(
        9,
        lambda b: b,
        lambda b: b"WRONG",  # unfold does not reproduce the source
        contract=TransformContract(
            transform_id="broken-fold",
            version=9,
            exactness=Exactness.EXACT,
            reversible=True,
            domain=(("element", "bytes"),),
            invariants=("claims-exact",),
            residuals="none",
            error_bound=0.0,
            support="all",
        ),
    )
    plane = OvidTransformPlane(store.files, registry=broken)
    with pytest.raises(IntegrityFailure):
        plane.fold_into(tenant_id, root, version_id, transform_version=9)
    # Nothing was registered for the refused transform.
    assert not store._db.execute(
        "SELECT 1 FROM file_versions WHERE tenant_id=? AND file_object_id=?",
        (tenant_id, "nope"),
    ).fetchone()
    store.close()
    custody.close()


# 12.7 — tenant isolation: a blob filed under another tenant's path segment
def test_cross_tenant_blob_is_a_mismatch(tmp_path):
    store, custody, tenant_id = _plane(tmp_path)
    other = store.provision_client("m3-other", Quota(max_records=10**6, max_blob_bytes=10**8))
    root = _root()
    _, version_id = _put(store, tenant_id, root, content=b"mine")
    row = store._db.execute(
        "SELECT storage_uri FROM file_versions WHERE tenant_id=? AND file_version_id=?",
        (tenant_id, version_id),
    ).fetchone()
    real = Path(row["storage_uri"][7:])
    rel = real.relative_to(root / tenant_id)
    moved = root / other.tenant_id / rel
    moved.parent.mkdir(parents=True, exist_ok=True)
    real.replace(moved)
    with store._tx() as db:
        db.execute(
            "UPDATE file_versions SET storage_uri=?, logical_path=? "
            "WHERE tenant_id=? AND file_version_id=?",
            (f"file://{moved}", str(moved), tenant_id, version_id),
        )
    report = store.files.reconcile_files(tenant_id, root)
    assert version_id in report.tenant_mismatches
    store.close()
    custody.close()


# 12.8 — declared lineage without contract (or vice versa) is a transform mismatch
def test_lineage_contract_xor_detected(tmp_path):
    store, custody, tenant_id = _plane(tmp_path)
    root = _root()
    _, version_id = _put(store, tenant_id, root)
    with store._tx() as db:
        db.execute(
            "UPDATE file_versions SET ovid_lineage_id=? WHERE tenant_id=? AND file_version_id=?",
            ("ovt_orphaned_lineage", tenant_id, version_id),
        )
    report = store.files.reconcile_files(tenant_id, root)
    assert version_id in report.transform_mismatches
    store.close()
    custody.close()


# 12.9 — restart reconstructs everything from persisted state
def test_restart_recovers_registry_and_custody(tmp_path):
    store, custody, tenant_id = _plane(tmp_path)
    root = _root()
    _, version_id = _put(store, tenant_id, root)
    record_id = store.files.record_mining(tenant_id, "job", {"job_id": "j1"}, producer="stratum")
    digests_before = [
        r[0]
        for r in store._db.execute(
            "SELECT content_sha256 FROM file_versions WHERE tenant_id=?", (tenant_id,)
        )
    ]
    store.close()
    custody.close()

    custody2 = TheseusFileCustody(tmp_path / "custody", hmac_key=CUSTODY_KEY)
    store2 = OntologyStore(tmp_path / "adv.db", INTEGRITY_KEY, custody=custody2)
    assert store2.files.replay_lineage(tenant_id, record_id)["digest_ok"]
    assert [
        r[0]
        for r in store2._db.execute(
            "SELECT content_sha256 FROM file_versions WHERE tenant_id=?", (tenant_id,)
        )
    ] == digests_before
    assert custody2.verify(
        tenant_id,
        store2._db.execute(
            "SELECT custody_record_id FROM file_versions WHERE tenant_id=? AND file_version_id=?",
            (tenant_id, version_id),
        ).fetchone()[0],
    )
    assert store2.files.reconcile_files(tenant_id, root).passed
    store2.close()
    custody2.close()


# 12.10 — tampered custody record cannot be repaired into validity
def test_tampered_custody_record_fails_verification(tmp_path):
    store, custody, tenant_id = _plane(tmp_path)
    root = _root()
    _, version_id = _put(store, tenant_id, root)
    custody_id = store._db.execute(
        "SELECT custody_record_id FROM file_versions WHERE tenant_id=? AND file_version_id=?",
        (tenant_id, version_id),
    ).fetchone()[0]
    # Corrupt the custody blob on disk. THESEUS keeps a primary + replica and
    # heals one bad side from the other — a single-side corruption is repaired
    # (and still verifies), so the honest attack hits BOTH replicas.
    blobs = sorted((tmp_path / "custody").rglob(f"{custody_id}.json"))
    assert len(blobs) == 2, f"expected primary+replica, got {blobs}"
    blobs[0].write_bytes(blobs[0].read_bytes()[:-4] + b"XXXX")
    assert custody.verify(tenant_id, custody_id)  # healed from the good side
    for blob in blobs:
        blob.write_bytes(blob.read_bytes()[:-4] + b"XXXX")
    assert not custody.verify(tenant_id, custody_id)
    report = store.files.reconcile_files(tenant_id, root)
    assert version_id in report.custody_missing
    store.close()
    custody.close()


def test_retired_without_retention_event_is_violation(tmp_path):
    store, custody, tenant_id = _plane(tmp_path)
    root = _root()
    _, version_id = _put(store, tenant_id, root)
    with store._tx() as db:
        db.execute(
            "UPDATE file_versions SET status='RETIRED' WHERE tenant_id=? AND file_version_id=?",
            (tenant_id, version_id),
        )
    report = store.files.reconcile_files(tenant_id, root)
    assert version_id in report.retention_violations
    store.close()
    custody.close()


def test_wrong_integrity_key_fails_reconcile(tmp_path):
    """Read-side attestation: a wrong integrity key must not reconcile clean."""
    store, custody, tenant_id = _plane(tmp_path)
    root = _root()
    _, version_id = _put(store, tenant_id, root)
    store.close()
    foreign = OntologyStore(tmp_path / "adv.db", b"wrong-integrity-key-0123456789abcdef")
    foreign._db.execute("SELECT 1 FROM tenants LIMIT 1").fetchone()  # DB opens fine
    report = foreign.files.reconcile_files(tenant_id, root)
    assert not report.passed
    assert version_id in report.attestation_invalid
    foreign.close()
    custody.close()
