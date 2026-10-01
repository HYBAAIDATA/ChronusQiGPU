from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLATFORM = ROOT / "chronus" / "mla1517_platform" / "python"
for path in (ROOT, PLATFORM):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from mining.stratum_bridge import submission_exit_code
from scripts import live_pool_smoke
import runtime_config


def _args(**overrides):
    values = {
        "pool": "braiins",
        "worker": "actual-account.rig-01",
        "password_env": "PYTHIA_SMOKE_POOL_PASSWORD",
        "endpoint": None,
        "backend": "cpu",
        "window": 1024,
        "max_runtime": 30.0,
        "confirm_live_submit": True,
        "disarm_after": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_smoke_child_command_never_contains_password():
    args = _args()
    command = live_pool_smoke._bridge_command(args, "stratum.braiins.com:3333")
    rendered = " ".join(command)
    assert "--password" not in command
    assert "super-secret" not in rendered


def test_smoke_rejects_placeholder_worker():
    parser = live_pool_smoke._parser()
    with pytest.raises(SystemExit):
        live_pool_smoke._validate(_args(worker="account.worker"), parser)


def test_requested_live_submission_fails_without_pool_acceptance():
    assert submission_exit_code(True, 0) == 2
    assert submission_exit_code(True, 1) == 0
    assert submission_exit_code(False, 0) == 0


def test_ephemeral_config_is_private_and_restores_environment(tmp_path, monkeypatch):
    path = tmp_path / "live-smoke.json"
    config = runtime_config.default_config()
    monkeypatch.setenv("PYTHIA_RUNTIME_CONFIG", "original-config.json")

    live_pool_smoke._save_ephemeral_config(path, config)

    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert os.environ["PYTHIA_RUNTIME_CONFIG"] == "original-config.json"