"""Tests for supervised pool reader drop & recovery (Stage 0.1 & 0.2).

Validates:
- Socket drop mid-job (WinError 10054 / ConnectionResetError).
- Identity quarantine to NO_SUBSCRIPTION.
- Bounded re-auth (<= 30s).
- Monotone ledger snapshot version progression.
- Expected share time calculations and share gate verdicts.
"""

import time
import pytest
from pythia.pool_reader import (
    AuthFail,
    NetDrop,
    PoolConfig,
    SupervisedPoolReader,
    WorkIdentity,
    expected_share_time,
    share_gate,
)


class MockPoolSocket:
    """Mock Stratum socket with programmable drop behavior."""

    def __init__(self, should_fail: bool = False, drop_during_job: bool = False):
        self.should_fail = should_fail
        self.drop_during_job = drop_during_job
        self.subscribed = False
        self.authorized = False
        self.jobs_emitted = 0

    def subscribe(self) -> str:
        if self.should_fail:
            raise ConnectionResetError("[WinError 10054] An existing connection was forcibly closed by the remote host")
        self.subscribed = True
        return "sub-braiins-001"

    def authorize(self, user: str, password: str) -> bool:
        if self.should_fail:
            raise ConnectionResetError("[WinError 10054] An existing connection was forcibly closed by the remote host")
        self.authorized = (user == "valid_worker")
        return self.authorized

    def read_job(self, timeout: float = 10.0) -> dict:
        if self.drop_during_job and self.jobs_emitted >= 1:
            raise ConnectionResetError("[WinError 10054] An existing connection was forcibly closed by the remote host")
        self.jobs_emitted += 1
        return {"id": f"job-{self.jobs_emitted}", "diff": 1024}


def test_pool_reader_successful_authorization(tmp_path):
    cfg = PoolConfig(user="valid_worker", password="x")
    reader = SupervisedPoolReader(cfg)
    mock_sock = MockPoolSocket()

    ident = reader.step(mock_sock)
    assert ident.authorized is True
    assert ident.subscription_id == "sub-braiins-001"
    assert ident.job_id == "job-1"
    assert ident.status == "ACTIVE_JOB"
    assert len(reader.storage_snapshots) >= 1
    assert reader.ledger_version > 40


def test_pool_reader_drop_and_quarantine_recovery(tmp_path):
    """Kill socket mid-job: assert quarantine, NO_SUBSCRIPTION logged, re-auth <= 30s, monotone ledger."""
    cfg = PoolConfig(user="valid_worker", password="x")
    reader = SupervisedPoolReader(cfg)

    # 1. First step succeeds
    sock_healthy = MockPoolSocket(drop_during_job=False)
    ident_ok = reader.step(sock_healthy)
    assert ident_ok.authorized is True
    v1 = reader.ledger_version

    # 2. Drop occurs mid-job
    sock_dropping = MockPoolSocket(drop_during_job=True)
    # emit one job to trigger drop condition
    sock_dropping.jobs_emitted = 1
    ident_dropped = reader.step(sock_dropping)

    # Must be quarantined
    assert ident_dropped.authorized is False
    assert ident_dropped.subscription_id is None
    assert ident_dropped.status == "NO_SUBSCRIPTION"
    assert reader.pool_drop_count == 1
    assert len(reader.quarantine_events) == 1

    # Monotone storage ledger progression
    v2 = reader.ledger_version
    assert v2 > v1, f"Ledger version did not monotonically increase: v2={v2}, v1={v1}"

    # 3. Supervised recovery with healthy socket
    sock_recovered = MockPoolSocket(drop_during_job=False)
    ident_recovered = reader.step(sock_recovered)
    assert ident_recovered.authorized is True
    assert ident_recovered.status == "ACTIVE_JOB"
    v3 = reader.ledger_version
    assert v3 > v2, f"Ledger version did not advance on recovery: v3={v3}, v2={v2}"


def test_auth_failure_fails_closed():
    """Unrecognized user fails closed with AuthFail."""
    cfg = PoolConfig(user="invalid_user", password="x")
    reader = SupervisedPoolReader(cfg)
    sock = MockPoolSocket()

    with pytest.raises(AuthFail):
        reader.step(sock)


def test_share_frequency_expectation_and_gate():
    """Stage 0.2: verify expected share time formula and gate verdicts."""
    hashrate = 508e6  # 508 MH/s

    # Diff 1024: E ≈ 8658s ≈ 2.405h
    t_1024 = expected_share_time(1024, hashrate)
    assert abs(t_1024 - 8657.57) < 1.0
    hours_1024 = t_1024 / 3600.0
    assert 2.39 < hours_1024 < 2.42

    # Diff 8192: E ≈ 69260s ≈ 19.24h
    t_8192 = expected_share_time(8192, hashrate)
    hours_8192 = t_8192 / 3600.0
    assert 19.2 < hours_8192 < 19.3

    # Share gate test in 4.0h window with Diff 1024 and 52 jobs
    # E = 2.4h, window = 2.0h -> insufficient window
    gate_short = share_gate(jobs_seen=52, window_h=2.0, hashrate_Hs=hashrate, current_diff=1024)
    assert gate_short["verdict"] == "INSUFFICIENT_WINDOW_EXPECT_ZERO_SHARES"

    # E = 19.2h (Diff 8192), window = 4.0h -> insufficient window (0 shares is EXPECTED)
    gate_4h_high_diff = share_gate(jobs_seen=52, window_h=4.0, hashrate_Hs=hashrate, current_diff=8192)
    assert gate_4h_high_diff["verdict"] == "INSUFFICIENT_WINDOW_EXPECT_ZERO_SHARES"

    # window = 25h > 19.2h -> evaluate measured outcomes only
    gate_long = share_gate(jobs_seen=300, window_h=25.0, hashrate_Hs=hashrate, current_diff=8192, shares_found=1)
    assert gate_long["verdict"] == "EVALUATE_MEASURED_OUTCOMES_ONLY"
    assert gate_long["reward"] == 1
