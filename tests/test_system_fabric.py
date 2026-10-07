from __future__ import annotations

import time

import pytest


@pytest.fixture()
def cfg_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHIA_RUNTIME_CONFIG", str(tmp_path / "runtime_config.json"))
    return tmp_path


def _pool(endpoint: str, worker: str, enabled: bool = False) -> dict:
    return {"endpoint": endpoint, "worker": worker, "password": "pw", "enabled": enabled}


def test_forensic_map_marks_every_named_subsystem():
    import system_fabric

    m = system_fabric.forensic_map(opencl_count=0, have_mmio=False, have_credentials=True)
    assert m["schema"] == "pythia.fabric_map/1"
    keys = {s["key"] for s in m["subsystems"]}
    # The operator's named technology all appears — the map is the answer
    # to "where is my manifold / tensor / VQC / Salamander / …".
    assert {
        "chronus",
        "manifold_iid",
        "poincare_11d",
        "yang_mills",
        "ricci",
        "toe",
        "structured_search",
        "unstructured_search",
        "tensor",
        "vqc",
        "folding_storage",
        "salamander",
        "agentic_workflow",
        "chain_verification",
    } <= keys
    assert all(
        s["wired"] in {"production", "fabric", "orchestrator", "idle", "stub", "parked"}
        for s in m["subsystems"]
    )
    # OpenCL-gated rows report the gate closed with zero devices.
    gated = {s["key"]: s for s in m["subsystems"] if s["gate"]}
    assert gated["chronus"]["gate_state"] == "closed"
    # Canonical subsystems are present; parked (unwired) subsystems are
    # absent and demoted — the map must name exactly this set, no more.
    # manifold_iid, structured_search, unstructured_search, tensor, vqc,
    # first_principles_quantum and discovery were promoted: the Kellogg/TOE/
    # TUQC consolidations repointed their registry entries at real modules
    # (kellogg.exact_tensor, Intelligence.search_crystal, and the
    # turing_universal_quantum_computer package), so find_spec resolves
    # them as present. pulvini_runtime followed once Intelligence.pulvini_runtime
    # was wired (opt-in solve-first planning).
    parked = {
        "pythia_agent",
        "ontology_chain",
        "search_tree",
        "salamander_transaction",
        "pool_aware_miner",
    }
    absent = {s["key"] for s in m["subsystems"] if not s["present"]}
    assert absent == parked
    assert all(
        s["present"] for s in m["subsystems"] if s["key"] not in parked
    )
    assert all(
        s["wired"] == "parked" for s in m["subsystems"] if s["key"] in parked
    )


def test_forensic_map_gates_open_on_hardware():
    import system_fabric

    m = system_fabric.forensic_map(opencl_count=2, have_mmio=True, have_credentials=True)
    gated = {s["key"]: s for s in m["subsystems"] if s["gate"]}
    assert gated["chronus"]["gate_state"] == "open"
    assert m["gates"]["opencl_devices"] == 2


def test_runner_lifecycle_done_and_error():
    import system_fabric

    r = system_fabric._Runner("t")
    assert r.start(lambda _r: {"ok": True}) is True
    deadline = time.time() + 5
    while r.status()["state"] == "running" and time.time() < deadline:
        time.sleep(0.05)
    status = r.status()
    assert status["state"] == "done"
    assert status["result"] == {"ok": True}

    def boom(_r):
        raise ValueError("nope")

    r2 = system_fabric._Runner("t2")
    assert r2.start(boom) is True
    deadline = time.time() + 5
    while r2.status()["state"] == "running" and time.time() < deadline:
        time.sleep(0.05)
    assert r2.status()["state"] == "error"
    assert "nope" in (r2.status()["error"] or "")


def test_runner_start_is_exclusive():
    import system_fabric
    import threading

    gate = threading.Event()
    r = system_fabric._Runner("t3")
    assert r.start(lambda _r: gate.wait(2)) is True
    try:
        assert r.start(lambda _r: None) is False  # already running
    finally:
        r.stop()
        gate.set()


def test_campaign_requires_configured_phases(cfg_dir):
    import system_fabric
    import runtime_config

    runtime_config.save({"pools": [_pool("stratum.braiins.com:3333", "acct.w1")]})
    runner = system_fabric._Runner("c")
    with pytest.raises(ValueError, match="no phases"):
        system_fabric._run_campaign(
            runner,
            apply_config=lambda cfg: cfg,
            retire_all=lambda: [],
            counter_probe=lambda: {},
        )


def test_campaign_drives_phases_through_config(cfg_dir, monkeypatch):
    """Each phase enables exactly its pool, sets target/arms, binds the
    live_submit approval to that identity, then retires all arms at end."""
    import system_fabric
    import runtime_config

    braiins = _pool("stratum.braiins.com:3333", "acct.b1", enabled=True)
    viabtc = _pool("btc.viabtc.io:3333", "acct.v1")
    runtime_config.save(
        {
            "pools": [braiins, viabtc],
            "campaign": {
                "phases": [
                    {
                        "pool": "acct.b1",
                        "duration_s": 10,
                        "target_hs": 1e18,
                        "arms": 2,
                        "live_submit": True,
                    },
                    {
                        "pool": "acct.v1",
                        "duration_s": 10,
                        "target_hs": 1e18,
                        "arms": 4,
                        "live_submit": False,
                    },
                ]
            },
        }
    )

    # Fake clock: sleep advances time instantly so 10s phases take ~0s.
    fake_now = [time.time()]
    monkeypatch.setattr(system_fabric.time, "time", lambda: fake_now[0])
    monkeypatch.setattr(
        system_fabric.time, "sleep", lambda s: fake_now.__setitem__(0, fake_now[0] + s)
    )

    applied: list[dict] = []
    retired: list[bool] = []
    # Cumulative process counter: 3 shares before the phase, 5 during it —
    # the phase record keeps only the phase-local delta.
    probe_calls = {"n": 0}

    def probe() -> dict:
        probe_calls["n"] += 1
        return {"hashrate_hs": 5e5, "shares_accepted": 3 if probe_calls["n"] == 1 else 5}

    record = system_fabric._run_campaign(
        system_fabric._Runner("c"),
        apply_config=lambda cfg: (applied.append(cfg), cfg)[1],
        retire_all=lambda: (retired.append(True), ["arm-0"])[1],
        counter_probe=probe,
    )

    assert len(record["phases"]) == 2
    p0, p1 = applied[0], applied[1]
    # Phase 0: braiins enabled, armed to that identity.
    assert next(p for p in p0["pools"] if p["enabled"])["worker"] == "acct.b1"
    assert p0["solvers"]["arms"] == 2
    assert p0["live_submit"]["enabled"] is True
    assert p0["live_submit"]["approval_id"] == runtime_config.identity_commit(
        "stratum.braiins.com:3333", "acct.b1"
    )
    # Phase 1: switched to viabtc, live submit disarmed.
    assert next(p for p in p1["pools"] if p["enabled"])["worker"] == "acct.v1"
    assert p1["solvers"]["arms"] == 4
    assert p1["live_submit"]["enabled"] is False
    # Measured counters recorded honestly: hashrate is the measured mean,
    # shares are the phase-local delta (5 earned inside the phase, the 3
    # pre-phase shares do not leak into its record).
    assert record["phases"][0]["measured_hs_avg"] == 5e5
    assert record["phases"][0]["shares_accepted"] == 2
    assert record["retired"] == ["arm-0"]
    assert retired == [True]


def test_campaign_unknown_pool_fails(cfg_dir):
    import system_fabric
    import runtime_config

    # A hand-edited phase naming no configured pool is refused at run time.
    runtime_config.save({"pools": [_pool("stratum.braiins.com:3333", "acct.w1")]})
    cfg = runtime_config.load()
    cfg["campaign"] = {"phases": [{"pool": "ghost.w", "duration_s": 10}]}
    runtime_config.config_path().write_text(__import__("json").dumps(cfg), encoding="utf-8")
    # validate() would reject this on save; _run_campaign must fail closed.
    with pytest.raises(ValueError, match="not configured"):
        system_fabric._run_campaign(
            system_fabric._Runner("c"),
            apply_config=lambda c: c,
            retire_all=lambda: [],
            counter_probe=lambda: {},
        )


def test_idle_statuses_are_idle():
    import system_fabric

    for fn in (
        system_fabric.agentic_status,
        system_fabric.campaign_status,
        system_fabric.selftest_status,
        system_fabric.verification_status,
    ):
        st = fn()
        assert st["state"] in {"idle", "done", "stopped", "error"}
        assert "schema" in st
