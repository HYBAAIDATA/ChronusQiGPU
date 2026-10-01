"""Soak voyage: the full software (or hardware) voyage under seeded chaos.

Drives the real IntelligentPoolCoordinator, StratumClient and Execution
Router against the scripted local pool for ``--seconds``, injecting job
churn, target changes, block advances, rejected and lost submit responses,
pool disconnects and Salamander recovery pulses. It then checks the
invariants that keep a miner honest and alive:

  * no share is ever submitted twice, and no submission names a stale job;
  * leases, the plan queue and the causal ledger stay bounded;
  * no unexpected exception escapes; liveness gaps are measured, not assumed.

Usage:  python soak_voyage.py --seconds 600 --backend auto --seed 1517
The pool is local; no live pool is contacted.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import time
import tracemalloc
from typing import Any

import mining_runtime
from manifold_pool_coordinator import PoolEndpoint
from chronus.mla1517.mining.coordinator import IntelligentPoolCoordinator
from chronus.mla1517.mining.session import MiningSession
from test_agentic_voyages import FakeChain, FakePool, _job, parent_of_current_job

SHARE_TARGET = "03" + "ff" * 31  # roughly one share per ~85 hashes


class SoakPool(FakePool):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.stale_submits = 0
        self.policy_rng = random.Random(0)

    async def handle(self, reader, writer):  # noqa: D401 - same contract as FakePool
        original = self.submits

        class Recorder(list):
            def append(inner, params):  # noqa: N805
                if params[1] != self.job[0]:
                    self.stale_submits += 1
                roll = self.policy_rng.random()
                self.submit_policy = (
                    "drop" if roll < 0.04 else "reject" if roll < 0.12 else "accept"
                )
                list.append(inner, params)

        if not isinstance(original, Recorder):
            self.submits = Recorder(original)
        await super().handle(reader, writer)

    def disconnect(self) -> None:
        if self._writer is not None:
            self._writer.close()


async def _identity_job(coord: IntelligentPoolCoordinator) -> str | None:
    identity, _ = coord._resolve_work_identity()
    return identity.job_id if identity else None


async def run_soak(seconds: float, *, seed: int = 1517, backend: str = "cpu") -> dict[str, Any]:
    rng = random.Random(seed)
    hasher = mining_runtime._execution_hasher(backend)
    pool = SoakPool(target=SHARE_TARGET, job=_job("soak-0"))
    pool.policy_rng = random.Random(seed + 1)
    server = await asyncio.start_server(pool.handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    chain = FakeChain()
    coord = IntelligentPoolCoordinator(
        [PoolEndpoint("127.0.0.1", port, "soak-pool")],
        username="PYTHIA.001",
        password="x",
        submit_enabled=True,
        mining_session=MiningSession(cooldown_seconds=0),
        chain_observer=chain,
        execution_hasher=hasher,
    )
    tracemalloc.start()
    stats: dict[str, Any] = {
        "seed": seed,
        "backend": getattr(hasher, "backend", None),
        "device": getattr(hasher, "device", None),
        "executions": 0,
        "accepted_returns": 0,
        "reconnects": 0,
        "jobs": 1,
        "block_advances": 0,
        "target_changes": 0,
        "salamander_pulses": 0,
        "connection_errors": 0,
        "unexpected_errors": [],
        "max_queue_depth": 0,
        "max_active_leases": 0,
    }
    precompute = None
    job_counter = 0
    gaps: list[float] = []
    slowest: list[dict[str, Any]] = []
    last_exec = None
    started = time.monotonic()
    mem_start = None
    try:
        await coord.connect_with_failover()
        chain.block_hash = parent_of_current_job(coord)
        precompute = asyncio.create_task(coord._precompute_loop())
        while time.monotonic() - started < seconds:
            iteration_started = time.monotonic()
            action = "none"
            if coord.client is None or not coord.client.connected:
                action = "reconnect"
                if coord.client is not None:
                    await coord.client.close()
                coord.client = None
                await coord.connect_with_failover()
                stats["reconnects"] += 1
                chain.block_hash = parent_of_current_job(coord)
                last_exec = None
            roll = rng.random()
            if roll < 0.03:
                job_counter += 1
                clean = rng.random() < 0.7
                action = "new_job"
                await pool.new_job(_job(f"soak-{job_counter}", clean=clean))
                stats["jobs"] += 1
                for _ in range(200):
                    if await _identity_job(coord) == f"soak-{job_counter}":
                        break
                    await asyncio.sleep(0.005)
                if rng.random() < 0.3:
                    chain.advance_to(parent_of_current_job(coord))
                    stats["block_advances"] += 1
                else:
                    chain.block_hash = parent_of_current_job(coord)
            elif roll < 0.045:
                action = "set_target"
                target = SHARE_TARGET if rng.random() < 0.8 else "00" * 31 + "01"
                await pool.push("mining.set_target", [target])
                stats["target_changes"] += 1
            elif roll < 0.055:
                action = "disconnect"
                pool.disconnect()
            elif roll < 0.065:
                action = "salamander_pulse"
                coord.apply_salamander_mode(
                    "RECOVERING", f"salamander:soak-{stats['salamander_pulses']}"
                )
                await asyncio.sleep(0.02)
                coord.apply_salamander_mode("NORMAL")
                stats["salamander_pulses"] += 1
            coord._last_chain_poll = 0.0
            poll_started = time.monotonic()
            await coord.before_hardware_poll()
            search_started = time.monotonic()
            outcome = "returned"
            try:
                if await coord.search_current_job():
                    stats["accepted_returns"] += 1
            except ConnectionError as exc:
                stats["connection_errors"] += 1
                outcome = f"ConnectionError: {exc}"
            except Exception as exc:  # pragma: no cover - reported, never hidden
                stats["unexpected_errors"].append(repr(exc))
                outcome = repr(exc)
            finished = time.monotonic()
            last = coord.last_execution or {}
            slowest.append(
                {
                    "iteration_s": round(finished - iteration_started, 3),
                    "action": action,
                    "action_s": round(poll_started - iteration_started, 3),
                    "poll_s": round(search_started - poll_started, 3),
                    "search_s": round(finished - search_started, 3),
                    "outcome": outcome,
                    "executed": last.get("executed"),
                    "pool_outcome": last.get("pool_outcome"),
                    "reason": last.get("reason"),
                }
            )
            slowest.sort(key=lambda item: item["iteration_s"], reverse=True)
            del slowest[5:]
            if outcome != "returned":
                continue
            if coord.last_execution and coord.last_execution.get("executed"):
                stats["executions"] += 1
                now = time.monotonic()
                if last_exec is not None:
                    gaps.append(now - last_exec)
                last_exec = now
            stats["max_queue_depth"] = max(stats["max_queue_depth"], coord.agentic.queue_depth())
            leases = coord.agentic.snapshot()["leases"]
            stats["max_active_leases"] = max(
                stats["max_active_leases"], leases["reserved"] + leases["executing"]
            )
            if mem_start is None and stats["executions"] >= 50:
                mem_start = tracemalloc.get_traced_memory()[0]
            await asyncio.sleep(0)
    finally:
        if precompute is not None:
            precompute.cancel()
            try:
                await precompute
            except asyncio.CancelledError:
                pass
        if coord.client is not None:
            await coord.client.close()
        server.close()
        await server.wait_closed()
    mem_end, mem_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    submits = [tuple(p[1:]) for p in pool.submits]
    quality = coord.agentic.snapshot()["quality"]
    hashes = sum((q["execution"]["hashes_per_second_mean"] or 0) for q in quality.values()) / max(
        1, len(quality)
    )
    share_states = [entry.get("state") for entry in coord.session.share_log]
    stats.update(
        {
            "seconds": round(time.monotonic() - started, 1),
            "submits": len(submits),
            "duplicate_submits": len(submits) - len(set(submits)),
            "stale_submits": pool.stale_submits,
            "share_states_in_log": {s: share_states.count(s) for s in set(share_states)},
            "max_gap_s": round(max(gaps), 3) if gaps else None,
            "p99_gap_s": (
                round(sorted(gaps)[int(len(gaps) * 0.99) - 1], 3) if len(gaps) > 100 else None
            ),
            "causal_events_retained": len(coord.causal.events()),
            "plans": {
                k: coord.agentic.snapshot()[k]
                for k in ("plans_created", "plans_consumed", "plans_invalidated", "plans_stale")
            },
            "precompute_waste_ratio": coord.agentic.snapshot()["precompute_waste_ratio"],
            "lookahead": coord.agentic.lookahead,
            "mean_policy_hashes_per_second": round(hashes, 1),
            "memory_bytes": {"after_warmup": mem_start, "end": mem_end, "peak": mem_peak},
            "slowest_iterations": slowest,
            "recovery_mode": coord.recovery.mode,
            "session_state": coord.session.state,
        }
    )
    return stats


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--seed", type=int, default=1517)
    parser.add_argument("--backend", default="cpu", choices=("cpu", "auto", "gpu"))
    args = parser.parse_args()
    result = asyncio.run(run_soak(args.seconds, seed=args.seed, backend=args.backend))
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    _main()
