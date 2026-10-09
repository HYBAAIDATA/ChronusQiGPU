"""M3 §13 controlled local mining-storage E2E voyage.

Runs the canonical mining path (FakePool -> Stratum client ->
PythiaProductionMiningCoordinator -> Chronus execution -> SHA256d proof ->
submission -> literal pool outcome -> PYTHIA learning) while a
MiningStorageRecorder observes the causal ledger and projects every boundary
into the hyba_db file plane under THESEUS custody. Then the process restarts
(fresh store handle on the same DB) and the lineage replays to the same
content addresses.
"""

from __future__ import annotations

import asyncio
import pytest
import json
import tempfile
import uuid
from pathlib import Path

from manifold_pool_coordinator import PoolEndpoint
from test_agentic_voyages import EASY_TARGET, FakePool, _connected, _job, _served, bip34_coinb1

from chronus.mla1517.mining.causal import CausalCoordinate, CausalEvent, CausalLedger, load_jsonl
from chronus.mla1517.mining.geodesic_support import PythiaProductionMiningCoordinator
from chronus.mla1517.mining.hashrate_governor import HashrateGovernor
from chronus.mla1517.mining.pool_chain import PoolChainObserver
from chronus.mla1517.mining.session import MiningSession
from chronus.mla1517.mining.storage_recorder import MiningStorageRecorder
from hyba_db.models import Quota
from hyba_db.store import OntologyStore
from hyba_db.theseus_custody import TheseusFileCustody

INTEGRITY_KEY = b"m3-voyage-integrity-key-0123456789ab"
CUSTODY_KEY = b"m3-voyage-theseus-custody-key-0123456!"


def _short_root() -> Path:
    """CAS root short enough for Windows MAX_PATH with 39-char tenant ids."""
    return Path(tempfile.gettempdir()) / f"m3v-{uuid.uuid4().hex[:8]}"


def _plane(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    custody = TheseusFileCustody(tmp_path / "custody", hmac_key=CUSTODY_KEY)
    store = OntologyStore(tmp_path / "store.db", INTEGRITY_KEY, custody=custody)
    client = store.provision_client("m3-voyage", Quota(max_records=10**7, max_blob_bytes=10**9))
    return store, custody, client.tenant_id


def _coordinator(port: int) -> PythiaProductionMiningCoordinator:
    coord = PythiaProductionMiningCoordinator(
        [PoolEndpoint("127.0.0.1", port, "m3-voyage")],
        username="m3-voyage-worker",
        password="x",
        submit_enabled=True,
        mining_session=MiningSession(cooldown_seconds=0),
    )
    coord.chain_observer = PoolChainObserver(lambda: coord.client)
    coord.governor = HashrateGovernor(max_network_fraction=None)
    return coord


def _mining_rows(store, tenant_id):
    rows = store._db.execute(
        "SELECT kind, payload_json, evidence_state, custody_record_id, content_sha256 "
        "FROM mining_lifecycle WHERE tenant_id=?",
        (tenant_id,),
    ).fetchall()
    return [(dict(r)) for r in rows]


async def _voyage(tmp_path):
    store, custody, tenant_id = _plane(tmp_path)
    root = _short_root()
    recorder = MiningStorageRecorder(store.files, tenant_id, root)
    pool = FakePool(
        target=EASY_TARGET,
        job=_job("job-m3-voyage", coinb1=bip34_coinb1(900_001)),
    )
    server, port = await _served(pool)
    coord = _coordinator(port)
    coord.causal.set_observer(recorder.observe)
    try:
        await _connected(coord, "job-m3-voyage")
        coord._last_chain_poll = 0.0
        assert await coord.before_hardware_poll() is True
        assert await coord.search_current_job() is True
        assert len(pool.submits) == 1
        assert coord.evidence_snapshot()["last_execution"]["pool_outcome"] == "ACCEPTED"
    finally:
        if coord.client:
            await coord.client.close()
        server.close()
        await server.wait_closed()
    return store, custody, tenant_id, root, recorder


def test_voyage_projects_full_custodied_lifecycle(tmp_path):
    store, custody, tenant_id, root, recorder = asyncio.run(_voyage(tmp_path))
    try:
        rows = _mining_rows(store, tenant_id)
        kinds = {row["kind"] for row in rows}
        assert {
            "job",
            "search_plan",
            "lease",
            "execution",
            "candidate_verification",
            "verified_proof",
            "submission",
            "pool_outcome",
            "learning",
        } <= kinds
        outcomes = [
            json.loads(r["payload_json"])["pool_outcome"]
            for r in rows
            if r["kind"] == "pool_outcome"
        ]
        assert "ACCEPTED" in outcomes
        # Every chain record is THESEUS-custodied — verified, not asserted.
        for row in rows:
            assert custody.verify(tenant_id, row["custody_record_id"]), row["kind"]
        # Boundary receipts exist on the CAS file plane and reconcile clean.
        file_rows = store._db.execute(
            "SELECT file_version_id, storage_uri, custody_record_id FROM file_versions "
            "WHERE tenant_id=?",
            (tenant_id,),
        ).fetchall()
        assert file_rows, "no durable receipts registered"
        for row in file_rows:
            assert row["storage_uri"].startswith("file://")
            assert custody.verify(tenant_id, row["custody_record_id"])
        report = store.files.reconcile_files(tenant_id, root)
        assert report.passed, report.unresolved
        verification = store.verify_database(tenant_id, storage_roots={tenant_id: str(root)})
        assert verification.reconciliation_ok is True
        assert verification.file_plane_ok is True
        assert verification.mining_chain_ok is True
        assert verification.passed, verification.errors
        assert recorder.snapshot()["errors"] == 0
    finally:
        store.close()


def test_restart_replays_lineage_to_same_digests(tmp_path):
    store, custody, tenant_id, root, _recorder = asyncio.run(_voyage(tmp_path))
    learning = [
        r["record_id"]
        for r in store._db.execute(
            "SELECT record_id FROM mining_lifecycle WHERE tenant_id=? AND kind='learning'",
            (tenant_id,),
        ).fetchall()
    ]
    assert learning
    before = store.files.replay_lineage(tenant_id, learning[-1])
    before_sha = {item["record_id"]: item["content_sha256"] for item in before["chain"]}
    store.close()
    custody.close()

    # Restart: new process handles over the same persisted state.
    custody2 = TheseusFileCustody(tmp_path / "custody", hmac_key=CUSTODY_KEY)
    store2 = OntologyStore(tmp_path / "store.db", INTEGRITY_KEY, custody=custody2)
    try:
        after = store2.files.replay_lineage(tenant_id, learning[-1])
        assert after["digest_ok"] is True
        assert {i["record_id"]: i["content_sha256"] for i in after["chain"]} == before_sha
        assert after["length"] == before["length"]
        report = store2.files.reconcile_files(tenant_id, root)
        assert report.passed, report.unresolved
    finally:
        store2.close()
        custody2.close()


def test_recorder_replays_causal_jsonl_to_identical_chain(tmp_path):
    """Ledger mirror -> fresh recorder -> identical mining digests."""
    store, custody, tenant_id = _plane(tmp_path)
    root = tmp_path / "storage"
    ledger_path = tmp_path / "causal.jsonl"
    ledger = CausalLedger(path=ledger_path)
    recorder = MiningStorageRecorder(store.files, tenant_id, root)
    ledger.set_observer(recorder.observe)
    coord = CausalCoordinate(
        pool_session_id="sess1",
        generation=1,
        job_fingerprint="fp1",
        plan_id="plan1",
        lease_id="lease1",
        execution_id="exec1",
        submission_id="sub1",
        job_id="job1",
    )
    ledger.record("identity_bound", coord, job_id="job1", clean_jobs=True)
    ledger.record("plan_created", coord, window=1024)
    ledger.record("execution_started", coord, extranonce2="aa")
    ledger.record("candidate_found", coord, nonce="0000002a")
    ledger.record("submission_sent", coord, job_id="job1", block_hash="ab" * 32)
    ledger.record("learning_observed", coord, pool_outcome="ACCEPTED")
    first = {rid: k for rid, k in recorder.records.items()}

    # Replay the JSONL mirror into a SECOND store: digests must match exactly.
    store2, custody2, tenant2 = _plane(tmp_path / "replayed")
    replayed = MiningStorageRecorder(store2.files, tenant2, _short_root())
    for event in load_jsonl(ledger_path.read_text().splitlines()):
        replayed.observe(event)
    assert len(replayed.records) == len(first)
    # Payload digests (content_sha256) must be identical across replays.
    digests1 = sorted(
        row[0]
        for row in store._db.execute(
            "SELECT content_sha256 FROM mining_lifecycle WHERE tenant_id=?", (tenant_id,)
        )
    )
    digests2 = sorted(
        row[0]
        for row in store2._db.execute(
            "SELECT content_sha256 FROM mining_lifecycle WHERE tenant_id=?", (tenant2,)
        )
    )
    assert digests1 == digests2
    store.close()
    custody.close()
    store2.close()
    custody2.close()


def test_recorder_materializes_missing_parents_honestly(tmp_path):
    store, custody, tenant_id = _plane(tmp_path)
    recorder = MiningStorageRecorder(store.files, tenant_id, _short_root())
    event = CausalEvent(
        1,
        0.0,
        "submission_sent",
        CausalCoordinate(submission_id="sub-late"),
        {"job_id": "job-late"},
    )
    recorder.observe(event)
    rows = _mining_rows(store, tenant_id)
    by_kind = {}
    for row in rows:
        by_kind.setdefault(row["kind"], []).append(row)
    # A submission implies upstream boundaries; the gap is marked MISSING,
    # never minted as observed evidence.
    assert "submission" in by_kind
    assert by_kind["job"][0]["evidence_state"] == "MISSING"
    assert json.loads(by_kind["job"][0]["payload_json"])["inferred_from_downstream"]
    store.close()
    custody.close()


def test_no_submission_means_no_pool_outcome(tmp_path):
    store, custody, tenant_id = _plane(tmp_path)
    recorder = MiningStorageRecorder(store.files, tenant_id, _short_root())
    coord = CausalCoordinate(pool_session_id="s", generation=1, job_id="j")
    recorder.observe(
        CausalEvent(1, 0.0, "identity_bound", coord, {"job_id": "j", "clean_jobs": True})
    )
    recorder.observe(
        CausalEvent(2, 0.1, "learning_observed", coord, {"pool_outcome": "NO_CANDIDATE"})
    )
    kinds = {row["kind"] for row in _mining_rows(store, tenant_id)}
    assert "pool_outcome" not in kinds
    assert "submission" not in kinds
    # The observed outcome is still preserved as durable evidence.
    assert (
        recorder.receipts
        or store._db.execute(
            "SELECT 1 FROM file_versions WHERE tenant_id=?", (tenant_id,)
        ).fetchone()
    )
    store.close()
    custody.close()


def test_recorder_observer_failures_are_counted_not_raised(tmp_path):
    store, custody, tenant_id = _plane(tmp_path)
    recorder = MiningStorageRecorder(store.files, tenant_id, _short_root())
    ledger = CausalLedger()
    ledger.set_observer(recorder.observe)
    store.close()  # break the storage plane mid-observation
    ledger.record("identity_bound", CausalCoordinate(), job_id="x")
    # The recorder isolates its own failures (counted, not raised), so the
    # mining path keeps running even when the storage plane is broken.
    assert recorder.errors >= 1
    assert ledger.observer_errors == 0
    custody.close()


def test_raw_observer_failure_surfaces_on_ledger(tmp_path):
    """A non-isolating observer's failure is counted on the ledger itself."""
    ledger = CausalLedger()

    def broken(event):
        raise RuntimeError("observer exploded")

    ledger.set_observer(broken)
    ledger.record("identity_bound", CausalCoordinate(), job_id="x")
    assert ledger.observer_errors == 1
    assert len(ledger.events()) == 1


def test_from_env_honors_tenant_and_requires_keys(tmp_path, monkeypatch):
    """The live-wiring seam: from_env binds PYTHIA_STORAGE_* correctly."""
    from chronus.mla1517.mining.storage_recorder import MiningStorageRecorder

    monkeypatch.delenv("PYTHIA_STORAGE_DB", raising=False)
    monkeypatch.delenv("PYTHIA_STORAGE_ROOT", raising=False)
    assert MiningStorageRecorder.from_env() is None  # absent config: untouched

    monkeypatch.setenv("PYTHIA_STORAGE_DB", str(tmp_path / "s.db"))
    monkeypatch.setenv("PYTHIA_STORAGE_ROOT", str(tmp_path / "root"))
    with pytest.raises(RuntimeError, match="KEY_HEX"):
        MiningStorageRecorder.from_env()

    monkeypatch.setenv("PYTHIA_STORAGE_INTEGRITY_KEY_HEX", "ab" * 32)
    monkeypatch.setenv("PYTHIA_STORAGE_CUSTODY_KEY_HEX", "cd" * 32)
    monkeypatch.setenv("PYTHIA_STORAGE_TENANT", "Ops Tenant!")
    rec = MiningStorageRecorder.from_env(worker="w1")
    assert rec is not None
    row = rec._store._db.execute(
        "SELECT namespace FROM tenants WHERE tenant_id=?", (rec.tenant_id,)
    ).fetchone()
    assert row[0] == "ops-tenant"
    rec._store.close()


def test_from_env_rejects_empty_sanitized_tenant(tmp_path, monkeypatch):
    from chronus.mla1517.mining.storage_recorder import MiningStorageRecorder

    monkeypatch.setenv("PYTHIA_STORAGE_DB", str(tmp_path / "s.db"))
    monkeypatch.setenv("PYTHIA_STORAGE_ROOT", str(tmp_path / "root"))
    monkeypatch.setenv("PYTHIA_STORAGE_INTEGRITY_KEY_HEX", "ab" * 32)
    monkeypatch.setenv("PYTHIA_STORAGE_CUSTODY_KEY_HEX", "cd" * 32)
    monkeypatch.setenv("PYTHIA_STORAGE_TENANT", "!!!")
    with pytest.raises(RuntimeError, match="sanitizes to empty"):
        MiningStorageRecorder.from_env()


def test_restart_recovers_event_identity_and_requires_fresh_stratum(tmp_path):
    """No duplicate replay; old proof parents cannot authorise a new pool write."""
    from types import SimpleNamespace
    from chronus.mla1517.mining.storage_recorder import M3StorageError

    store, custody, tenant_id = _plane(tmp_path)
    root = _short_root()
    ledger = CausalLedger()
    recorder = MiningStorageRecorder(store.files, tenant_id, root, strict=True)
    ledger.set_observer(recorder.observe, fail_closed=True)
    coord = CausalCoordinate(
        pool_session_id="real-session-1",
        generation=1,
        job_fingerprint="fingerprint-1",
        job_id="job-1",
        plan_id="plan-1",
        lease_id="lease-1",
        execution_id="exec-1",
    )
    job_event = ledger.record("identity_bound", coord, job_id="job-1", clean_jobs=True)
    ledger.record("plan_created", coord, window=32)
    ledger.record("execution_started", coord, extranonce2="00")
    ledger.record("candidate_found", coord, nonce=42)
    rows_before = store._db.execute(
        "SELECT COUNT(*) FROM mining_lifecycle WHERE tenant_id=?", (tenant_id,),
    ).fetchone()[0]
    store.close()
    custody.close()

    custody2 = TheseusFileCustody(tmp_path / "custody", hmac_key=CUSTODY_KEY)
    store2 = OntologyStore(tmp_path / "store.db", INTEGRITY_KEY, custody=custody2)
    try:
        recovered = MiningStorageRecorder(store2.files, tenant_id, root, strict=True)
        report = recovered.recover()
        assert report["records"] == rows_before
        assert report["replayable_events"] >= 4
        # Reprocessing the *exact* mirrored event must not add a new row.
        recovered.observe(job_event)
        assert store2._db.execute(
            "SELECT COUNT(*) FROM mining_lifecycle WHERE tenant_id=?", (tenant_id,),
        ).fetchone()[0] == rows_before
        with pytest.raises(M3StorageError, match="fresh Stratum identity"):
            recovered.persist_verified_proof(
                context={"job_id": "job-1", "generation": 1},
                proof=SimpleNamespace(
                    nonce=42, digest=b"\x11" * 32, target=(1 << 256) - 1,
                ),
                authorization_evidence_id="old-authorisation",
                authorization_version_id="fv-old",
                policy_version="old-policy",
            )
        # A new session never inherits the previous session's candidate/proof.
        fresh = CausalCoordinate(pool_session_id="real-session-2", generation=2, job_id="job-2")
        recovered.observe(
            CausalEvent(1, 1000.0, "identity_bound", fresh, {"job_id": "job-2"}),
        )
        assert set(recovered.snapshot()["heads"]) == {"job"}
        assert recovered.health(reconcile=True)["healthy"] is True
    finally:
        store2.close()
        custody2.close()


def test_from_env_exact_ovid_wires_transform_and_provenance(tmp_path, monkeypatch):
    """OVID may be explicitly composed; every raw source remains in THESEUS."""
    monkeypatch.setenv("PYTHIA_STORAGE_DB", str(tmp_path / "store.db"))
    monkeypatch.setenv("PYTHIA_STORAGE_ROOT", str(tmp_path / "objects"))
    monkeypatch.setenv("PYTHIA_STORAGE_CUSTODY_ROOT", str(tmp_path / "custody"))
    monkeypatch.setenv("PYTHIA_STORAGE_INTEGRITY_KEY_HEX", "ab" * 32)
    monkeypatch.setenv("PYTHIA_STORAGE_CUSTODY_KEY_HEX", "cd" * 32)
    monkeypatch.setenv("PYTHIA_STORAGE_TENANT", "ovid-recovery-test")
    monkeypatch.setenv("PYTHIA_STORAGE_OVID_EXACT", "true")
    rec = MiningStorageRecorder.from_env(worker="ovid-worker")
    assert rec is not None and rec.transform_plane is not None
    try:
        rec.observe(
            CausalEvent(
                1, 1.0, "identity_bound",
                CausalCoordinate(pool_session_id="session", generation=1, job_id="job"),
                {"job_id": "job"},
                software_revision="test-revision",
            ),
        )
        transform_rows = rec._store._db.execute(
            "SELECT fv.exactness,fv.transform_contract FROM file_versions fv "
            "JOIN file_objects fo ON fo.tenant_id=fv.tenant_id "
            "AND fo.file_object_id=fv.file_object_id "
            "WHERE fv.tenant_id=? AND fo.file_class='transform'",
            (rec.tenant_id,),
        ).fetchall()
        assert transform_rows and all(row["exactness"] == "EXACT" for row in transform_rows)
        receipt_row = rec._store._db.execute(
            "SELECT fv.producer_version,fp.provenance_json FROM file_versions fv "
            "JOIN file_objects fo ON fo.tenant_id=fv.tenant_id "
            "AND fo.file_object_id=fv.file_object_id "
            "JOIN file_provenance fp ON fp.tenant_id=fv.tenant_id "
            "AND fp.file_version_id=fv.file_version_id "
            "WHERE fv.tenant_id=? AND fo.logical_name LIKE 'receipt-%'",
            (rec.tenant_id,),
        ).fetchone()
        assert receipt_row["producer_version"] == "test-revision"
        provenance = json.loads(receipt_row["provenance_json"])
        assert provenance["correlation_ids"]["pool_session_id"] == "session"
        assert provenance["source_ids"]
        assert rec.health(reconcile=True)["healthy"] is True
    finally:
        rec._store.close()


def test_strict_from_env_rejects_unknown_tenant(tmp_path, monkeypatch):
    """Strict mode must not silently register a new tenant with huge quotas."""
    from chronus.mla1517.mining.storage_recorder import M3StorageError

    monkeypatch.setenv("PYTHIA_STORAGE_DB", str(tmp_path / "store.db"))
    monkeypatch.setenv("PYTHIA_STORAGE_ROOT", str(tmp_path / "objects"))
    monkeypatch.setenv("PYTHIA_STORAGE_CUSTODY_ROOT", str(tmp_path / "custody"))
    monkeypatch.setenv("PYTHIA_STORAGE_INTEGRITY_KEY_HEX", "ab" * 32)
    monkeypatch.setenv("PYTHIA_STORAGE_CUSTODY_KEY_HEX", "cd" * 32)
    monkeypatch.setenv("PYTHIA_STORAGE_TENANT", "unapproved")
    with pytest.raises(M3StorageError, match="unknown tenant"):
        MiningStorageRecorder.from_env(strict=True)


def test_retry_after_partial_custody_write_is_idempotent(tmp_path, monkeypatch):
    """A crash after chain commit but before receipt must not duplicate a job."""
    from chronus.mla1517.mining.storage_recorder import M3StorageError

    store, custody, tenant_id = _plane(tmp_path)
    recorder = MiningStorageRecorder(store.files, tenant_id, _short_root(), strict=True)
    event = CausalEvent(
        1, 100.0, "identity_bound",
        CausalCoordinate(pool_session_id="pool", generation=1, job_id="job"),
        {"job_id": "job"},
    )
    original = recorder._receipt

    def failed_receipt(*args, **kwargs):
        raise RuntimeError("injected after mining custody commit")

    monkeypatch.setattr(recorder, "_receipt", failed_receipt)
    with pytest.raises(M3StorageError, match="injected"):
        recorder.observe(event)
    count = store._db.execute(
        "SELECT COUNT(*) FROM mining_lifecycle WHERE tenant_id=?", (tenant_id,),
    ).fetchone()[0]
    assert count == 1
    monkeypatch.setattr(recorder, "_receipt", original)
    recorder.observe(event)
    assert store._db.execute(
        "SELECT COUNT(*) FROM mining_lifecycle WHERE tenant_id=?", (tenant_id,),
    ).fetchone()[0] == count
    assert recorder.receipts
    store.close()
    custody.close()


def test_mining_idempotency_conflict_refuses_divergent_payload(tmp_path):
    """One causal identity must not be used to rewrite different mining truth."""
    from hyba_db.models import IntegrityFailure

    store, custody, tenant_id = _plane(tmp_path)
    try:
        first = store.files.record_mining(
            tenant_id, "job", {"job_id": "job-a"}, idempotency_key="causal-key"
        )
        assert store.files.record_mining(
            tenant_id, "job", {"job_id": "job-a"}, idempotency_key="causal-key"
        ) == first
        with pytest.raises(IntegrityFailure, match="idempotency"):
            store.files.record_mining(
                tenant_id, "job", {"job_id": "job-b"}, idempotency_key="causal-key"
            )
    finally:
        store.close()
        custody.close()
