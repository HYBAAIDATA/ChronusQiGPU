"""Config-bound execution, pacing and fail-closed policy regressions."""

import json
import stat
from types import SimpleNamespace

import pytest

from chronus.mla1517_platform.python import runtime_config


@pytest.mark.parametrize(
    "section",
    [
        {"hashrate": {"target_hs": float("inf")}},
        {"hashrate": {"ceiling_hs": 2e19}},
        {"solvers": {"arms": True}},
        {"window": True},
        {"live_submit": {"enabled": "false"}},
        {"execution": {"mode": "invented"}},
        {"intelligence": {"seed": True}},
        {"intelligence": {"max_workers": 33}},
    ],
)
def test_untrusted_policy_cannot_retain_live_approval(tmp_path, monkeypatch, section):
    monkeypatch.setenv("PYTHIA_RUNTIME_CONFIG", str(tmp_path / "config.json"))
    pool = {
        "endpoint": "example.invalid:3333",
        "worker": "fixture.worker",
        "password": "fixture",
        "enabled": True,
    }
    config = {
        "pools": [pool],
        "live_submit": {
            "enabled": True,
            "approval_id": runtime_config.identity_commit(pool["endpoint"], pool["worker"]),
        },
    }
    config.update(section)
    runtime_config.config_path().write_text(json.dumps(config))
    loaded = runtime_config.load()
    assert loaded["live_submit"]["enabled"] is False
    assert loaded["hashrate"]["ceiling_hs"] <= 1e19


def test_private_atomic_policy_and_lower_ceiling(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHIA_RUNTIME_CONFIG", str(tmp_path / "config.json"))
    saved = runtime_config.save({"hashrate": {"ceiling_hs": 1000, "target_hs": 0}})
    assert saved["hashrate"]["ceiling_hs"] == 1000
    assert runtime_config.load()["hashrate"]["ceiling_hs"] == 1000
    assert stat.S_IMODE(runtime_config.config_path().stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".config.json.*"))
    with pytest.raises(ValueError, match="ceiling"):
        runtime_config.save({"hashrate": {"ceiling_hs": 1000, "target_hs": 2000}})


@pytest.mark.asyncio
async def test_zero_target_still_paces_under_ceiling(monkeypatch):
    from mining import stratum_bridge as bridge

    clock = {"now": 0.0, "sleeps": []}

    async def sleep(seconds):
        clock["sleeps"].append(seconds)
        clock["now"] += seconds

    monkeypatch.setattr(bridge, "time", SimpleNamespace(perf_counter=lambda: clock["now"]))
    monkeypatch.setattr(bridge, "asyncio", SimpleNamespace(sleep=sleep))
    monkeypatch.setattr(
        bridge, "_load_runtime_config", lambda: {"hashrate": {"ceiling_hs": 10, "target_hs": 0}}
    )
    assert await bridge._pace_configured_work(1000, 0) == 10
    assert clock["now"] == 100
    assert max(clock["sleeps"]) <= 30


def test_config_error_revokes_previous_governor_approval(monkeypatch):
    import runtime_config as config_module
    from chronus.mla1517.mining.coordinator import IntelligentPoolCoordinator

    coord = IntelligentPoolCoordinator.__new__(IntelligentPoolCoordinator)
    coord._governor_config_at = float("-inf")
    coord._live_submit_approved = True

    def unavailable():
        raise OSError("fixture: policy unavailable")

    monkeypatch.setattr(config_module, "load", unavailable)
    coord._refresh_governor()
    assert coord._live_submit_approved is False


def test_independent_default_executes_real_known_answer_without_gpu(tmp_path, monkeypatch):
    from chronus.virtual_igpu.client import ChronusClient
    from chronus.virtual_igpu.mining_hasher import ChronusVirtualIGPUHasher

    monkeypatch.setenv("PYTHIA_RUNTIME_CONFIG", str(tmp_path / "config.json"))
    hasher = ChronusVirtualIGPUHasher(client=ChronusClient(store_dir=str(tmp_path / "device")))
    hasher.self_check()
    assert "chronus-software-fabric" in hasher.device
    assert hasher.physical_device_executed is False


def test_scale_stack_config_cannot_silently_use_software(tmp_path, monkeypatch):
    from chronus.virtual_igpu.client import ChronusClient
    from chronus.virtual_igpu.adapters import AdapterUnavailable, ChronusSoftwareFabricAdapter
    from chronus.virtual_igpu.runtime import RuntimeDaemon
    from chronus.virtual_igpu.mining_hasher import ChronusVirtualIGPUHasher

    monkeypatch.setenv("PYTHIA_RUNTIME_CONFIG", str(tmp_path / "config.json"))
    runtime_config.save({"execution": {"mode": "scale_stack"}})
    daemon = RuntimeDaemon(store_dir=tmp_path / "device", adapters=[ChronusSoftwareFabricAdapter()])
    hasher = ChronusVirtualIGPUHasher(client=ChronusClient(daemon=daemon))
    with pytest.raises(AdapterUnavailable, match="fallback is disabled"):
        hasher.self_check()


def test_control_api_persists_execution_and_intelligence_sections(tmp_path, monkeypatch):
    import control_api

    # This contract tests merge/validation/persistence, not worker startup.
    monkeypatch.setattr(control_api, "_apply_runtime_config", lambda cfg: {"fixture": True})
    monkeypatch.setattr(control_api, "_audit", lambda: SimpleNamespace(append=lambda *a, **k: None))
    monkeypatch.setattr(control_api, "_live_arm_ids", lambda: [])
    monkeypatch.setenv("PYTHIA_RUNTIME_CONFIG", str(tmp_path / "config.json"))
    status, response = control_api._config_put(
        {"execution": {"mode": "auto"}, "intelligence": {"seed": 42, "max_workers": 1}}
    )
    assert int(status) == 200
    loaded = runtime_config.load()
    assert loaded["execution"]["mode"] == "auto"
    assert loaded["intelligence"]["seed"] == 42
    assert loaded["intelligence"]["max_workers"] == 1


def test_corrupt_scale_stack_policy_never_downgrades_to_independent(tmp_path, monkeypatch):
    from chronus.virtual_igpu.client import ChronusClient
    from chronus.virtual_igpu.mining_hasher import ChronusVirtualIGPUHasher

    monkeypatch.setenv("PYTHIA_RUNTIME_CONFIG", str(tmp_path / "config.json"))
    runtime_config.config_path().write_text(
        json.dumps({"execution": {"mode": "scale_stack"}, "window": -1})
    )
    hasher = ChronusVirtualIGPUHasher(client=ChronusClient(store_dir=str(tmp_path / "device")))
    with pytest.raises(PermissionError, match="invalid persisted execution policy"):
        hasher.self_check()
