# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Exact planning arithmetic and real local ledger/HTTP regression tests."""
import threading

import pytest

from chronus.fleet.auth import FleetAuth, ReplayCache, new_token, replay_capacity_for_workers
from chronus.fleet.errors import AuthenticationError, LedgerError
from chronus.fleet.ledger import AnchorLedger, verify_ledger
from chronus.fleet.transport import FleetClient, FleetHTTPServer
from chronus.fleet.worker import _phase

pytestmark = pytest.mark.real


def test_scale_replay_budget_preserves_full_window():
    assert replay_capacity_for_workers(1, 1000, 150) == 200_000
    assert replay_capacity_for_workers(125, 1000, 150) == 1_150_500
    assert replay_capacity_for_workers(1000, 1000, 150) == 9_204_000
    assert replay_capacity_for_workers(125, 1000, 2000) == 300_500
    with pytest.raises(ValueError):
        replay_capacity_for_workers(0, 1000, 150)


def test_http_budget_is_wired_and_exhaustion_fails_closed():
    token = new_token()
    server = FleetHTTPServer(("127.0.0.1", 0), lambda *_: (200, {}), FleetAuth(token),
                             replay_capacity=2)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = FleetClient(f"http://127.0.0.1:{server.server_address[1]}", FleetAuth(token), "client:test")
        client.get("/v1/status")
        client.get("/v1/status")
        with pytest.raises(AuthenticationError):
            client.get("/v1/status")
        assert server.replay.status() == {"capacity": 2, "retained_nonces": 2, "capacity_rejections": 1}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def test_cache_never_evicts_a_live_nonce():
    cache = ReplayCache(1)
    assert cache.check_and_add("one", 1)
    assert not cache.check_and_add("two", 2)
    assert not cache.check_and_add("one", 3)
    assert cache.status()["capacity_rejections"] == 1


def test_stale_ledger_cannot_corrupt_chain(tmp_path):
    path = tmp_path / "ledger.jsonl"
    a, b = AnchorLedger(path), AnchorLedger(path)
    a.append("note", "a" * 64)
    with pytest.raises(LedgerError, match="stale writer"):
        b.append("note", "b" * 64)
    assert verify_ledger(path).valid
    entry = AnchorLedger(path).append("note", "b" * 64)
    assert entry["seq"] == 1
    with pytest.raises(LedgerError, match="stale writer"):
        a.append("note", "c" * 64)
    assert verify_ledger(path).entries == 2


def test_phase_is_stable_and_spreads_workers():
    phases = [_phase(f"node-{i}") for i in range(125)]
    assert all(0 <= phase < 1 for phase in phases)
    assert phases == [_phase(f"node-{i}") for i in range(125)]
    assert len(set(phases)) == 125
