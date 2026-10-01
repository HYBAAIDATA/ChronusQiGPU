"""A started miner hashes; it submits only with an approval bound to this pool.

The dashboard's live-submit approval used to be saved and read by nothing,
and a worker without --submit did not hash at all. Now a started worker
mines in shadow (full SHA256d and target checks, shares found and learned
from, nothing written to the pool) until the operator's approval names the
exact endpoint and worker it is connected as.
"""

from __future__ import annotations

import asyncio

import runtime_config
from manifold_pool_coordinator import PoolEndpoint
from test_agentic_voyages import EASY_TARGET, FakePool, _connected, _job, _served, bip34_coinb1
from test_pool_only_mining import _poll, _pool_only_coordinator


def _approve(port: int, worker: str) -> None:
    endpoint = f"127.0.0.1:{port}"
    runtime_config.save(
        {
            "pools": [{"endpoint": endpoint, "worker": worker, "password": "x", "enabled": True}],
            "live_submit": {
                "enabled": True,
                "approval_id": runtime_config.identity_commit(endpoint, worker),
            },
        }
    )


def test_shadow_until_the_approval_names_this_pool_and_worker(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHIA_RUNTIME_CONFIG", str(tmp_path / "runtime_config.json"))

    async def mine():
        pool = FakePool(target=EASY_TARGET, job=_job("job-s", coinb1=bip34_coinb1(900_001)))
        server, port = await _served(pool)
        coord = _pool_only_coordinator([PoolEndpoint("127.0.0.1", port, "ckpool")])
        coord.submit_enabled = False  # no --submit: the dashboard decides
        try:
            await _connected(coord, "job-s")
            assert await _poll(coord) is True
            assert await coord.search_current_job() is False
            assert coord.governor.shares >= 1  # a proof-checked share was found...
            assert pool.submits == []  # ...and never written
            assert coord.evidence_snapshot()["submission"] == "shadow"

            _approve(port, "someone-else")  # an approval for another identity
            coord._governor_config_at = float("-inf")  # the 5 s re-read, now
            assert await coord.search_current_job() is False
            assert pool.submits == [] and not coord.submission_permitted()

            _approve(port, "coordinator-default")  # this pool, this worker
            coord._governor_config_at = float("-inf")
            assert await _poll(coord) is True
            assert await coord.search_current_job() is True
            assert len(pool.submits) == 1
            assert coord.evidence_snapshot()["submission"] == "live"

            runtime_config.save({})  # revoked: back to shadow within one re-read
            coord._governor_config_at = float("-inf")
            coord._refresh_governor()
            assert not coord.submission_permitted()
        finally:
            await coord.client.close()
            server.close()

    asyncio.run(mine())
