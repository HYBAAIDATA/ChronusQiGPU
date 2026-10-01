"""Owner-B Salamander contracts: real fault->repair->verify-recovery loop.

The native seqlock TelemetryReader needs libmla1517_mmio (absent on this
host), so a scripted reader feeds ABI-shaped frames into the real engine:
sense -> FaultBucket -> McLaren/Michie -> staged CSR commit -> mode report.
"Verify recovery" means a recovery_id stays open while repair actions flow
and is only closed by a later observation with nothing left to fix.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PY_DIR = REPO_ROOT / "chronus/mla1517_platform" / "python"
sys.path.insert(0, str(PY_DIR))

import salamander_control
from salamander_engine import SalamanderEngine


class _FakeBridge:
    """MMIOBridge stand-in: records staged CSRs; commit ack is scripted."""

    def __init__(self, ack: bool = True) -> None:
        self.ack = ack
        self.lane_masks: list[int] = []
        self.poly_masks: list[int] = []
        self.commit_requests = 0

    def stage_lane_mask(self, mask: int) -> None:
        self.lane_masks.append(mask)

    def stage_polyhedral_mask(self, mask: int) -> None:
        self.poly_masks.append(mask)

    def request_supervisor_commit(self) -> None:
        self.commit_requests += 1

    def supervisor_commit_ack(self) -> bool:
        return self.ack


class _ScriptedReader:
    """TelemetryReader stand-in: returns the frame the test last set."""

    def __init__(self) -> None:
        self.current: dict = {}

    def read(self) -> dict:
        return self.current


def _faults(lane: int, count: int) -> list[int]:
    faults = [0] * salamander_control.LANES
    faults[lane] = count
    return faults


def _engine(tmp_path, monkeypatch, *, bridge: _FakeBridge, failover=None):
    monkeypatch.setenv("MLA1517_SALAMANDER_POLICY", "none")
    monkeypatch.setenv("MLA1517_PRIME_DB_CURSORS", str(tmp_path / "no_cursor_file"))
    engine = SalamanderEngine(
        bridge,
        telemetry_path=tmp_path / "telemetry",
        data_dir=tmp_path,
        enabled=True,
        failover=failover,
        governance_enabled=False,
    )
    engine.telemetry_reader = _ScriptedReader()
    reports: list[dict] = []
    engine.mode_reporter = lambda payload: reports.append(dict(payload)) or True
    return engine, engine.telemetry_reader, reports


def test_fault_retire_then_new_observation_verifies_recovery(tmp_path, monkeypatch):
    bridge = _FakeBridge(ack=True)
    engine, reader, reports = _engine(tmp_path, monkeypatch, bridge=bridge)

    reader.current = {"cassini_faults": _faults(5, 4), "total_tests": 1_000}
    step1 = engine.step(now_ms=1_000)

    assert step1["actions"] == ["retire:5"]
    assert step1["mode"] == "RECOVERING"
    assert step1["active_lanes"] == 31
    # Retire is a real staged+acked CSR transaction on lane 5's bit.
    assert bridge.lane_masks == [0xFFFFFFFF & ~(1 << 5)]
    assert bridge.commit_requests == 1
    assert engine.recovery_id == step1["recovery_id"]
    assert reports[-1]["mode"] == "RECOVERING"
    assert reports[-1]["recovery_id"] == engine.recovery_id

    # A fresh observation with nothing left to fix verifies recovery:
    # NORMAL is reported carrying the same recovery_id, which then closes.
    reader.current = {"cassini_faults": _faults(5, 4), "total_tests": 1_100}
    step2 = engine.step(now_ms=1_050)

    assert step2["actions"] == []
    assert step2["mode"] == "NORMAL"
    assert reports[-1]["mode"] == "NORMAL"
    assert reports[-1]["recovery_id"] == step1["recovery_id"]
    assert engine.recovery_id is None


def test_commit_ack_false_blocks_repair(tmp_path, monkeypatch):
    bridge = _FakeBridge(ack=False)
    engine, reader, _reports = _engine(tmp_path, monkeypatch, bridge=bridge)

    reader.current = {"cassini_faults": _faults(7, 9), "total_tests": 1_000}
    step = engine.step(now_ms=2_000)

    # Ack-gating: an unacknowledged commit must not count as a repair.
    assert step["actions"] == []
    assert step["active_lanes"] == 32
    assert engine.mclaren.state.active[7] is True
    assert engine.recovery_id is None


def test_probationary_readmit_restores_lane(tmp_path, monkeypatch):
    bridge = _FakeBridge(ack=True)
    engine, reader, reports = _engine(tmp_path, monkeypatch, bridge=bridge)

    reader.current = {"cassini_faults": _faults(3, 6), "total_tests": 5_000}
    engine.step(now_ms=1_000)
    engine.step(now_ms=1_050)  # quiet observation closes recovery #1
    assert engine.recovery_id is None
    assert engine.mclaren.state.active[3] is False

    # Probation window must elapse before the lane is even self-tested.
    probation_end = 1_000 + salamander_control.PROBATION_MS
    reader.current = {"cassini_faults": _faults(3, 6), "total_tests": 6_000}
    steps = [
        engine.step(now_ms=tick)
        for tick in (probation_end, probation_end + 50, probation_end + 100)
    ]
    # Third passing self-test commits the readmit (READMIT_PASSES == 3).
    step = steps[2]
    assert steps[0]["actions"] == [] and steps[1]["actions"] == []

    assert step["actions"] == ["readmit:3"]
    assert step["mode"] == "RECOVERING"
    assert engine.mclaren.state.active[3] is True
    # Final staged mask restored lane 3's bit.
    assert bridge.lane_masks[-1] & (1 << 3)
    assert step["active_lanes"] == 32

    step_after = engine.step(now_ms=probation_end + 150)
    assert step_after["actions"] == []
    assert step_after["mode"] == "NORMAL"
    assert reports[-1]["mode"] == "NORMAL"
    assert engine.recovery_id is None


def test_faulting_lane_fails_probation_self_test(tmp_path, monkeypatch):
    """The probation self-test is a real observation, not a lambda-true:
    a lane whose cumulative fault counter keeps growing while quarantined
    must not be readmitted; only consecutive fault-free ticks count."""
    bridge = _FakeBridge(ack=True)
    engine, reader, _reports = _engine(tmp_path, monkeypatch, bridge=bridge)

    reader.current = {"cassini_faults": _faults(3, 6), "total_tests": 5_000}
    engine.step(now_ms=1_000)
    engine.step(now_ms=1_050)  # quiet observation closes recovery #1
    assert engine.mclaren.state.active[3] is False

    probation_end = 1_000 + salamander_control.PROBATION_MS
    # First probation tick: counter still flat -> observed pass 1.
    reader.current = {"cassini_faults": _faults(3, 6), "total_tests": 6_000}
    step = engine.step(now_ms=probation_end)
    assert step["actions"] == []
    assert engine.mclaren.state.passes[3] == 1

    # The counter grows on the next observation -> fail, passes reset,
    # probation restarts (quarantined_since moves to this tick).
    reader.current = {"cassini_faults": _faults(3, 7), "total_tests": 6_100}
    step = engine.step(now_ms=probation_end + 50)
    assert "readmit:3" not in step["actions"]
    assert engine.mclaren.state.passes[3] == 0
    restart = engine.mclaren.state.quarantined_since[3] == probation_end + 50
    assert restart

    # It grows again on the next probation observation -> fails again.
    reader.current = {"cassini_faults": _faults(3, 8), "total_tests": 6_200}
    engine.step(now_ms=probation_end + 50 + salamander_control.PROBATION_MS)
    assert engine.mclaren.state.passes[3] == 0

    # Three consecutive fault-free observations then readmit.
    ticks = (
        probation_end + 50 + 2 * salamander_control.PROBATION_MS,
        probation_end + 100 + 2 * salamander_control.PROBATION_MS,
        probation_end + 150 + 2 * salamander_control.PROBATION_MS,
    )
    steps = []
    for tick in ticks:
        reader.current = {"cassini_faults": _faults(3, 8), "total_tests": 6_300}
        steps.append(engine.step(now_ms=tick))
    assert steps[2]["actions"] == ["readmit:3"]
    assert engine.mclaren.state.active[3] is True


def test_stratum_drops_trigger_failover_once(tmp_path, monkeypatch):
    calls: list[str] = []
    bridge = _FakeBridge(ack=True)
    engine, reader, _reports = _engine(
        tmp_path, monkeypatch, bridge=bridge, failover=lambda: calls.append("f") or True
    )

    reader.current = {"stratum_drops": 4, "total_tests": 2_000}
    step = engine.step(now_ms=10_000)

    assert "request_failover" in step["actions"]
    assert calls == ["f"]
    assert engine.failover_state.pending is False

    # Drops persist but cooldown suppresses a second switch.
    step2 = engine.step(now_ms=10_050)
    assert calls == ["f"]
    assert "request_failover" not in step2["actions"]

    # Edge-triggered: the same cumulative count past cooldown does NOT
    # re-fire — failover needs >3 NEW drops since the last switch.
    reader.current = {"stratum_drops": 4, "total_tests": 2_100}
    step3 = engine.step(now_ms=10_000 + salamander_control.FAILOVER_COOLDOWN_MS + 1)
    assert calls == ["f"]
    assert "request_failover" not in step3["actions"]

    reader.current = {"stratum_drops": 8, "total_tests": 2_200}
    step4 = engine.step(now_ms=10_000 + salamander_control.FAILOVER_COOLDOWN_MS + 2)
    assert calls == ["f", "f"]
    assert "request_failover" in step4["actions"]

    # A failed switch is cancelled, not latched.
    engine2 = SalamanderEngine(
        bridge,
        telemetry_path=tmp_path / "t2",
        data_dir=tmp_path,
        enabled=True,
        failover=lambda: False,
        governance_enabled=False,
    )
    engine2.telemetry_reader = _ScriptedReader()
    engine2.mode_reporter = lambda payload: True
    reader2 = engine2.telemetry_reader
    reader2.current = {"stratum_drops": 4}
    step3 = engine2.step(now_ms=20_000)
    assert "request_failover" not in step3["actions"]
    assert engine2.failover_state.pending is False


def test_min_lane_floor_engages_degraded_not_retire(tmp_path, monkeypatch):
    bridge = _FakeBridge(ack=True)
    engine, reader, _reports = _engine(tmp_path, monkeypatch, bridge=bridge)
    # Pre-quarantine 8 lanes so only MIN_LANES remain active.
    for lane in range(8):
        engine.mclaren.state.active[lane] = False
        engine.mclaren.state.quarantined_since[lane] = 0
        engine.fault_bucket.armed[lane] = False
    assert sum(engine.mclaren.state.active) == salamander_control.MIN_LANES

    reader.current = {"cassini_faults": _faults(20, 8), "total_tests": 9_000}
    step = engine.step(now_ms=30_000)

    assert step["actions"] == ["degraded_mode"]
    assert engine.mclaren.degraded is True
    assert engine.mclaren.state.active[20] is True  # lane NOT retired below floor
    assert step["mode"] == "RECOVERING"

    # While the fault sits armed at the floor the action re-fires each tick.
    still_faulted = engine.step(now_ms=30_050)
    assert still_faulted["actions"] == ["degraded_mode"]
    assert still_faulted["mode"] == "RECOVERING"

    # Once the fault decays below trip the observation reports honest
    # DE_RATE (degraded persists) rather than NORMAL.
    quiet = engine.step(now_ms=30_000 + salamander_control.FAULT_TAU_MS)
    assert quiet["actions"] == []
    assert quiet["mode"] == "DE_RATE"


def test_disabled_engine_senses_without_acting(tmp_path, monkeypatch):
    monkeypatch.setenv("MLA1517_PRIME_DB_CURSORS", str(tmp_path / "none"))
    engine = SalamanderEngine(
        _FakeBridge(),
        telemetry_path=tmp_path / "t",
        data_dir=tmp_path,
        enabled=False,
        governance_enabled=False,
    )
    engine.telemetry_reader = _ScriptedReader()
    engine.telemetry_reader.current = {"cassini_faults": _faults(1, 9)}
    step = engine.step(now_ms=1_000)
    assert step["enabled"] is False
    assert step["actions"] == []
    assert step["state"]["faults"][1] == 9
