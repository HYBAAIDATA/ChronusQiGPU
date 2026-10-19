"""Tests for Salamander Autonomic Mining Healer and Healer Outranks Optimiser Law.

Verifies:
1. test_salamander_heals_stale_identity: Recovery from simulated mid-session IDENTITY_MISMATCH.
2. test_healer_outranks_optimiser: Optimizer locks immediately upon healing; trials abort; scaling is halted.
3. test_salamander_fail_closed: Unresolvable degradation fails closed without fabricating shares or false success.
4. test_seeds_and_evidence_ledger_integrity: SHA256 evidence chain verification across seeds [1337, 42, 2026].
"""

from __future__ import annotations

import copy
import time
import pytest
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from chronus.mla1517.mining.closed_loop import ClosedLoopOptimizer
from chronus.mla1517.mining.coordinator import IntelligentPoolCoordinator
from chronus.mla1517.mining.recovery_authority import RecoveryGovernor
from chronus.mla1517.mining.search_plan import WorkIdentity, CompletionState, EvidenceClass
from manifold_pool_coordinator import PoolEndpoint
from salamander.mining_healer import (
    HealDiagnosis,
    HealObservation,
    HealerState,
    SalamanderMiningHealer,
)
from salamander.runtime import DurableEvidenceLedger, FaultClass


@dataclass
class MockStratumJob:
    job_id: str
    target: int
    generation_id: int = 1
    fingerprint: str = "fp_mock_job_001"
    target_generation: int = 1
    clean_jobs: bool = True
    received_at: float = 1000.0
    ntime: str = "65abcdef"
    nbits: str = "1d00ffff"
    prevhash: str = "00" * 32
    coinb1: str = "01000000"
    coinb2: str = "ffffffff"
    merkle_branch: tuple = ()
    version: str = "20000000"
    extranonce1: str = "01020304"
    extranonce2_size: int = 4


class MockProofAdapter:
    def __init__(self, job: MockStratumJob) -> None:
        self.subscription = SimpleNamespace(extranonce1="01020304", extranonce2_size=4)
        self.current_job: MockStratumJob | None = job

    def build_header(self, job_id: str, extranonce2: str, ntime: str, nonce: int) -> bytes:
        return b"\x00" * 80


class MockRuntimeState:
    def __init__(self, job: MockStratumJob, session_id: str = "sess_001") -> None:
        self.session_id = session_id
        self.current_job: MockStratumJob | None = job
        self.ready = True


class MockStratumClient:
    def __init__(self, job: MockStratumJob) -> None:
        self.proof_adapter = MockProofAdapter(copy.copy(job))
        self.runtime_state = MockRuntimeState(copy.copy(job))


@pytest.fixture
def mock_coordinator(tmp_path: Path):
    """Construct an IntelligentPoolCoordinator wired with mock client and Salamander healer."""
    endpoint = PoolEndpoint("127.0.0.1", 3333, "mock-pool")
    healer = SalamanderMiningHealer(evidence_path=tmp_path / "salamander_evidence.jsonl")
    coord = IntelligentPoolCoordinator(
        [endpoint],
        username="PYTHIA.MOCK",
        password="x",
        submit_enabled=False,
        salamander_healer=healer,
    )
    initial_job = MockStratumJob(job_id="job_01", target=0x000000000000FFFF)
    coord.client = MockStratumClient(initial_job)
    return coord


def test_salamander_heals_stale_identity(mock_coordinator):
    """Test 1: Simulated mid-session IDENTITY_MISMATCH healed via canonical 7-step loop.

    Steps:
    1. Verify initial identity resolves cleanly.
    2. Inject mid-session mismatch: runtime_state gets job_02, but proof_adapter stays on job_01.
    3. Assert _resolve_work_identity() returns (None, 'IDENTITY_MISMATCH').
    4. Call _refresh_work_identity(): Salamander healer detects, locks optimizer, resyncs adapter,
       verifies recovery, logs ExecutionRecord, appends EvidenceLedger, and unlocks optimizer.
    5. Assert healed WorkIdentity returned with job_id == 'job_02'.
    6. Assert consensus truth preserved and optimizer unlocked.
    """
    coord = mock_coordinator

    # 1. Initial resolution succeeds
    ident, reason = coord._resolve_work_identity()
    assert ident is not None
    assert ident.job_id == "job_01"
    assert reason is None

    # 2. Inject mid-session IDENTITY_MISMATCH
    new_job = MockStratumJob(
        job_id="job_02",
        target=0x000000000000FFFF,
        generation_id=2,
        fingerprint="fp_mock_job_002",
    )
    coord.client.runtime_state.current_job = new_job
    # Note: coord.client.proof_adapter.current_job intentionally remains job_01

    # 3. Direct resolve observes mismatch
    mismatch_ident, mismatch_reason = coord._resolve_work_identity()
    assert mismatch_ident is None
    assert mismatch_reason == "IDENTITY_MISMATCH"

    # 4. _refresh_work_identity triggers Salamander autonomic healer
    healer = coord.salamander_healer
    assert healer is not None
    initial_heal_count = healer.heal_count

    # Execute refresh which invokes healer
    healed_ident = coord._refresh_work_identity()

    # 5. Verify successful recovery
    assert healed_ident is not None
    assert healed_ident.job_id == "job_02"
    assert healed_ident.generation == 2
    assert healed_ident.job_fingerprint == "fp_mock_job_002"

    # Verify adapter was resynchronized
    assert coord.client.proof_adapter.current_job.job_id == "job_02"

    # Verify healer audit record
    assert healer.heal_count == initial_heal_count + 1
    last_audit = healer.last_audit
    assert last_audit is not None
    assert last_audit.verified is True
    assert last_audit.fault_class == FaultClass.RECOVERABLE_DEGRADATION.value
    assert "RESYNC_PROOF_ADAPTER" in last_audit.actions_taken
    assert "LOCK_OPTIMIZER" in last_audit.actions_taken

    # Verify execution record logged with route honesty and recovery_event=True
    exec_rec = last_audit.execution_record
    assert exec_rec.recovery_event is True
    assert exec_rec.requested_route is None
    assert exec_rec.executed_route is None
    assert exec_rec.completion_state == CompletionState.COMPLETE

    # Verify optimizer unlocked after verified recovery
    assert coord.optimization.is_locked is False


def test_healer_outranks_optimiser_law():
    """Test 2: Healer outranks optimiser law.

    When optimizer is locked by healer:
    1. Active trials abort immediately with safety rollback.
    2. Propose window scaling refuses candidate expansion and returns baseline.
    3. Observe ignores candidate rates and does not mutate active window.
    4. Unlocking restores normal optimization capability.
    """
    opt = ClosedLoopOptimizer(min_samples=2, min_improvement=0.05)
    route = "intel_igpu"

    # Establish baseline
    base_window = opt.select(route=route, proposed_window=1024)
    assert base_window == 1024

    # Feed baseline observations
    opt.observe(
        route=route,
        planned_window=1024,
        completed_work=1024,
        elapsed_seconds=1.0,
        completion_state="COMPLETE",
    )
    opt.observe(
        route=route,
        planned_window=1024,
        completed_work=1024,
        elapsed_seconds=1.0,
        completion_state="COMPLETE",
    )

    # Start a candidate trial
    candidate_window = opt.select(route=route, proposed_window=2048)
    assert candidate_window == 2048
    assert opt.trial is not None
    assert opt.trial["candidate"] == 2048

    # HEALER STEPS IN -> LOCKS OPTIMIZER
    opt.lock(reason="salamander_healer: IDENTITY_MISMATCH")
    assert opt.is_locked is True

    # Trial must be aborted and rolled back to baseline
    assert opt.trial is None
    assert opt.active[route] == 1024

    # Further selection attempts must be rejected while locked
    attempt = opt.select(route=route, proposed_window=4096)
    assert attempt == 1024  # Returns current safe baseline

    # Observation during lock must be discarded
    opt.observe(
        route=route,
        planned_window=4096,
        completed_work=4096,
        elapsed_seconds=0.5,
        completion_state="COMPLETE",
    )
    assert opt.active[route] == 1024

    # Unlocking restores normal operation
    opt.unlock()
    assert opt.is_locked is False


def test_salamander_fail_closed_on_unresolvable_state(mock_coordinator):
    """Test 3: Unresolvable degradation fails closed.

    If runtime_state has no job at all, the healer must fail closed:
    - No fabricated identity or share
    - Optimizer remains locked
    - Healer state transitions to FAILED
    """
    coord = mock_coordinator
    coord.client.runtime_state.current_job = None
    coord.client.proof_adapter.current_job = None

    healer = coord.salamander_healer
    with pytest.raises(RuntimeError, match="Autonomic healing postcondition failed"):
        healer.heal_identity_mismatch(coord)

    assert healer.state == HealerState.FAILED
    assert coord.optimization.is_locked is True


@pytest.mark.parametrize("seed", [1337, 42, 2026])
def test_seeds_and_evidence_ledger_integrity(mock_coordinator, tmp_path: Path, seed: int):
    """Test 4: Evidence ledger hash chain integrity across seeds [1337, 42, 2026]."""
    ledger_path = tmp_path / f"evidence_seed_{seed}.jsonl"
    healer = SalamanderMiningHealer(evidence_path=ledger_path)
    coord = mock_coordinator
    coord.salamander_healer = healer

    # Trigger multiple healing events
    for i in range(3):
        new_job = MockStratumJob(
            job_id=f"job_seed_{seed}_{i}",
            target=0x000000000000FFFF,
            generation_id=10 + i,
            fingerprint=f"fp_seed_{seed}_{i}",
        )
        coord.client.runtime_state.current_job = new_job
        # Mismatch
        coord.client.proof_adapter.current_job = MockStratumJob(
            job_id="stale_job", target=0x000000000000FFFF
        )

        healed = coord._refresh_work_identity()
        assert healed is not None
        assert healed.job_id == f"job_seed_{seed}_{i}"

    # Verify durable ledger
    assert len(healer.ledger.records) == 3
    assert healer.ledger.verify() is True
    assert healer.ledger.head != "0" * 64
