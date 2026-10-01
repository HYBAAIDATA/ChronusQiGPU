"""The discovery worker experiments on a simulated twin: it needs no device.

Before, every worker waited for ``MLA1517_MMIO_DEVICE``, so a host without a
mining device (a laptop, a CI runner, an operator's review box) never ran
the discovery campaign either. Now only the workers that drive the device
wait for it.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

import control_api


class _Process:
    pid = 4242

    def poll(self):
        return None

    def terminate(self):
        pass

    def wait(self, timeout=None):
        return 0

    def kill(self):
        pass


@pytest.fixture
def control(tmp_path, monkeypatch):
    env = {
        "MLA1517_STRATUM_USER": "rig.discovery",
        "PYTHIA_AUTOSTART_WORKERS": "1",
        "PYTHIA_BOOT_AUDIT": str(tmp_path / "BOOT_AUDIT.log"),
        "PYTHIA_WORKER_HEARTBEAT_DIR": str(tmp_path / "hb"),
    }
    spawned = []

    def popen(args, **_kwargs):
        if str(args[-1]).endswith(".py"):  # a worker, not a probe
            spawned.append(os.path.basename(args[-1]))
        return _Process()

    with patch.dict(os.environ, env, clear=False):
        monkeypatch.delenv("MLA1517_MMIO_DEVICE", raising=False)
        monkeypatch.setattr(control_api, "_AUDIT", None)
        monkeypatch.setattr(control_api.subprocess, "Popen", popen)
        plane = control_api.ControlPlane()
        plane.ensure_workers()
        yield plane, spawned
        plane.stop_event.set()


def test_without_a_device_only_discovery_spawns(control):
    plane, spawned = control
    states = {r.worker_id: r.state for r in plane.records()}
    assert spawned == ["discovery_runtime.py"]
    assert states["agentic-mining"] == "armed_no_device"
    assert states["salamander"] == "armed_no_device"
    assert states["discovery"] != "armed_no_device"
