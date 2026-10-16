"""PYTHIA's discovery worker: experiments on a twin of the live miner.

The Active Discovery Engine (``Intelligence.asi.discovery_engine``) runs the
scientific loop (hypothesis, experiment, surprise, replication) over a
black-box environment. Here the environment is a digital twin of the
miner: the seeded policy simulator (``policy_bench``) parameterised by what
the mining world model has published to the knowledge fabric (route hash
rate, per-window overhead, invalidation rate). The hypotheses are
compositions of operating levers; an experiment's effect is the change in
simulated mining efficiency against the unmodified policy on the same
seeds, so every comparison is paired.

Each replicated, surprising finding is published to the fabric bound to the
world fact it was derived from. When the world model learns something
different, those discoveries decohere and the next campaign runs on the new
world. Findings come from a simulation and say so (evidence "simulated"):
they inform. A finding the live miner can apply is replayed on fresh seeds
(the promotion gate's twin round, ``promotion.candidate``); only a candidate
that then also wins in shadow on live measurements is ever applied.
"""

from __future__ import annotations

import logging
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PLATFORM_DIR = Path(__file__).resolve().parent
_CHRONOS_IGPU = _REPO_ROOT / "packages" / "chronos-one-igpu" / "src"
_PYTHIA_CONSUMER = _REPO_ROOT / "packages" / "pythia-consumer" / "src"
_TURING = _REPO_ROOT / "turing_universal_quantum_computer"
for _p in (str(_PLATFORM_DIR), str(_REPO_ROOT), str(_CHRONOS_IGPU), str(_PYTHIA_CONSUMER), str(_TURING)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from chronus.mla1517.knowledge import Fact, KnowledgeFabric, default_journal_path
from chronus.mla1517.mining.operating_policy import lucas_ladder
from chronus.mla1517.mining.promotion import applicable, judge_twin
from policy_bench import REGIMES, Regime, simulate

LOG = logging.getLogger("pythia.discovery")

REPO_ROOT = Path(__file__).resolve().parents[3]
BASE_REGIME = next(r for r in REGIMES if r.name == "cpu_mainnet_rung10_ladder_ceiling")
L31 = 3_010_349  # the operating intelligence's CPU window ceiling
LEVERS = {
    "envelope_half": "halve the 2 s responsiveness envelope",
    "envelope_double": "double the responsiveness envelope",
    "rung_down": "cap windows one Lucas rung lower",
    "chunk_half": "hash in chunks half as large",
}
CAMPAIGN_EVERY_S = 300.0
# The twin round of the promotion gate replays a finding on seeds the
# campaign never saw: a finding selected as the best of many is flattered
# on the seeds it was selected on (the winner's curse).
TRIAL_SEEDS = 8
TRIAL_FIRST_SEED = 90_001
POLL_S = 30.0


def twin_regime(world: Fact | None) -> tuple[Regime, dict[str, Any]]:
    """The regime to simulate, and where each number came from."""
    routes = (world.value.get("routes") or {}) if world is not None else {}
    learned = {
        name: route
        for name, route in routes.items()
        if route.get("hash_rate_hs") and route.get("overhead_ms") is not None
    }
    if not learned:
        basis = {
            "basis": "declared: the measured CPU route (88 kH/s, 0.246 ms per window)",
            "route": BASE_REGIME.route,
            "hash_rate_hs": BASE_REGIME.hash_rate,
            "overhead_ms": round(BASE_REGIME.overhead_s * 1e3, 6),
            "invalidations_per_hour": BASE_REGIME.invalidations_per_hour,
        }
        return replace(BASE_REGIME, max_window=L31), basis
    name, route = max(learned.items(), key=lambda item: item[1]["hash_rate_hs"])
    per_hour = world.value.get("invalidations_per_hour") or BASE_REGIME.invalidations_per_hour
    regime = replace(
        BASE_REGIME,
        name=f"twin:{name}",
        route=name,
        hash_rate=float(route["hash_rate_hs"]),
        overhead_s=float(route["overhead_ms"]) / 1e3,
        invalidations_per_hour=float(per_hour),
        max_window=L31,
        kernel_timing=route.get("method") == "direct",
        evidence=f"twin of the live world model, fact {world.fact_id[:12]}",
    )
    basis = {
        "basis": "live world model",
        "route": name,
        "hash_rate_hs": regime.hash_rate,
        "overhead_ms": round(regime.overhead_s * 1e3, 6),
        "invalidations_per_hour": regime.invalidations_per_hour,
    }
    return regime, basis


class PolicyTwin:
    """``environment(levers, state) -> efficiency change`` on paired seeds."""

    def __init__(
        self, regime: Regime, *, seconds: float = 30.0, seeds: int = 5, first_seed: int = 1517
    ) -> None:
        self.regime = regime
        self.seconds = seconds
        self.seeds = seeds
        self.first_seed = first_seed
        self.calls = 0
        self._baseline: dict[int, float] = {}

    def configure(self, levers: list[str]) -> tuple[Regime, float]:
        regime, envelope = self.regime, 2.0
        for lever in levers:
            if lever == "envelope_half":
                envelope *= 0.5
            elif lever == "envelope_double":
                envelope *= 2.0
            elif lever == "rung_down":
                rungs = lucas_ladder(regime.max_window, 32)
                regime = replace(regime, max_window=rungs[-2] if len(rungs) > 1 else rungs[-1])
            elif lever == "chunk_half":
                regime = replace(regime, chunk_cap=max(32, regime.chunk_cap // 2))
            else:
                raise ValueError(f"unknown lever {lever!r}")
        return regime, envelope

    def efficiency(self, regime: Regime, envelope: float, seed: int) -> float:
        result = simulate(
            regime, mode="model", seconds=self.seconds, seed=seed, max_window_seconds=envelope
        )
        return result["efficiency"]

    def __call__(self, levers: list[str], _state: Any = None) -> float:
        seed = self.first_seed + self.calls % self.seeds
        self.calls += 1
        if seed not in self._baseline:
            self._baseline[seed] = self.efficiency(self.regime, 2.0, seed)
        regime, envelope = self.configure(levers)
        return self.efficiency(regime, envelope, seed) - self._baseline[seed]


def _engine(twin: Callable[[list[str], Any], float], levers: dict[str, str], trials: int):
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from Intelligence.asi.compositional_generalization import CompositionalRule
    from Intelligence.asi.discovery_engine import ActiveDiscoveryEngine

    primitives = [
        CompositionalRule(name=name, input_pattern=name, output_pattern=description)
        for name, description in levers.items()
    ]
    return ActiveDiscoveryEngine(
        twin,
        primitives,
        n_trials=trials,
        surprise_threshold=0.01,  # one point of efficiency
        replication_tolerance=0.01,
        experiments_reversible=True,  # a simulation leaves the miner untouched
    )


def campaign_due(
    world_basis: str, stale: bool, last_basis: str | None, since_last_s: float
) -> bool:
    """Run on start; afterwards only when the world moved (or the last
    findings decohered), and never more often than ``CAMPAIGN_EVERY_S``."""
    if last_basis is None:
        return True
    moved = world_basis != last_basis or stale
    return moved and since_last_s >= CAMPAIGN_EVERY_S


def run_campaign(
    fabric: KnowledgeFabric,
    *,
    cycles: int = 30,
    seconds: float = 30.0,
    seeds: int = 5,
    twin: Callable[[list[str], Any], float] | None = None,
    levers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """One campaign on the current world; publishes what replicates.

    ``twin`` and ``levers`` default to the policy twin of the published
    world and its operating levers.
    """
    fabric.sync()
    world = fabric.observe("mining.world")
    regime, basis = twin_regime(world)
    default_twin = twin is None
    if twin is None:
        twin = PolicyTwin(regime, seconds=seconds, seeds=seeds)
    engine = _engine(twin, levers or LEVERS, seeds)
    report = engine.discover(initial_state=None, n_cycles=cycles, max_composition_length=2)
    depends_on = [world] if world is not None else []
    published = []
    for discovery in engine.discoveries:
        composition = "∘".join(engine._expand(discovery.rule_composition))
        fact = fabric.publish(
            "discovery.engine",
            f"discovery.policy.{composition}",
            {
                "levers": engine._expand(discovery.rule_composition),
                "efficiency_change": round(discovery.observed_effect, 5),
                "predicted_change": round(discovery.predicted_effect, 5),
                "surprise": round(discovery.surprise, 5),
                "replications": discovery.replications,
                "twin": basis,
            },
            evidence="simulated",
            depends_on=depends_on,
        )
        published.append(fact.topic)
    candidates = []
    for discovery in engine.discoveries:
        levers = engine._expand(discovery.rule_composition)
        if discovery.observed_effect <= 0 or not applicable(levers):
            continue
        trial_twin = (
            PolicyTwin(regime, seconds=seconds, seeds=TRIAL_SEEDS, first_seed=TRIAL_FIRST_SEED)
            if default_twin
            else twin
        )
        record = judge_twin([trial_twin(levers, None) for _ in range(TRIAL_SEEDS)])
        fabric.publish(
            "discovery.engine",
            "promotion.candidate",
            {"levers": levers, **record, "twin": basis},
            evidence="simulated",
            depends_on=depends_on,
        )
        candidates.append({"levers": levers, "verdict": record["verdict"]})
    # What each lever alone did: the basis every surprise is measured from.
    lever_effects = {
        entry["hypothesis"]: round(entry["observed"], 4)
        for entry in engine.experiment_log
        if len(entry["rules"]) == 1
    }
    summary = {
        "hypotheses_tested": report["hypotheses_tested"],
        "discoveries": report["discoveries"],
        "published": published,
        "promotion_candidates": candidates,
        "lever_effects": lever_effects,
        "twin": basis,
    }
    fabric.publish(
        "discovery.engine",
        "discovery.campaign",
        summary,
        evidence="simulated",
        depends_on=depends_on,
    )
    return summary


def main() -> None:
    from worker_lifecycle import HeartbeatEmitter

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    fabric = KnowledgeFabric(default_journal_path())
    last_basis: str | None = None
    last_campaign = float("-inf")
    with HeartbeatEmitter("discovery") as heartbeat:
        while True:
            fabric.sync()
            world = fabric.observe("mining.world")
            basis = world.fact_id if world is not None else "declared"
            campaign = fabric.observe("discovery.campaign")
            stale = campaign is not None and fabric.stale(campaign)
            if campaign_due(basis, stale, last_basis, time.monotonic() - last_campaign):
                summary = run_campaign(fabric)
                last_basis, last_campaign = basis, time.monotonic()
                heartbeat.report(
                    discoveries=summary["discoveries"],
                    hypotheses_tested=summary["hypotheses_tested"],
                )
                LOG.info(
                    "campaign on %s: %d hypotheses, %d discoveries",
                    summary["twin"]["basis"],
                    summary["hypotheses_tested"],
                    summary["discoveries"],
                )
            time.sleep(POLL_S)


if __name__ == "__main__":
    main()
