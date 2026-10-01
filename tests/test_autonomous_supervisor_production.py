"""Production wiring and evidence tests for the autonomy daemon."""

from types import SimpleNamespace

import autonomous_supervisor


class _ControlPlane:
    def __init__(self, records):
        self._records = records
        self.autostart = False
        self.restarts = 0

    def records(self):
        return list(self._records)

    def set_autostart(self, enabled):
        self.autostart = bool(enabled)

    def ensure_workers(self):
        self.restarts += 1
        self._records = [SimpleNamespace(hashrate=None, liveness=True)]


def test_builds_real_autonomy_supervisor_without_telemetry(monkeypatch):
    control = _ControlPlane([])
    monkeypatch.setattr("control_api._control_plane", lambda: control)
    monkeypatch.delenv("PYTHIA_CUOP_POWER_W", raising=False)
    daemon = autonomous_supervisor.AutonomousSupervisor(interval_s=5.0)

    daemon._build()

    status = daemon.status()
    assert daemon._supervisor is not None
    assert status["cuop"]["available"] is False
    assert status["cuop"]["evidence_class"] == "Unavailable"
    assert status["cuop"]["reason"] == "power_telemetry_unavailable"
    assert status["supervisor"]["optimiser_attached"] is False


def test_configured_power_is_not_a_measurement(monkeypatch):
    control = _ControlPlane([SimpleNamespace(hashrate=250.0, liveness=True)])
    monkeypatch.setattr("control_api._control_plane", lambda: control)
    monkeypatch.setenv("PYTHIA_CUOP_POWER_W", "12.5")
    daemon = autonomous_supervisor.AutonomousSupervisor(interval_s=5.0)

    daemon._build()

    status = daemon.status()
    assert status["cuop"]["available"] is False
    assert status["cuop"]["reason"] == "power_configured_not_measured"
    assert status["supervisor"]["optimiser_attached"] is False


def test_unmeasured_worker_hashrate_is_unavailable_not_zero(monkeypatch):
    control = _ControlPlane([SimpleNamespace(hashrate=None, liveness=True)])
    monkeypatch.setattr("control_api._control_plane", lambda: control)
    daemon = autonomous_supervisor.AutonomousSupervisor(interval_s=5.0, power_meter=lambda: 12.5)

    daemon._build()

    status = daemon.status()
    assert status["cuop"]["available"] is False
    assert status["cuop"]["reason"] == "hashrate_telemetry_unavailable"
    assert status["supervisor"]["optimiser_attached"] is False


def test_attaches_optimizer_only_with_measured_telemetry(monkeypatch):
    control = _ControlPlane([SimpleNamespace(hashrate=250.0, liveness=True)])
    monkeypatch.setattr("control_api._control_plane", lambda: control)
    daemon = autonomous_supervisor.AutonomousSupervisor(interval_s=5.0, power_meter=lambda: 12.5)

    daemon._build()

    status = daemon.status()
    assert status["cuop"]["available"] is True
    assert status["cuop"]["evidence_class"] == "Measured"
    assert status["cuop"]["reading"]["useful_ops"] == 1250.0
    assert status["supervisor"]["optimiser_attached"] is True
def test_losing_telemetry_mid_run_does_not_block_healing(monkeypatch):
    control = _ControlPlane([SimpleNamespace(hashrate=250.0, liveness=True)])
    control.autostart = True
    monkeypatch.setattr("control_api._control_plane", lambda: control)
    daemon = autonomous_supervisor.AutonomousSupervisor(interval_s=5.0, power_meter=lambda: 12.5)
    daemon._build()
    assert daemon.status()["supervisor"]["optimiser_attached"] is True

    control._records = [SimpleNamespace(hashrate=None, liveness=False)]
    outcome = daemon.trigger_cycle()

    assert outcome["ok"] is True
    assert control.restarts == 1
    assert outcome["result"]["healed"] == 1
    assert daemon.status()["cuop"]["reason"] == "hashrate_telemetry_unavailable"
