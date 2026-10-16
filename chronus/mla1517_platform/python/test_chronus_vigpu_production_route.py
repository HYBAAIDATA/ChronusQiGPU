"""PYTHIA production coordinator -> Chronus Virtual iGPU, end to end (local scripted pool).

Software-execution evidence only: no live pool, no physical device. Everything between
the Stratum client and the evidence snapshot is production code; the execution hasher is
bound through the real BackendRegistry ``chronus`` lane.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PLATFORM_DIR = Path(__file__).resolve().parent
_CHRONOS_IGPU = _REPO_ROOT / "packages" / "chronos-one-igpu" / "src"
_PYTHIA_CONSUMER = _REPO_ROOT / "packages" / "pythia-consumer" / "src"
_TURING = _REPO_ROOT / "turing_universal_quantum_computer"
for _p in (str(_PLATFORM_DIR), str(_REPO_ROOT), str(_CHRONOS_IGPU), str(_PYTHIA_CONSUMER), str(_TURING)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest

from chronus.mla1517.mining.backend_registry import BackendRegistry, BackendUnavailable
from chronus.virtual_igpu.adapters import CPUEmulatorAdapter
from chronus.virtual_igpu.client import ChronusClient
from chronus.virtual_igpu.mining_hasher import ChronusVirtualIGPUHasher
from chronus.virtual_igpu.runtime import RuntimeDaemon
from manifold_pool_coordinator import PoolEndpoint
from chronus.mla1517.mining.geodesic_support import PythiaProductionMiningCoordinator
from chronus.mla1517.mining.hashrate_governor import HashrateGovernor
from chronus.mla1517.mining.pool_chain import PoolChainObserver
from chronus.mla1517.mining.session import MiningSession
from test_agentic_voyages import EASY_TARGET, FakePool, _connected, _job, _served, bip34_coinb1


def _coordinator(port: int, hasher, *, submit_enabled: bool = True):
    coord = PythiaProductionMiningCoordinator(
        [PoolEndpoint("127.0.0.1", port, "vigpu-route")],
        username="coordinator-default",
        password="x",
        submit_enabled=submit_enabled,
        mining_session=MiningSession(cooldown_seconds=0),
        execution_hasher=hasher,
    )
    coord.chain_observer = PoolChainObserver(lambda: coord.client)
    coord.governor = HashrateGovernor(max_network_fraction=None)
    return coord


def _bound_hasher():
    selection = BackendRegistry().select("chronus")
    assert selection.lane == "chronus"
    return selection.hasher


async def _run(hasher, *, tmp_job: str) -> tuple[dict, FakePool]:
    pool = FakePool(target=EASY_TARGET, job=_job(tmp_job, coinb1=bip34_coinb1(900_001)))
    server, port = await _served(pool)
    coord = _coordinator(port, hasher)
    try:
        await _connected(coord, tmp_job)
        coord._last_chain_poll = 0.0
        assert await coord.before_hardware_poll() is True
        await coord.search_current_job()
        return coord.evidence_snapshot(), pool
    finally:
        if coord.client:
            await coord.client.close()
        server.close()
        await server.wait_closed()


def test_production_coordinator_executes_through_chronus_virtual_igpu() -> None:
    hasher = _bound_hasher()
    assert isinstance(hasher, ChronusVirtualIGPUHasher)
    snapshot, pool = asyncio.run(_run(hasher, tmp_job="job-vigpu-route"))

    execution = snapshot["last_execution"]
    assert execution["executed"] is True
    assert execution["candidate_host_verified"] is True
    assert len(pool.submits) == 1
    # The Chronus client actually ran workloads for the plan PYTHIA authorised.
    assert hasher.launches > 0
    assert hasher.last_result["status"] == "ok"
    assert hasher.last_result["receipt"], "no Chronus execution receipt retained"
    assert hasher.last_verification["status"] == "passed"
    assert hasher.last_adapter_kind == "software"
    assert execution["requested_route"] == "chronus_batch"
    assert execution["executed_route"] == "chronus_batch"
    assert execution["route_fallback_reason"] is None
    assert execution["device_backend"] == "chronus_vigpu"


def test_chronus_route_is_recorded_as_software_not_hardware() -> None:
    hasher = _bound_hasher()
    snapshot, _ = asyncio.run(_run(hasher, tmp_job="job-vigpu-evidence"))
    execution = snapshot["last_execution"]
    assert execution["executed_route"] == "chronus_batch"
    assert execution["evidence_class"] == "SOFTWARE_VERIFIED"
    assert execution["device_name"] == "Chronus Virtual iGPU (cpu-emulator)"


class _LyingAdapter(CPUEmulatorAdapter):
    """Claims a winning nonce whose digest it never computed."""

    def _sha256d_scan(self, workload, value, started):
        nonces = list(value["nonces"])
        return self._result(
            workload,
            {
                "hits": [{"nonce": nonces[0], "hash_hex": "00" * 32, "digest_int": 0}],
                "checked": 1,
                "start_nonce": nonces[0],
                "engine": "forged",
            },
            started,
        )


def test_lying_adapter_never_reaches_pythia_as_a_candidate(tmp_path) -> None:
    daemon = RuntimeDaemon(adapters=[_LyingAdapter()], store_dir=tmp_path / "rt")
    hasher = ChronusVirtualIGPUHasher(client=ChronusClient(daemon=daemon))
    with pytest.raises(Exception, match="mismatch|verification_failed"):
        hasher.grind_target_batch(bytes(range(80)), b"\xff" * 32, [5, 6, 7])


def test_unavailable_chronus_lane_fails_closed(monkeypatch) -> None:
    import chronus.mla1517.mining.backend_registry as reg

    def broken():
        return reg.LaneProbe("chronus", False, None, None, 0.0, "forced failure")

    registry = BackendRegistry(probes={reg.BackendLane.CHRONUS: broken})
    with pytest.raises(BackendUnavailable):
        registry.select("chronus")
