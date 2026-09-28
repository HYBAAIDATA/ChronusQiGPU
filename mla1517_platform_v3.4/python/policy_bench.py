"""Seeded simulator: learned operating policy vs the legacy fixed window.

Simulates the execution loop with the real ``MiningWorldModel``,
``OperatingPolicy`` and ``LossLedger``. Each window pays a fixed overhead,
then hashes in chunks of at most ``chunk_cap``; a work-invalidating event
(Poisson, rate ``lam``) wastes the rest of the chunk it lands in and abandons
the window, exactly like the router's between-chunk freshness guard. The
model starts empty and learns online from the records it produces, as it
would in production.

Ground truth is exact: ``useful`` counts only hashes done on work that was
still valid. It measures operating efficiency (how much of the device's time
became valid hashing), never share luck.

Usage:  python policy_bench.py            # prints the regime table as JSON
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from typing import Any

from mla1517.mining.loss_ledger import LossLedger
from mla1517.mining.operating_policy import OperatingPolicy, PolicyContext
from mla1517.mining.search_plan import CompletionState, ExecutionRecord
from mla1517.mining.world_model import MiningWorldModel

LANES = tuple(range(32))


@dataclass(frozen=True)
class Regime:
    name: str
    route: str
    hash_rate: float
    overhead_s: float
    invalidations_per_hour: float
    chunk_cap: int
    legacy_window: int
    max_window: int
    kernel_timing: bool
    evidence: str


def _record(route: str, window: int, hashes: int, elapsed: float, kernel_s: float, invalid: bool):
    return ExecutionRecord(
        plan_id="sim",
        job_fingerprint="sim",
        policy_id="sim",
        planned_window=window,
        actual_window=hashes,
        device_used=route,
        hash_count=hashes,
        elapsed_seconds=elapsed,
        kernel_ms=kernel_s * 1e3,
        temperature_c=None,
        locally_valid_shares=0,
        pool_accepted=0,
        pool_rejected=0,
        pool_stale=0,
        recovery_event=False,
        lane_order=LANES,
        preferred_face=0,
        requested_route=route,
        executed_route=route,
        completion_state=CompletionState.INVALIDATED if invalid else CompletionState.COMPLETE,
    )


def simulate(regime: Regime, *, mode: str, seconds: float = 600.0, seed: int = 1517) -> dict[str, Any]:
    if mode not in ("legacy", "model"):
        raise ValueError(mode)
    rng = random.Random(seed)
    lam = regime.invalidations_per_hour / 3600.0
    world = MiningWorldModel()
    policy = OperatingPolicy(world)
    ledger = LossLedger()
    t = 0.0
    world.tick(t)
    ledger.start(t)
    next_event = t + rng.expovariate(lam) if lam > 0 else math.inf
    useful = stale = 0.0
    windows = 0
    sources: dict[str, int] = {}
    while t < seconds:
        if mode == "legacy":
            window = regime.legacy_window
            sources["legacy"] = sources.get("legacy", 0) + 1
        else:
            decision = policy.decide(
                PolicyContext(
                    route=regime.route,
                    lanes=32,
                    max_window=regime.max_window,
                    legacy_window=regime.legacy_window,
                    legacy_lookahead=2,
                    capacity=3,
                    chunk_cap=regime.chunk_cap,
                )
            )
            window = decision.window
            sources[decision.source] = sources.get(decision.source, 0) + 1
        started = t
        t += regime.overhead_s * max(0.2, 1.0 + 0.1 * rng.gauss(0.0, 1.0))
        while next_event <= t:  # invalidated before any device time: freshness guard
            world.observe_bind(next_event, clean_jobs=True)
            ledger.observe_bind(next_event)
            next_event += rng.expovariate(lam)
        done, invalid, hashing_s = 0, False, 0.0
        while done < window:
            chunk = min(regime.chunk_cap, window - done)
            dur = chunk / regime.hash_rate
            if next_event < t + dur:
                valid = (next_event - t) * regime.hash_rate
                useful += valid
                stale += chunk - valid
                done += chunk
                hashing_s += dur
                t += dur
                invalid = True
                world.observe_bind(next_event, clean_jobs=True)
                ledger.observe_bind(next_event)
                next_event += rng.expovariate(lam)
                break
            useful += chunk
            done += chunk
            hashing_s += dur
            t += dur
        world.tick(t)
        record = _record(
            regime.route,
            window,
            done,
            t - started,
            hashing_s if regime.kernel_timing else 0.0,
            invalid,
        )
        world.observe_execution(record)
        ledger.observe_execution(record, world, started_at=started)
        windows += 1
    capacity = regime.hash_rate * t
    return {
        "mode": mode,
        "efficiency": useful / capacity,
        "stale_fraction": stale / capacity,
        "overhead_fraction": 1.0 - (useful + stale) / capacity,
        "windows": windows,
        "decision_sources": sources,
        "final_window": window,
        "learned": world.snapshot()["routes"].get(regime.route),
    }


REGIMES = (
    Regime(
        "cpu_mainnet_rung10",
        "cpu_reference",
        88_288.0,
        0.000246,
        6.0,
        1 << 20,
        96,
        96,
        False,
        "hash rate and overhead fitted from 1582 soak executions; cap = lucas(10)",
    ),
    Regime(
        "cpu_mainnet_rung10_ladder_ceiling",
        "cpu_reference",
        88_288.0,
        0.000246,
        6.0,
        1 << 20,
        96,
        15104,
        False,
        "WHAT-IF: needs the solver budget invariant (budget <= lucas(rung)) raised to lucas(20)",
    ),
    Regime(
        "cpu_reconnect_storm",
        "cpu_reference",
        88_288.0,
        0.000246,
        3600.0,
        1 << 20,
        15104,
        15104,
        False,
        "measured CPU route; one invalidation per second (reconnect storm / test pool)",
    ),
    Regime(
        "igpu_mainnet_top_rung",
        "opencl_m32",
        3.0e7,
        0.001,
        6.0,
        1_048_575,
        15104,
        15104,
        True,
        "ASSUMED iGPU figures (30 MH/s, 1 ms per-window overhead); cap = lucas(20)",
    ),
    Regime(
        "igpu_mainnet_extended_ceiling",
        "opencl_m32",
        3.0e7,
        0.001,
        6.0,
        1_048_575,
        15104,
        1 << 26,
        True,
        "WHAT-IF, ASSUMED iGPU figures: needs the lucas(rung) budget invariant extended to 2^26",
    ),
)


def run_all(seconds: float = 600.0, seed: int = 1517) -> list[dict[str, Any]]:
    rows = []
    for regime in REGIMES:
        legacy = simulate(regime, mode="legacy", seconds=seconds, seed=seed)
        model = simulate(regime, mode="model", seconds=seconds, seed=seed)
        rows.append(
            {
                "regime": regime.name,
                "evidence": regime.evidence,
                "legacy_efficiency": round(legacy["efficiency"], 5),
                "model_efficiency": round(model["efficiency"], 5),
                "gain_points": round(100 * (model["efficiency"] - legacy["efficiency"]), 3),
                "model_final_window": model["final_window"],
                "model_decisions": model["decision_sources"],
                "legacy_overhead_fraction": round(legacy["overhead_fraction"], 5),
                "model_overhead_fraction": round(model["overhead_fraction"], 5),
                "legacy_stale_fraction": round(legacy["stale_fraction"], 6),
                "model_stale_fraction": round(model["stale_fraction"], 6),
            }
        )
    return rows


if __name__ == "__main__":
    print(json.dumps(run_all(), indent=1))
