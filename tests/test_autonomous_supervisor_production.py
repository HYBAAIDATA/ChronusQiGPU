"""Production wiring and evidence tests for the autonomy daemon."""

from types import SimpleNamespace

import autonomous_supervisor


class _ControlPlane:
    def __init__(self, records):
        self._records = records
        self.autostart = False

    def records(self):
        return list(self._records)

    def set_autostart(self, enabled):
        self.autostart = bool(enabled)

    def ensure_workers(self):
        return None


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


def test_attaches_optimizer_only_with_measured_telemetry(monkeypatch):
    control = _ControlPlane([SimpleNamespace(hashrate=250.0, liveness=True)])
    monkeypatch.setattr("control_api._control_plane", lambda: control)
    monkeypatch.setenv("PYTHIA_CUOP_POWER_W", "12.5")
    daemon = autonomous_supervisor.AutonomousSupervisor(interval_s=5.0)

    daemon._build()

    status = daemon.status()
    assert status["cuop"]["available"] is True
    assert status["cuop"]["evidence_class"] == "Measured"
    assert status["cuop"]["reading"]["useful_ops"] == 1250.0
    assert status["supervisor"]["optimiser_attached"] is True
