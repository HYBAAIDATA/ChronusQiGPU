"""Canonical PYTHIA mining workflow over the real Stratum/coordinator stack.

The pool is local and scripted, so this is software execution evidence rather
than live-pool or physical-device evidence. Everything between the TCP Stratum
client and the evidence snapshot is production code.
"""

from __future__ import annotations

import asyncio

from manifold_pool_coordinator import PoolEndpoint
from chronus.mla1517.mining.geodesic_support import PythiaProductionMiningCoordinator
from chronus.mla1517.mining.hashrate_governor import HashrateGovernor
from chronus.mla1517.mining.pool_chain import PoolChainObserver
from chronus.mla1517.mining.session import MiningSession
from test_agentic_voyages import EASY_TARGET, FakePool, _connected, _job, _served, bip34_coinb1


def _coordinator(port: int, *, submit_enabled: bool = True) -> PythiaProductionMiningCoordinator:
    coord = PythiaProductionMiningCoordinator(
        [PoolEndpoint("127.0.0.1", port, "canonical-test")],
        username="coordinator-default",
        password="x",
        submit_enabled=submit_enabled,
        mining_session=MiningSession(cooldown_seconds=0),
    )
    coord.chain_observer = PoolChainObserver(lambda: coord.client)
    # The fixture target is deliberately easy. Disable only the network-share
    # pacing guard so the test exercises the production search/submission path.
    coord.governor = HashrateGovernor(max_network_fraction=None)
    return coord


async def _poll(coord: PythiaProductionMiningCoordinator) -> bool:
    coord._last_chain_poll = 0.0
    return await coord.before_hardware_poll()


def _role(snapshot: dict, name: str) -> dict:
    roles = snapshot["pythia_agentic_workforce"]["roles"]
    return next(item for item in roles if item["role"] == name)


async def _accepted_share() -> None:
    pool = FakePool(
        target=EASY_TARGET,
        job=_job("job-canonical-accept", coinb1=bip34_coinb1(900_001)),
    )
    server, port = await _served(pool)
    coord = _coordinator(port)
    try:
        await _connected(coord, "job-canonical-accept")
        assert await _poll(coord) is True
        assert await coord.search_current_job() is True
        assert len(pool.submits) == 1

        snapshot = coord.evidence_snapshot()
        search = snapshot["pythia_search_precompute"]
        assert search["architecture_id"] == "pythia_dual32_11d_h4_600_hilbert"
        assert search["state"] == "READY"
        assert search["dual_vertices"] == 600
        assert search["manifold_dimension"] == 11
        assert search["hilbert_qubits"] == 11
        assert _role(snapshot, "physical_execution")["owner"] == "Chronus"
        assert _role(snapshot, "hilbert_walk")["owner"] == "Turing"
        assert _role(snapshot, "healing_and_optimisation")["owner"] == "Salamander"

        execution = snapshot["last_execution"]
        assert execution["executed"] is True
        assert execution["pool_outcome"] == "ACCEPTED"
        assert execution["candidate_host_verified"] is True
        assert execution["chronus107"]["state"] == "POOL_CONFIRMED"
        assert execution["attempts"] > 0
    finally:
        if coord.client:
            await coord.client.close()
        server.close()
        await server.wait_closed()


def test_canonical_workflow_reaches_literal_pool_acceptance() -> None:
    asyncio.run(_accepted_share())


async def _rejected_share() -> None:
    pool = FakePool(
        target=EASY_TARGET,
        job=_job("job-canonical-reject", coinb1=bip34_coinb1(900_001)),
    )
    pool.submit_policy = "reject"
    server, port = await _served(pool)
    coord = _coordinator(port)
    try:
        await _connected(coord, "job-canonical-reject")
        assert await _poll(coord) is True
        assert await coord.search_current_job() is False
        assert len(pool.submits) == 1

        execution = coord.evidence_snapshot()["last_execution"]
        assert execution["pool_outcome"] == "REJECTED"
        assert execution["chronus107"]["state"] != "POOL_CONFIRMED"
    finally:
        if coord.client:
            await coord.client.close()
        server.close()
        await server.wait_closed()


def test_rejection_never_becomes_pool_confirmed() -> None:
    asyncio.run(_rejected_share())


async def _shadow_share() -> None:
    pool = FakePool(
        target=EASY_TARGET,
        job=_job("job-canonical-shadow", coinb1=bip34_coinb1(900_001)),
    )
    server, port = await _served(pool)
    coord = _coordinator(port, submit_enabled=False)
    try:
        await _connected(coord, "job-canonical-shadow")
        assert await _poll(coord) is True
        assert await coord.search_current_job() is False
        assert pool.submits == []
        assert coord.evidence_snapshot()["last_execution"]["pool_outcome"] == "NOT_SUBMITTED"
    finally:
        if coord.client:
            await coord.client.close()
        server.close()
        await server.wait_closed()


def test_shadow_mode_finds_and_verifies_without_network_submission() -> None:
    asyncio.run(_shadow_share())
