"""Owner-B lifecycle + boundary contracts: stop semantics, campaign retirement,
measured-zero telemetry, sidecar freshness, guardian wiring, graceful SIGTERM."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from http import HTTPStatus
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PY_DIR = REPO_ROOT / "chronus/mla1517_platform" / "python"
sys.path.insert(0, str(PY_DIR))

import control_api
import runtime_config
import system_fabric


def _campaign_cfg(tmp_path):
    cfg = {
        "pools": [
            {"endpoint": "stratum+tcp://a:3333", "worker": "w-a", "enabled": True},
            {"endpoint": "stratum+tcp://b:3333", "worker": "w-b", "enabled": False},
        ],
        "solvers": {"arms": 2, "workers": 2},
        "hashrate": {"target_hs": 1_000.0, "ceiling_hs": 1_000.0},
        "live_submit": {"enabled": False, "approval_id": ""},
        "campaign": {
            "phases": [
                {"pool": "w-a", "duration_s": 0.3, "arms": 1},
                {"pool": "w-b", "duration_s": 0.3, "arms": 1},
            ]
        },
    }
    path = tmp_path / "runtime_config.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    return path


class _CampaignDeps:
    def __init__(self, tmp_path, monkeypatch, counters=None, single_phase=False):
        path = _campaign_cfg(tmp_path)
        if single_phase:
            cfg = json.loads(path.read_text(encoding="utf-8"))
            cfg["campaign"]["phases"] = cfg["campaign"]["phases"][:1]
            path.write_text(json.dumps(cfg), encoding="utf-8")
        self.applied = []
        self.retired = 0
        self.counters = counters if counters is not None else {"hashrate_hs": 12.5}
        monkeypatch.setenv("PYTHIA_RUNTIME_CONFIG", str(path))

    def apply_config(self, next_cfg):
        self.applied.append(next_cfg)
        return {"ok": True}

    def retire_all(self):
        self.retired += 1
        return ["arm-0"]

    def counter_probe(self):
        return self.counters


def _fresh_campaign(monkeypatch):
    monkeypatch.setattr(system_fabric, "CAMPAIGN", system_fabric._Runner("campaign"))
    return system_fabric.CAMPAIGN


_TERMINAL_STATES = {"idle", "done", "stopped", "error"}


def _wait_terminal(runner, timeout=10.0):
    deadline = time.time() + timeout
    while runner.status()["state"] not in _TERMINAL_STATES and time.time() < deadline:
        time.sleep(0.05)
    if runner._thread is not None:
        runner._thread.join(timeout=timeout)
    return runner.status()


def test_campaign_retires_arms_on_phase_failure(tmp_path, monkeypatch):
    deps = _CampaignDeps(tmp_path, monkeypatch)
    runner = _fresh_campaign(monkeypatch)

    def boom(_cfg):
        raise RuntimeError("apply failed mid-flight")

    assert system_fabric.start_campaign(
        apply_config=boom, retire_all=deps.retire_all, counter_probe=deps.counter_probe
    )
    status = _wait_terminal(runner)
    assert status["state"] == "error"
    # RUN-02: arms are retired even though the campaign never completed.
    assert deps.retired == 1
    assert status["progress"]["campaign_record"]["retired"] == ["arm-0"]


def test_campaign_operator_stop_retires_and_stays_stopped(tmp_path, monkeypatch):
    deps = _CampaignDeps(tmp_path, monkeypatch)
    runner = _fresh_campaign(monkeypatch)
    assert system_fabric.start_campaign(
        apply_config=deps.apply_config,
        retire_all=deps.retire_all,
        counter_probe=deps.counter_probe,
    )
    time.sleep(0.15)
    runner.stop()
    status = _wait_terminal(runner)
    # RUN-01: an operator stop is terminal "stopped", never "error" — and
    # retirement still lands on the unwinding path.
    assert status["state"] == "stopped"
    assert deps.retired == 1
    assert status["progress"]["campaign_record"]["retired"] == ["arm-0"]


def test_runner_stop_is_truthful_stopping_until_worker_exits(monkeypatch):
    """RUN-01: stop() must not claim stopped/finished while the worker is
    still inside a phase — the state is 'stopping' until actual exit."""
    runner = system_fabric._Runner("blocked")
    release = threading.Event()

    def blocked(r):
        while not r.stopped:
            time.sleep(0.01)
        # Operator stop observed: now simulate teardown still in flight.
        release.wait(timeout=10)
        raise InterruptedError("phase unwound after stop")

    assert runner.start(blocked)
    time.sleep(0.05)
    assert runner.stop() is True
    mid = runner.status()
    assert mid["state"] == "stopping"
    assert mid["finished_at"] is None
    # Restart is refused while the old worker still runs.
    assert runner.start(lambda r: None) is False
    release.set()
    status = _wait_terminal(runner)
    assert status["state"] == "stopped"
    assert status["finished_at"] is not None
    assert status["finished_at"] >= status["started_at"]
    assert "stop_detail" in status["progress"]
    # And the runner is eligible to start again once the worker exited.
    assert runner.start(lambda r: {"ok": True}) is True
    assert _wait_terminal(runner)["state"] == "done"


def test_runner_done_when_stop_arrives_between_phases(monkeypatch):
    """A function that returns normally after the stop flag is still a
    stopped run, not a successful 'done'."""
    runner = system_fabric._Runner("late-stop")

    def slow(r):
        time.sleep(0.05)
        return {"partial": True}

    assert runner.start(slow)
    runner.stop()
    status = _wait_terminal(runner)
    assert status["state"] == "stopped"
    assert status["result"] == {"partial": True}


def test_campaign_measured_zero_is_a_measurement(tmp_path, monkeypatch):
    deps = _CampaignDeps(tmp_path, monkeypatch, counters={"hashrate_hs": 0.0}, single_phase=True)
    runner = _fresh_campaign(monkeypatch)
    assert system_fabric.start_campaign(
        apply_config=deps.apply_config,
        retire_all=deps.retire_all,
        counter_probe=deps.counter_probe,
    )
    status = _wait_terminal(runner)
    # DATA-01: an observed 0.0 stays a measurement, distinct from unmeasured.
    assert status["result"]["phases"][0]["measured_hs_avg"] == 0.0


def test_campaign_absent_rate_stays_unmeasured(tmp_path, monkeypatch):
    deps = _CampaignDeps(tmp_path, monkeypatch, counters={}, single_phase=True)
    runner = _fresh_campaign(monkeypatch)
    assert system_fabric.start_campaign(
        apply_config=deps.apply_config,
        retire_all=deps.retire_all,
        counter_probe=deps.counter_probe,
    )
    status = _wait_terminal(runner)
    assert status["result"]["phases"][0]["measured_hs_avg"] is None


def test_campaign_shares_are_phase_deltas_not_cumulative(tmp_path, monkeypatch):
    """DATA-01: a cumulative process-wide shares counter must not inflate a
    later phase — each phase records only the shares earned inside it."""
    deps = _CampaignDeps(tmp_path, monkeypatch)
    runner = _fresh_campaign(monkeypatch)
    # First probe of a phase is the baseline read; later probes are the
    # loop reads. This makes the expected values independent of how many
    # loop iterations fit in the phase duration.
    calls = {1: 0, 2: 0}

    def probe():
        phase = len(deps.applied)  # apply_config runs once per phase
        calls[phase] += 1
        if phase == 1:
            return {"hashrate_hs": 10.0, "shares_accepted": 4 if calls[phase] == 1 else 6}
        return {"hashrate_hs": 10.0, "shares_accepted": 6 if calls[phase] == 1 else 8}

    deps.counter_probe = probe
    assert system_fabric.start_campaign(
        apply_config=deps.apply_config,
        retire_all=deps.retire_all,
        counter_probe=deps.counter_probe,
    )
    status = _wait_terminal(runner)
    phases = status["result"]["phases"]
    assert len(phases) == 2
    assert phases[0]["shares_accepted"] == 2
    assert phases[1]["shares_accepted"] == 2


def test_campaign_shares_counter_reset_counts_new_total(tmp_path, monkeypatch):
    """DATA-01: when the aggregate counter resets (arm respawn/pool switch)
    the reading itself is the new phase-local count, not a negative delta."""
    deps = _CampaignDeps(tmp_path, monkeypatch, single_phase=True)
    runner = _fresh_campaign(monkeypatch)
    calls = {"n": 0}

    def probe():
        calls["n"] += 1
        # Baseline reads 4; every later read drops to 2 (a respawned arm's
        # fresh counter) — the phase delta is the post-reset count itself.
        return {"hashrate_hs": 10.0, "shares_accepted": 4 if calls["n"] == 1 else 2}

    deps.counter_probe = probe
    assert system_fabric.start_campaign(
        apply_config=deps.apply_config,
        retire_all=deps.retire_all,
        counter_probe=deps.counter_probe,
    )
    status = _wait_terminal(runner)
    assert status["result"]["phases"][0]["shares_accepted"] == 2


def test_arm_counters_distinguish_zero_absent_and_stale(tmp_path, monkeypatch):
    hb = tmp_path / "hb"
    hb.mkdir()
    monkeypatch.setenv("PYTHIA_WORKER_HEARTBEAT_DIR", str(hb))
    # No sidecar at all: hashrate is unmeasured, not zero.
    assert control_api._arm_counters()["hashrate_hs"] is None
    # A fresh sidecar reporting 0.0 is a real measurement.
    (hb / "a.metrics.json").write_text(
        json.dumps({"counters": {"hashrate_hs": 0.0, "shares_accepted": 2}}),
        encoding="utf-8",
    )
    out = control_api._arm_counters()
    assert out["hashrate_hs"] == 0.0 and out["shares_accepted"] == 2
    # A stale sidecar (killed arm) must not leak into the live totals.
    stale = hb / "dead.metrics.json"
    stale.write_text(
        json.dumps({"counters": {"hashrate_hs": 999.0, "shares_accepted": 50}}),
        encoding="utf-8",
    )
    old = time.time() - 3600
    os.utime(stale, (old, old))
    out = control_api._arm_counters()
    assert out["hashrate_hs"] == 0.0 and out["shares_accepted"] == 2


def test_control_api_import_resolves_guardian():
    """Regression: importing control_api cold (the python main.py entry) must
    leave pythia_guardian_api callable — repo-root packages are not on the
    script's sys.path without the shim."""
    code = (
        "import sys; sys.path.insert(0, %r);"
        "import control_api;"
        "assert control_api.pythia_guardian_api is not None, 'guardian bound to None'"
    ) % str(PY_DIR)
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, result.stderr


def test_serve_registers_graceful_sigterm(monkeypatch):
    """serve() must register SIGTERM/SIGBREAK so a terminated server runs the
    finally-cleanup instead of dying mid-flight."""
    captured = {}

    def fake_signal(sig, handler):
        captured[sig] = handler

    control = type("C", (), {"shutdown": lambda self: None})()
    monkeypatch.setattr(control_api, "_control_plane", lambda: control)
    monkeypatch.setattr(control_api, "_CONTROL", control)
    monkeypatch.setattr(control_api, "start_repo_engineer", lambda: None)
    monkeypatch.setattr(control_api, "announce_skills", lambda: None)
    monkeypatch.setattr(system_fabric, "startup_self_repair_enabled", lambda: False)
    monkeypatch.setattr(control_api, "publish_active_port", lambda *a, **k: None)
    monkeypatch.setattr(control_api, "retract_active_port", lambda: None)
    lock = type("L", (), {"release": lambda self: setattr(self, "released", True)})()
    monkeypatch.setattr(control_api, "_boot_lock", lambda: lock)
    monkeypatch.setattr(control_api.signal, "signal", fake_signal)
    monkeypatch.setattr(
        control_api, "_audit", lambda: type("A", (), {"append": lambda *a, **k: None})()
    )

    thread = threading.Thread(
        target=control_api.serve, kwargs={"host": "127.0.0.1", "port": 0}, daemon=True
    )
    thread.start()
    deadline = time.time() + 10
    while not captured and time.time() < deadline:
        time.sleep(0.05)
    assert signal.SIGTERM in captured
    captured[signal.SIGTERM](signal.SIGTERM, None)
    thread.join(timeout=10)
    assert not thread.is_alive()
    assert getattr(lock, "released", False)


class _NoDeviceControl:
    def mining_device_bound(self):
        return False

    def stop_workers(self):
        return []


def _config_store(tmp_path, monkeypatch):
    path = tmp_path / "runtime_config.json"
    path.write_text(json.dumps(runtime_config.default_config()), encoding="utf-8")
    monkeypatch.setenv("PYTHIA_RUNTIME_CONFIG", str(path))
    monkeypatch.setattr(control_api, "_control_plane", lambda: _NoDeviceControl())
    monkeypatch.setattr(
        control_api, "_audit", lambda: type("A", (), {"append": lambda *a, **k: None})()
    )
    return path


def test_config_put_rejects_unknown_sections_and_bad_bounds(tmp_path, monkeypatch):
    _config_store(tmp_path, monkeypatch)

    status, body = control_api._config_put({"not_a_section": {}})
    assert status == HTTPStatus.BAD_REQUEST and "unknown config sections" in body["error"]

    for bad in (
        {"solvers": {"arms": 0}},
        {"solvers": {"arms": 999}},
        {"solvers": {"workers": 0}},
        {"hashrate": {"target_hs": -1.0}},
        {"hashrate": {"target_hs": 1e19}},
        {"pools": [{"endpoint": "no port", "worker": "w", "password": "p"}]},
    ):
        status, _body = control_api._config_put(bad)
        assert status == HTTPStatus.BAD_REQUEST, bad
    # Nothing was persisted by any of the rejections.
    assert runtime_config.load()["solvers"]["arms"] == 1


def test_config_put_persists_and_fail_closes_without_device(tmp_path, monkeypatch):
    path = _config_store(tmp_path, monkeypatch)

    status, body = control_api._config_put({"solvers": {"arms": 3}})
    assert status == HTTPStatus.OK and body["ok"] is True
    assert runtime_config.load()["solvers"]["arms"] == 3
    # Honest apply: no device -> durable config, arms stay armed_no_device.
    assert "no mining device" in body["applied"]["note"]
    assert json.loads(path.read_text(encoding="utf-8"))["solvers"]["arms"] == 3


def test_live_submit_approval_binds_pool_identity_and_revokes(tmp_path, monkeypatch):
    _config_store(tmp_path, monkeypatch)
    pool = {
        "endpoint": "pool.example:3333",
        "worker": "acct.worker1",
        "password": "secret",
        "enabled": True,
    }

    status, _body = control_api._config_put({"pools": [pool], "live_submit": {"enabled": True}})
    assert status == HTTPStatus.OK
    saved = runtime_config.load()
    # The approval is an identity commit: SHA-256(endpoint|worker).
    expected = runtime_config.identity_commit("pool.example:3333", "acct.worker1")
    assert saved["live_submit"]["approval_id"] == expected
    assert runtime_config.live_submit_permitted(
        saved, endpoint="pool.example:3333", worker="acct.worker1"
    )
    # Same approval must not unlock a different worker or endpoint.
    assert not runtime_config.live_submit_permitted(
        saved, endpoint="pool.example:3333", worker="acct.other"
    )
    assert not runtime_config.live_submit_permitted(
        saved, endpoint="other.pool:3333", worker="acct.worker1"
    )

    # A pools write with no live_submit section revokes the arming: the
    # approval was bound to an identity that may no longer exist.
    status, _body = control_api._config_put({"pools": [dict(pool, worker="acct.w2")]})
    assert status == HTTPStatus.OK
    saved = runtime_config.load()
    assert saved["live_submit"] == {"enabled": False, "approval_id": ""}
    assert not runtime_config.live_submit_permitted(saved)


def test_persisted_session_state_survives_restore(tmp_path, monkeypatch):
    """Persistence/restore: a config write is durable across a cold load."""
    path = _config_store(tmp_path, monkeypatch)
    control_api._config_put({"solvers": {"arms": 5}, "window": 1024})
    # Simulate process restart: only the file remains.
    restored = runtime_config.load()
    assert restored["solvers"]["arms"] == 5 and restored["window"] == 1024
    # Corrupt file fails closed to defaults, never to garbage.
    path.write_text("{not json", encoding="utf-8")
    fallback = runtime_config.load()
    assert fallback["solvers"]["arms"] == 1


def test_schema_corrupt_persisted_config_loads_defaults(tmp_path, monkeypatch):
    """Valid JSON that violates the schema is untrusted too: load() must not
    hand unvalidated sections to public_view (e.g. {"solvers": null} would
    crash dict(cfg["solvers"]) -> 500 on /api/v1/config)."""
    path = _config_store(tmp_path, monkeypatch)
    path.write_text(json.dumps({"solvers": None}), encoding="utf-8")
    fallback = runtime_config.load()
    assert fallback["solvers"]["arms"] == 1
    view = runtime_config.public_view(fallback)
    assert view["solvers"]["arms"] == 1

    path.write_text(json.dumps({"window": "wide"}), encoding="utf-8")
    assert runtime_config.load()["window"] == 200000
