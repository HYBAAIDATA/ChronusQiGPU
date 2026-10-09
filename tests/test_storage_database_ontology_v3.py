from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

from hyba_db import AccessDenied, IntegrityFailure, ModuleEvidenceAdapter, OntologyStore, Quota, TheseusFileCustody
from hyba_db.production_gate import evaluate
from hyba_db.rebuild import projection_fingerprint, restore_projection_from_custody

INTEGRITY_KEY = b"i" * 32
CUSTODY_KEY = b"c" * 32


def _opened(tmp_path, namespace="ontology-v3"):
    custody = TheseusFileCustody(tmp_path / "custody", hmac_key=CUSTODY_KEY)
    store = OntologyStore(tmp_path / "ontology.db", INTEGRITY_KEY, custody=custody)
    client = store.provision_client(namespace, Quota(100_000, 100_000_000))
    return store, custody, client


def _project(store, tenant_id, *, value, state, supersedes=None, source="src-1"):
    return store.knowledge.project(
        tenant_id,
        subject="pythia:mining:structured-search",
        predicate="evidence",
        domain="mining",
        object_value=value,
        knowledge_kind="observation",
        knowledge_form="semantic",
        semantic_owner="pythia",
        producer="pythia",
        producer_version="test-revision",
        schema_version=1,
        evidence_state=state,
        evidence_class="CI_UNAVAILABLE" if state == "UNAVAILABLE" else "LOCAL_TEST_PASSED",
        maturity_stage="HYPOTHESIZED" if state == "UNAVAILABLE" else "REPRODUCED",
        source_ids=(source,),
        correlation_ids={"run": "run-1"},
        provenance={
            "code_ref": "test-revision",
            "config_digest": "cfg-1",
            "backend": "cpu-reference",
            "device_identity": "software",
            "exactness_contract": "exact",
            "policy_refs": ["authority-register-2026-10-05"],
            "owner_approval_ref": "owner-directive-2026-10-07",
            "retention_class": "evidence",
            "recovery_class": "replayable",
        },
        supersedes_id=supersedes,
    )


def test_knowledge_is_custodied_owned_and_evidence_bound(tmp_path):
    store, custody, client = _opened(tmp_path)
    try:
        record = _project(
            store,
            client.tenant_id,
            value={"status": "not-yet-observed"},
            state="UNAVAILABLE",
        )
        assert record.semantic_owner == "pythia"
        assert record.domain == "mining"
        assert record.knowledge_form == "semantic"
        assert record.maturity_stage == "HYPOTHESIZED"
        assert record.evidence_state == "UNAVAILABLE"
        assert record.evidence_class == "CI_UNAVAILABLE"
        assert record.provenance["owner_approval_ref"] == "owner-directive-2026-10-07"

        op = custody.open_tenant(client.tenant_id).get_record(record.custody_record_id)
        assert op.kind == "knowledge_projection"
        assert op.producer == "pythia"
        assert op.evidence_state == "UNAVAILABLE"
        assert op.meta["semantic_owner"] == "pythia"
        assert op.meta["evidence_class"] == "CI_UNAVAILABLE"
        assert store.knowledge.verify(client.tenant_id)["passed"] is True
    finally:
        store.close()


def test_changed_knowledge_supersedes_without_rewriting_history(tmp_path):
    store, _custody, client = _opened(tmp_path)
    try:
        first = _project(
            store,
            client.tenant_id,
            value={"status": "unavailable"},
            state="UNAVAILABLE",
        )
        second = _project(
            store,
            client.tenant_id,
            value={"status": "measured", "value": 1},
            state="MEASURED",
            supersedes=first.knowledge_id,
            source="src-2",
        )

        latest = store.knowledge.query(
            client.tenant_id,
            subject="pythia:mining:structured-search",
            predicate="evidence",
        )
        history = store.knowledge.query(
            client.tenant_id,
            subject="pythia:mining:structured-search",
            predicate="evidence",
            latest_only=False,
        )
        assert [item.knowledge_id for item in latest] == [second.knowledge_id]
        assert {item.knowledge_id for item in history} == {
            first.knowledge_id,
            second.knowledge_id,
        }
        relation = store._db.execute(
            "SELECT relation_type,custody_record_id FROM knowledge_relations "
            "WHERE tenant_id=? AND from_knowledge_id=? AND to_knowledge_id=?",
            (client.tenant_id, second.knowledge_id, first.knowledge_id),
        ).fetchone()
        assert relation["relation_type"] == "supersedes"
        assert relation["custody_record_id"]
    finally:
        store.close()


def test_knowledge_projection_rebuilds_from_theseus_custody(tmp_path):
    store, _custody, client = _opened(tmp_path)
    try:
        first = _project(
            store,
            client.tenant_id,
            value={"status": "unavailable"},
            state="UNAVAILABLE",
        )
        second = _project(
            store,
            client.tenant_id,
            value={"status": "measured"},
            state="MEASURED",
            supersedes=first.knowledge_id,
            source="src-2",
        )
        with store._tx() as db:
            db.execute("DELETE FROM knowledge_relations WHERE tenant_id=?", (client.tenant_id,))
            db.execute("DELETE FROM knowledge_records WHERE tenant_id=?", (client.tenant_id,))

        restored = store.knowledge.restore_from_custody(client.tenant_id)
        assert restored["passed"] is True
        assert set(restored["restored"]) == {first.knowledge_id, second.knowledge_id}
        assert restored["restored_relations"]
        assert store.knowledge.verify(client.tenant_id)["passed"] is True
        # Rebuilding a missing projection must not double-charge quota when
        # its original quota ledger survived.
        usage = store._db.execute(
            "SELECT used_records,used_blob_bytes FROM tenants WHERE tenant_id=?",
            (client.tenant_id,),
        ).fetchone()
        ledger = store._db.execute(
            "SELECT COALESCE(SUM(record_delta),0),COALESCE(SUM(byte_delta),0) "
            "FROM quota_events WHERE tenant_id=?",
            (client.tenant_id,),
        ).fetchone()
        assert tuple(usage) == tuple(ledger)
        latest = store.knowledge.query(client.tenant_id)
        assert second.knowledge_id in {item.knowledge_id for item in latest}
    finally:
        store.close()


def test_knowledge_tamper_and_cross_tenant_links_fail_closed(tmp_path):
    store, _custody, first_client = _opened(tmp_path)
    second_client = store.provision_client("other-tenant", Quota(100_000, 100_000_000))
    try:
        first = _project(
            store,
            first_client.tenant_id,
            value={"value": 1},
            state="MEASURED",
        )
        other = _project(
            store,
            second_client.tenant_id,
            value={"value": 2},
            state="MEASURED",
        )
        with pytest.raises(AccessDenied):
            store.knowledge.relate(
                first_client.tenant_id,
                first.knowledge_id,
                other.knowledge_id,
                "supports",
                producer="pythia",
            )
        with store._tx() as db:
            db.execute(
                "UPDATE knowledge_records SET object_json=? "
                "WHERE tenant_id=? AND knowledge_id=?",
                (json.dumps({"value": 999}), first_client.tenant_id, first.knowledge_id),
            )
        with pytest.raises(IntegrityFailure):
            store.knowledge.read(first_client.tenant_id, first.knowledge_id)
        assert store.knowledge.verify(first_client.tenant_id)["passed"] is False
    finally:
        store.close()


def test_file_versions_preserve_provenance_and_exact_custody_binding(tmp_path):
    store, custody, client = _opened(tmp_path)
    root = tmp_path / "files"
    try:
        _obj, version = store.files.put_file(
            client.tenant_id,
            root,
            logical_name="plan.json",
            file_class="plan",
            semantic_owner="pythia",
            domain="mining",
            content=b'{"plan":1}',
            producer="pythia",
            producer_version="rev-a",
            schema_version=7,
            evidence_state="MEASURED",
            provenance={
                "source_ids": ["stratum-job-1"],
                "correlation_ids": {"run": "run-1"},
                "code_ref": "rev-a",
                "backend": "chronus_batch",
                "owner_approval_ref": "owner-directive-2026-10-07",
            },
            links=(("external:test", "plan-source", "supports"),),
        )
        row = store._db.execute(
            "SELECT provenance_json,provenance_sha256 FROM file_provenance "
            "WHERE tenant_id=? AND file_version_id=?",
            (client.tenant_id, version),
        ).fetchone()
        provenance = json.loads(row["provenance_json"])
        assert provenance["semantic_owner"] == "pythia"
        assert provenance["source_ids"] == ["stratum-job-1"]
        assert provenance["owner_approval_ref"] == "owner-directive-2026-10-07"

        version_row = store._db.execute(
            "SELECT custody_record_id FROM file_versions "
            "WHERE tenant_id=? AND file_version_id=?",
            (client.tenant_id, version),
        ).fetchone()
        op = custody.open_tenant(client.tenant_id).get_record(
            version_row["custody_record_id"]
        )
        assert op.producer_version == "rev-a"
        assert op.schema_version == 7
        assert op.kind == "file_version"
        assert op.meta["semantic_owner"] == "pythia"
        assert store.files.verify_database(client.tenant_id)["passed"] is True
    finally:
        store.close()


def test_identical_bytes_do_not_merge_distinct_semantic_provenance(tmp_path):
    store, _custody, client = _opened(tmp_path)
    root = tmp_path / "files"
    try:
        kwargs = dict(
            tenant_id=client.tenant_id,
            root=root,
            logical_name="evidence.json",
            file_class="durable_evidence",
            semantic_owner="pythia",
            domain="mining",
            content=b'{"same":true}',
            producer="pythia",
            links=(("external:test", "evidence-source", "supports"),),
        )
        _obj1, v1 = store.files.put_file(
            **kwargs, provenance={"source_ids": ["source-a"]}
        )
        _obj2, v2 = store.files.put_file(
            **kwargs, provenance={"source_ids": ["source-b"]}
        )
        assert v1 != v2
        versions = store._db.execute(
            "SELECT version,content_sha256 FROM file_versions "
            "WHERE tenant_id=? ORDER BY version",
            (client.tenant_id,),
        ).fetchall()
        assert [row["version"] for row in versions] == [1, 2]
        assert versions[0]["content_sha256"] == versions[1]["content_sha256"]
    finally:
        store.close()



def test_missing_or_corrupt_cas_blob_recovers_from_theseus(tmp_path):
    store, _custody, client = _opened(tmp_path)
    root = tmp_path / "files"
    try:
        _object_id, version_id = store.files.put_file(
            client.tenant_id,
            root,
            logical_name="recoverable.json",
            file_class="durable_evidence",
            semantic_owner="pythia",
            domain="mining",
            content=b'{"recoverable":true}',
            producer="pythia",
            producer_version="recovery-test",
            provenance={
                "source_ids": ["source-recovery"],
                "code_ref": "recovery-test",
                "recovery_class": "theseus-canonical",
            },
            links=(("external:test", "recovery", "supports"),),
        )
        row = store._db.execute(
            "SELECT storage_uri,content_sha256 FROM file_versions "
            "WHERE tenant_id=? AND file_version_id=?",
            (client.tenant_id, version_id),
        ).fetchone()
        path = Path(str(row["storage_uri"])[7:])
        path.write_bytes(b"corrupt")
        before = store.files.reconcile_files(client.tenant_id, root)
        assert version_id in before.hash_mismatches

        recovered = store.files.recover_blob_from_custody(
            client.tenant_id, version_id, root
        )
        assert recovered["passed"] is True
        assert recovered["recovered"] is True
        assert path.read_bytes() == b'{"recoverable":true}'
        after = store.files.reconcile_files(client.tenant_id, root)
        assert after.passed is True
        assert store.files.verify_database(client.tenant_id)["passed"] is True

        path.unlink()
        batch = store.files.recover_blobs_from_custody(client.tenant_id, root)
        assert batch["passed"] is True
        assert version_id in batch["recovered"]
        assert store.files.reconcile_files(client.tenant_id, root).passed is True
    finally:
        store.close()

def test_destructive_rebuild_restores_folds_certificates_and_ontology(tmp_path):
    store, _custody, client = _opened(tmp_path)
    tenant_id = client.tenant_id
    try:
        first = store.write_fold(
            tenant_id,
            [float(i) / 10.0 for i in range(11)],
        )
        second = store.write_fold(
            tenant_id,
            [float(i + 11) / 10.0 for i in range(11)],
            parent_id=first.id,
        )
        term_id = store.register_term(
            tenant_id,
            "mining.work.identity",
            "A versioned identity binding pool session, job, target and nonce space.",
            {"owner": "PYTHIA", "custody": "THESEUS", "transform": "OVID"},
        )
        before = projection_fingerprint(store, tenant_id)
        assert before["folds"]
        assert before["certificates"]
        assert before["ontology"]
    finally:
        store.close()

    rebuilt_custody = TheseusFileCustody(
        tmp_path / "custody",
        hmac_key=CUSTODY_KEY,
    )
    rebuilt = OntologyStore(
        tmp_path / "rebuilt-ontology.db",
        INTEGRITY_KEY,
        custody=rebuilt_custody,
    )
    try:
        report = restore_projection_from_custody(
            rebuilt,
            tenant_id,
            tmp_path / "files",
        )
        after = projection_fingerprint(rebuilt, tenant_id)

        assert report["passed"] is True
        assert set(report["folds"]) == {first.id, second.id}
        assert report["ontology_terms"] == (term_id,)
        assert after["folds"] == before["folds"]
        assert after["certificates"] == before["certificates"]
        assert after["ontology"] == before["ontology"]
        assert rebuilt.read_fold(tenant_id, second.id).parent_id == first.id
        assert rebuilt.verify_database(tenant_id).passed is True
    finally:
        rebuilt.close()


def test_database_verification_refuses_unavailable_custody_adapter(tmp_path):
    store, _custody, client = _opened(tmp_path)
    root = tmp_path / "files"
    tenant_id = client.tenant_id
    store.files.put_file(
        tenant_id,
        root,
        logical_name="audit.json",
        file_class="audit",
        semantic_owner="theseus",
        domain="audit",
        content=b"{}",
        producer="theseus",
        links=(("external:test", "audit", "supports"),),
    )
    store.close()

    reopened = OntologyStore(tmp_path / "ontology.db", INTEGRITY_KEY, custody=None)
    try:
        verdict = reopened.verify_database(tenant_id)
        assert verdict.passed is False
        assert verdict.file_plane_ok is False
        assert any("custody adapter unavailable" in error for error in verdict.errors)
    finally:
        reopened.close()


def test_installed_distribution_includes_hyba_db_and_gate():
    with open("pyproject.toml", "rb") as handle:
        project = tomllib.load(handle)
    setuptools = project["tool"]["setuptools"]
    assert setuptools["package-dir"]["hyba_db"] == "hyba_db"
    assert "hyba_db" in setuptools["packages"]
    assert (
        project["project"]["scripts"]["pythia-storage-db-gate"]
        == "hyba_db.production_gate:main"
    )


def test_production_gate_closes_database_storage_and_custody_together(tmp_path):
    store, _custody, client = _opened(tmp_path)
    root = tmp_path / "files"
    tenant_id = client.tenant_id
    store.files.put_file(
        tenant_id,
        root,
        logical_name="production-evidence.json",
        file_class="durable_evidence",
        semantic_owner="pythia",
        domain="mining",
        content=b'{"evidence":"local"}',
        producer="pythia",
        producer_version="test-revision",
        evidence_state="LOCAL_E2E_EXECUTED",
        provenance={
            "source_ids": ["local-e2e"],
            "code_ref": "test-revision",
            "owner_approval_ref": "owner-directive-2026-10-07",
        },
        links=(("external:test", "local-e2e", "supports"),),
    )
    store.close()

    blocked = evaluate(
        db_path=tmp_path / "ontology.db",
        storage_root=root,
        tenant_id=tenant_id,
        integrity_key=INTEGRITY_KEY,
        custody_root=tmp_path / "custody",
        custody_key=CUSTODY_KEY,
    )
    assert blocked["passed"] is False
    assert blocked["checks"]["producer_revalidation_complete"] is False
    assert blocked["pending_producer_revalidation"]

    report = evaluate(
        db_path=tmp_path / "ontology.db",
        storage_root=root,
        tenant_id=tenant_id,
        integrity_key=INTEGRITY_KEY,
        custody_root=tmp_path / "custody",
        custody_key=CUSTODY_KEY,
        producer_revalidators={
            "pythia": lambda _record: "PASS",
            "theseus": lambda _record: "PASS",
        },
    )
    assert report["passed"] is True
    assert all(report["checks"].values())
    assert report["pending_producer_revalidation"] == {}
    assert report["producer_revalidation_errors"] == []
    assert report["destructive_rebuild"]["passed"] is True
    assert report["claim_boundary"]["live_pool"] == "UNAVAILABLE"
    assert report["claim_boundary"]["accepted_share"] == "UNAVAILABLE"


def test_module_adapter_projects_knowledge_under_producer_identity(tmp_path):
    store, _custody, client = _opened(tmp_path)
    try:
        adapter = ModuleEvidenceAdapter(store.files, "pythia")
        record = adapter.project_knowledge(
            client.tenant_id,
            subject="pythia:mining:search-plan",
            predicate="authority",
            domain="mining",
            object_value={"owner": "PYTHIA"},
            knowledge_kind="decision",
            knowledge_form="meta",
            evidence_state="PASS",
            maturity_stage="PROVISIONALLY_TRUSTED",
            producer_version="test-revision",
            provenance={"owner_approval_ref": "owner-directive-2026-10-07"},
        )
        assert record.producer == "pythia"
        assert record.semantic_owner == "pythia"
        assert record.evidence_state == "PASS"
        assert store.knowledge.verify(client.tenant_id)["passed"] is True
    finally:
        store.close()
