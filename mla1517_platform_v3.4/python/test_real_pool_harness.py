"""The read-only real-pool harness, exercised against the local scripted pool."""

from __future__ import annotations

import asyncio

from real_pool_voyage import run_real_pool_voyage
from test_agentic_voyages import EASY_TARGET, FakePool, _job, _served


async def _run() -> tuple[dict, FakePool]:
    pool = FakePool(target=EASY_TARGET, job=_job("live-like"))
    server, port = await _served(pool)
    try:
        report = await run_real_pool_voyage(
            f"127.0.0.1:{port}", "PYTHIA.001", "x", seconds=2.0, backend="cpu", tls=False
        )
    finally:
        server.close()
        await server.wait_closed()
    return report, pool


def test_harness_executes_real_jobs_and_never_submits():
    report, pool = asyncio.run(_run())
    assert report["result"] == "COMPLETED"
    assert report["executions"] and report["generations_seen"]
    assert report["local_candidates"] == report["proof_adapter_validated"] > 0
    assert report["stratum"]["primary"]["authorized"] is True
    assert pool.submits == []
