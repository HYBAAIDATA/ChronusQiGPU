from __future__ import annotations

import json

import pytest


@pytest.fixture()
def cfg_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHIA_RUNTIME_CONFIG", str(tmp_path / "runtime_config.json"))
    return tmp_path


def _valid_pool() -> dict:
    return {
        "endpoint": "btc.viabtc.io:3333",
        "worker": "acct.worker1",
        "password": "pw",
        "enabled": True,
    }


def test_defaults_when_file_absent(cfg_dir):
    import runtime_config

    cfg = runtime_config.load()
    assert cfg["solvers"] == {"arms": 1, "workers": 32}
    assert cfg["hashrate"]["ceiling_hs"] == 1e19
    assert cfg["live_submit"]["enabled"] is False
    assert cfg["bounds"]["arms"] == [1, 600]


def test_save_roundtrip_and_validation(cfg_dir):
    import runtime_config

    cfg = runtime_config.save(
        {
            "pools": [_valid_pool()],
            "solvers": {"arms": 4, "workers": 32},
            "hashrate": {"target_hs": 5e6, "ceiling_hs": 1e19},
            "live_submit": {"enabled": False, "approval_id": ""},
            "window": 200000,
        }
    )
    assert cfg["schema"] == "pythia.runtime_config/1"
    loaded = runtime_config.load()
    assert loaded["solvers"]["arms"] == 4
    assert loaded["hashrate"]["target_hs"] == 5e6
    assert runtime_config.active_pool(loaded)["endpoint"] == "btc.viabtc.io:3333"


def test_hashrate_ceiling_is_enforced(cfg_dir):
    import runtime_config

    with pytest.raises(ValueError, match="1e19"):
        runtime_config.save(
            {
                "pools": [_valid_pool()],
                "hashrate": {"target_hs": 2e19},
            }
        )


@pytest.mark.parametrize("arms", [0, -1, 601, 1.5, "4"])
def test_arms_bounds_rejected(cfg_dir, arms):
    import runtime_config

    with pytest.raises(ValueError, match="arms"):
        runtime_config.save({"solvers": {"arms": arms, "workers": 32}})


def test_live_submit_requires_enabled_pool_and_approval(cfg_dir):
    import runtime_config

    with pytest.raises(ValueError, match="enabled pool"):
        runtime_config.save(
            {
                "pools": [],
                "live_submit": {"enabled": True, "approval_id": "00" * 32},
            }
        )


def test_live_submit_approval_binds_to_identity(cfg_dir):
    import runtime_config

    pool = _valid_pool()
    approval = runtime_config.identity_commit(pool["endpoint"], pool["worker"])
    cfg = runtime_config.save(
        {
            "pools": [pool],
            "live_submit": {"enabled": True, "approval_id": approval},
        }
    )
    assert runtime_config.live_submit_permitted(
        cfg, endpoint="btc.viabtc.io:3333", worker="acct.worker1"
    )
    # A different connection identity never satisfies the approval.
    assert not runtime_config.live_submit_permitted(
        cfg, endpoint="stratum.braiins.com:3333", worker="acct.worker1"
    )
    assert not runtime_config.live_submit_permitted(
        cfg, endpoint="btc.viabtc.io:3333", worker="other.worker"
    )


def test_pool_change_invalidates_gate(cfg_dir):
    import runtime_config

    pool = _valid_pool()
    approval = runtime_config.identity_commit(pool["endpoint"], pool["worker"])
    cfg = runtime_config.save(
        {
            "pools": [pool],
            "live_submit": {"enabled": True, "approval_id": approval},
        }
    )
    # New pool enabled in place of the approved one: stored approval no
    # longer matches any enabled pool identity.
    cfg2 = dict(cfg)
    cfg2["pools"] = [
        {
            "endpoint": "stratum.braiins.com:3333",
            "worker": "other.worker",
            "password": "x",
            "enabled": True,
        }
    ]
    assert not runtime_config.live_submit_permitted(cfg2)


def test_public_view_never_leaks_password(cfg_dir):
    import runtime_config

    cfg = runtime_config.save({"pools": [_valid_pool()]})
    view = runtime_config.public_view(cfg)
    assert "pw" not in json.dumps(view)
    assert view["pools"][0]["password_committed"] is True


def test_duplicate_and_double_enabled_pools_rejected(cfg_dir):
    import runtime_config

    with pytest.raises(ValueError, match="duplicates"):
        runtime_config.save({"pools": [_valid_pool(), _valid_pool()]})
    other = {
        "endpoint": "stratum.braiins.com:3333",
        "worker": "a.b",
        "password": "x",
        "enabled": True,
    }
    with pytest.raises(ValueError, match="exactly one"):
        runtime_config.save({"pools": [_valid_pool(), other]})


def test_bridge_config_gate_matches_arm_identity(cfg_dir):
    """The stratum bridge polls the runtime config file: submit is allowed
    only when enabled AND the arm's live connection identity equals the
    approved endpoint+worker."""
    from mining import stratum_bridge as sb
    import runtime_config

    pool = _valid_pool()
    approval = runtime_config.identity_commit(pool["endpoint"], pool["worker"])
    runtime_config.save(
        {
            "pools": [pool],
            "live_submit": {"enabled": True, "approval_id": approval},
        }
    )
    assert sb._config_live_submit_permits("btc.viabtc.io", 3333, "acct.worker1")
    assert not sb._config_live_submit_permits("btc.viabtc.io", 443, "acct.worker1")
    assert not sb._config_live_submit_permits("stratum.braiins.com", 3333, "acct.worker1")
    assert not sb._config_live_submit_permits("btc.viabtc.io", 3333, "other.worker")

    runtime_config.save({"pools": [pool], "live_submit": {"enabled": False, "approval_id": ""}})
    assert not sb._config_live_submit_permits("btc.viabtc.io", 3333, "acct.worker1")


def test_campaign_defaults_empty(cfg_dir):
    import runtime_config

    cfg = runtime_config.load()
    assert cfg["campaign"] == {"phases": []}


def test_campaign_phases_validate_and_normalize(cfg_dir):
    import runtime_config

    pool = _valid_pool()
    cfg = runtime_config.save(
        {
            "pools": [pool],
            "campaign": {
                "phases": [
                    {
                        "pool": "acct.worker1",
                        "duration_s": 600,
                        "target_hs": 1e18,
                        "arms": 2,
                        "live_submit": True,
                    }
                ]
            },
        }
    )
    assert cfg["campaign"]["phases"] == [
        {
            "pool": "acct.worker1",
            "duration_s": 600,
            "target_hs": 1e18,
            "arms": 2,
            "live_submit": True,
        }
    ]


def test_campaign_phase_pool_must_be_configured(cfg_dir):
    import runtime_config

    with pytest.raises(ValueError, match="must name a configured pool"):
        runtime_config.save(
            {
                "pools": [_valid_pool()],
                "campaign": {"phases": [{"pool": "ghost.worker", "duration_s": 600}]},
            }
        )


@pytest.mark.parametrize("duration", [0, 9, 86401, 10.5, "600", True])
def test_campaign_duration_bounds(cfg_dir, duration):
    import runtime_config

    with pytest.raises(ValueError, match="duration_s"):
        runtime_config.save(
            {
                "pools": [_valid_pool()],
                "campaign": {"phases": [{"pool": "acct.worker1", "duration_s": duration}]},
            }
        )


def test_campaign_phase_target_and_arms_bounds(cfg_dir):
    import runtime_config

    with pytest.raises(ValueError, match="target_hs"):
        runtime_config.save(
            {
                "pools": [_valid_pool()],
                "campaign": {
                    "phases": [{"pool": "acct.worker1", "duration_s": 600, "target_hs": 2e19}]
                },
            }
        )
    with pytest.raises(ValueError, match="arms"):
        runtime_config.save(
            {
                "pools": [_valid_pool()],
                "campaign": {"phases": [{"pool": "acct.worker1", "duration_s": 600, "arms": 601}]},
            }
        )


def test_campaign_max_phases(cfg_dir):
    import runtime_config

    with pytest.raises(ValueError, match="at most"):
        runtime_config.save(
            {
                "pools": [_valid_pool()],
                "campaign": {
                    "phases": [{"pool": "acct.worker1", "duration_s": 10} for _ in range(33)]
                },
            }
        )


def test_public_view_includes_campaign(cfg_dir):
    import runtime_config

    cfg = runtime_config.save(
        {
            "pools": [_valid_pool()],
            "campaign": {"phases": [{"pool": "acct.worker1", "duration_s": 600}]},
        }
    )
    view = runtime_config.public_view(cfg)
    assert view["campaign"]["phases"][0]["pool"] == "acct.worker1"
    assert "pw" not in json.dumps(view)


def test_bridge_target_hashrate_reads_config(cfg_dir):
    from mining import stratum_bridge as sb
    import runtime_config

    assert sb._configured_target_hs() == 0.0
    runtime_config.save({"hashrate": {"target_hs": 2.5e6, "ceiling_hs": 1e19}})
    assert sb._configured_target_hs() == 2.5e6
    # A hand-edited over-ceiling value fails closed to unthrottled only via
    # the reader — the API write path rejects it outright.
    path = runtime_config.config_path()
    path.write_text(json.dumps({"hashrate": {"target_hs": 2e19}}), encoding="utf-8")
    assert sb._configured_target_hs() == 0.0
