from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from chronus.mla1517.mining.causal import CausalCoordinate, CausalLedger
from chronus.mla1517.mining.geodesic_support import PythiaProductionMiningCoordinator
from chronus.mla1517.mining.m3_coordinator import M3PythiaProductionMiningCoordinator
from chronus.mla1517.mining.search_plan import PoolOutcome
from chronus.mla1517.mining.storage_recorder import M3StorageError, MiningStorageRecorder
from chronus.mla1517.mining.stratum_adapter import StaleJobError
from hyba_db.models import Quota
from hyba_db.store import OntologyStore
from hyba_db.theseus_custody import TheseusFileCustody

INTEGRITY_KEY = b"m3-closure-integrity-key-0123456789"
CUSTODY_KEY = b"m3-closure-custody-key-012345678901"


def _plane(tmp_path: Path):
    custody = TheseusFileCustody(tmp_path / "custody", hmac_key=CUSTODY_KEY)
    store = OntologyStore(tmp_path / "store.db", INTEGRITY_KEY, custody=custody)
    client = store.provision_client("m3-closure", Quota(100_000, 100_000_000))
    recorder = MiningStorageRecorder(
        store.files,
        client.tenant_id,
        tmp_path / "objects",
        strict=True,
    )
    recorder._store = store
    return store, custody, recorder


def _seed_candidate(ledger: CausalLedger) -> CausalCoordinate:
    coord = CausalCoordinate(
        pool_session_id="session-1",
        generation=7,
        job_fingerprint="fp-1",
        job_id="job-1",
        plan_id="plan-1",
        lease_id="lease-1",
        execution_id="execution-1",
        candidate_id="candidate-1",
    )
    ledger.record("identity_bound", coord, job_id="job-1", clean_jobs=True)
    ledger.record("plan_created", coord, window=64)
    ledger.record("execution_started", coord, extranonce2="00")
    ledger.record("candidate_found", coord, nonce=42)
    return coord


def test_strict_custody_failure_propagates_after_causal_event_is_retained(tmp_path):
    store, custody, recorder = _plane(tmp_path)
    ledger = CausalLedger()
    ledger.set_observer(recorder.observe, fail_closed=True)
    store.close()

    with pytest.raises(M3StorageError):
        ledger.record("identity_bound", CausalCoordinate(), job_id="job-x")

    assert ledger.observer_errors == 1
    assert ledger.events()[-1].kind == "identity_bound"
    assert recorder.errors == 1
    custody.close()


def test_strict_verified_proof_is_custodied_before_submission_record(tmp_path):
    store, custody, recorder = _plane(tmp_path)
    ledger = CausalLedger()
    ledger.set_observer(recorder.observe, fail_closed=True)
    coord = _seed_candidate(ledger)

    verdict = {
        "allowed": True,
        "reason": "ALLOWED",
        "evidence_id": "al-haras-evidence-1",
        "policy_version": "al-haras.policy.v1",
    }
    auth_version = recorder.persist_authorization(
        verdict,
        context={"job_id": "job-1", "generation": 7},
    )
    proof = SimpleNamespace(
        nonce="0000002a",
        digest=bytes.fromhex("11" * 32),
        target=(1 << 256) - 1,
    )
    proof_id, proof_version = recorder.persist_verified_proof(
        context={
            "job_id": "job-1",
            "generation": 7,
            "pool_session_id": "session-1",
        },
        proof=proof,
        authorization_evidence_id=verdict["evidence_id"],
        authorization_version_id=auth_version,
        policy_version=verdict["policy_version"],
    )

    ledger.record(
        "submission_sent",
        coord.extend(submission_id="submission-1"),
        job_id="job-1",
        block_hash=proof.digest[::-1].hex(),
    )

    rows = store._db.execute(
        "SELECT kind, parent_ids_json FROM mining_lifecycle WHERE tenant_id=?",
        (recorder.tenant_id,),
    ).fetchall()
    kinds = [row["kind"] for row in rows]
    assert kinds.count("verified_proof") == 1
    assert kinds.count("submission") == 1
    assert recorder.receipts[proof_id] == proof_version
    assert recorder.health(reconcile=True)["healthy"] is True
    store.close()
    custody.close()


def test_strict_verified_proof_refuses_missing_candidate_parent(tmp_path):
    store, custody, recorder = _plane(tmp_path)
    proof = SimpleNamespace(
        nonce="0000002a",
        digest=bytes.fromhex("22" * 32),
        target=(1 << 256) - 1,
    )
    with pytest.raises(M3StorageError, match="candidate_verification"):
        recorder.persist_verified_proof(
            context={"job_id": "job-1"},
            proof=proof,
            authorization_evidence_id="auth",
            authorization_version_id="fv-auth",
            policy_version="policy",
        )
    store.close()
    custody.close()


def test_stale_job_is_refused_without_killing_m3_coordinator():
    coord = M3PythiaProductionMiningCoordinator.__new__(M3PythiaProductionMiningCoordinator)
    coord._pending_correlation = {}
    coord._last_pool_outcome = PoolOutcome.NOT_SUBMITTED
    coord.agentic = SimpleNamespace(clear_work=lambda reason: setattr(coord, "_cleared", reason))
    coord.cycle = SimpleNamespace(try_transition=lambda *args, **kwargs: True)
    coord._precompute_wake = asyncio.Event()
    coord._work_wake = asyncio.Event()
    coord.causal = SimpleNamespace(record=lambda *args, **kwargs: None)

    with patch.object(
        PythiaProductionMiningCoordinator,
        "search_current_job",
        AsyncMock(side_effect=StaleJobError("job generation changed")),
    ):
        result = asyncio.run(coord.search_current_job())

    assert result is False
    assert coord._last_pool_outcome is PoolOutcome.STALE
    assert coord._cleared == "STALE_JOB"
