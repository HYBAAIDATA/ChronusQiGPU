from __future__ import annotations

from pathlib import Path

import pytest

from startup_contract import (
    AppendOnlyAudit,
    ConfigConflict,
    StateViolation,
    StartupConfigError,
    WorkerRecord,
    resolve_stratum_identity,
    validate_worker_identity,
)


def test_worker_state_lattice_and_audit(tmp_path):
    audit = AppendOnlyAudit(tmp_path / "BOOT_AUDIT.log")
    worker = WorkerRecord("agentic-mining", "mining_runtime.py", "starting")
    worker.transition("ready", audit, "heartbeat_received")
    worker.transition("running", audit, "ready_evidence")
    worker.transition("restarting", audit, "worker_exit")
    worker.transition("starting", audit, "bounded_retry")
    assert worker.public()["state"] == "starting"
    assert len((tmp_path / "BOOT_AUDIT.log").read_text().splitlines()) == 4
    with pytest.raises(StateViolation):
        worker.transition("stopped", audit, "illegal")


def test_stratum_alias_conflict_is_fail_closed(monkeypatch):
    monkeypatch.setenv("MLA1517_STRATUM_USER", "canonical.worker")
    monkeypatch.setenv("MLA1517_STRATUM_PASSWORD", "secret")
    monkeypatch.setenv("MLA1517_BRAIINS_ENDPOINT", "stratum.braiins.com:3333")
    monkeypatch.setenv("PYTHIA_STRATUM_WORKER", "different.worker")
    with pytest.raises(ConfigConflict):
        resolve_stratum_identity()


def test_identity_public_view_contains_no_password(monkeypatch):
    monkeypatch.setenv("MLA1517_STRATUM_USER", "canonical.worker")
    monkeypatch.setenv("MLA1517_STRATUM_PASSWORD", "secret-value")
    monkeypatch.setenv("MLA1517_BRAIINS_ENDPOINT", "stratum.braiins.com:3333")
    monkeypatch.delenv("PYTHIA_STRATUM_WORKER", raising=False)
    monkeypatch.delenv("PYTHIA_STRATUM_PASSWORD", raising=False)
    identity = resolve_stratum_identity()
    public = identity.public()
    assert public["user_redacted"] == "ca***"
    assert "secret-value" not in str(public)
    assert len(public["identity_commit"]) == 64


@pytest.mark.parametrize(
    "worker",
    ["account.worker", "YOUR_WORKER", "PYTHIA.001", "worker", "test.worker"],
)
def test_placeholder_worker_identities_fail_closed(worker):
    with pytest.raises(StartupConfigError, match="real pool worker identity"):
        validate_worker_identity(worker)


def test_real_worker_identity_is_preserved():
    assert validate_worker_identity("actual-account.rig-01") == "actual-account.rig-01"


def test_epoch_change_resets_sequence_without_regression(tmp_path, monkeypatch):
    from worker_lifecycle import HeartbeatEmitter, HeartbeatReader
    monkeypatch.setenv("PYTHIA_IDENTITY_HMAC_SECRET", "11" * 32)
    monkeypatch.setenv("PYTHIA_WORKER_HEARTBEAT_DIR", str(tmp_path))
    with HeartbeatEmitter("epoch-worker", interval=100.0):
        reader = HeartbeatReader("epoch-worker")
        assert reader.poll()["kind"] == "fresh"
        assert reader.poll()["kind"] == "stale"
        reader.last_seq += 100
    with HeartbeatEmitter("epoch-worker", interval=100.0):
        evidence = reader.poll()
        assert evidence["kind"] == "epoch_change"
        assert evidence["seq"] == 1


def test_authenticated_heartbeat_rejects_tampering(tmp_path, monkeypatch):
    from worker_lifecycle import HeartbeatEmitter, HeartbeatReader
    monkeypatch.setenv("PYTHIA_WORKER_HEARTBEAT_DIR", str(tmp_path))
    monkeypatch.setenv("PYTHIA_IDENTITY_HMAC_SECRET", "22" * 32)
    with HeartbeatEmitter("auth-worker", interval=100.0):
        reader = HeartbeatReader("auth-worker")
        assert reader.poll()["kind"] == "fresh"
        path = tmp_path / "auth-worker.bin"
        raw = bytearray(path.read_bytes())
        raw[-1] ^= 0x01
        path.write_bytes(raw)
        evidence = reader.poll()
        assert evidence["kind"] == "malformed"
        assert evidence["error"] == "hmac_invalid"


def test_restart_budget_terminal_state_is_explicit():
    import control_api
    source = Path(control_api.__file__).read_text(encoding="utf-8")
    assert control_api._MAX_RESTARTS_WINDOW == 5
    assert "RestartBudgetExhausted" in source and "failed" in source
