"""Promotion gate: a candidate replaces the running policy only after it wins twice.

A self-improving player keeps its current best version until a candidate
beats it in play (Silver et al., AlphaGo Zero, 2017: the evaluator promoted
a new network only after it won enough games against the current best).
Here a candidate is a set of operating levers the discovery worker found in
the twin, and it plays two rounds:

1. **Twin.** Paired seeds in the simulator parameterised by the live world
   model: the same invalidation times for champion and candidate, so each
   seed gives one paired difference in efficiency. The candidate must win an
   exact one-sided sign test at 5% over at least ``MIN_PAIRS`` untied seeds.
   (The discovery worker runs this round: it owns the twin.)
2. **Shadow.** On the live miner, the candidate decides beside the champion
   for every window without acting. Where both chose window sizes the miner
   has measured, each choice is worth its measured valid hashes per second
   of wall time. The decisions are pooled in epochs, each epoch one paired
   result, and the candidate must again win the sign test over the epochs.

Only then are its levers applied. A candidate may only **tighten** the
operator's bounds (a shorter responsiveness envelope, a lower window
ceiling): nothing learned can widen what the operator allowed, and no lever
touches SHA256d, targets or submission.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any

from .operating_policy import OperatingPolicy, PolicyContext, PolicyDecision, lucas_ladder
from .world_model import MiningWorldModel

ALPHA = 0.05
MIN_PAIRS = 6
EPOCH = 64
MAX_EPOCHS = 40

# Levers the live miner can apply, all tightening; the discovery worker's
# other levers ("envelope_double" widens the operator's bound, "chunk_half"
# is the router's chunking, not a policy input) are never promoted.
LIVE_LEVERS = {
    "envelope_half": "halve the responsiveness envelope",
    "rung_down": "cap windows one Lucas rung lower",
}


def sign_test(wins: int, losses: int) -> float:
    """Exact one-sided p-value of at least ``wins`` wins in ``wins + losses``
    fair coin flips: the chance a candidate no better than the champion
    wins this often."""
    n = wins + losses
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(wins, n + 1)) / 2.0**n


def applicable(levers: list[str] | tuple[str, ...]) -> bool:
    return bool(levers) and all(lever in LIVE_LEVERS for lever in levers)


def apply_levers(ctx: PolicyContext, levers: tuple[str, ...]) -> PolicyContext:
    """The context the candidate decides in: the champion's, tightened."""
    for lever in levers:
        if lever == "envelope_half":
            if ctx.max_window_seconds is not None:
                ctx = replace(ctx, max_window_seconds=ctx.max_window_seconds * 0.5)
        elif lever == "rung_down":
            rungs = lucas_ladder(ctx.max_window, ctx.lanes)
            if len(rungs) > 1:
                ctx = replace(ctx, max_window=rungs[-2])
        else:
            raise ValueError(f"lever {lever!r} cannot be applied live")
    return ctx


def judge(wins: int, losses: int) -> str:
    """ "promote" / "reject" / "undecided" for a paired record."""
    if wins + losses < MIN_PAIRS:
        return "undecided"
    if sign_test(wins, losses) < ALPHA:
        return "promote"
    if sign_test(losses, wins) < ALPHA:
        return "reject"
    return "undecided"


def judge_twin(differences: list[float]) -> dict[str, Any]:
    """Round one, on the twin's paired efficiency differences."""
    wins = sum(1 for d in differences if d > 0)
    losses = sum(1 for d in differences if d < 0)
    verdict = judge(wins, losses)
    return {
        "round": "twin",
        "wins": wins,
        "losses": losses,
        "p_value": sign_test(wins, losses),
        "mean_difference": sum(differences) / len(differences) if differences else 0.0,
        "verdict": "shadow" if verdict == "promote" else "rejected",
    }


def measured_valid_rate(
    world: MiningWorldModel, route: str, window: int, chunk_cap: int
) -> float | None:
    """Valid hashes per second of a window size the miner has run, or None."""
    model = world.route(route)
    elapsed = model.measured_elapsed(window) if model is not None else None
    if elapsed is None or elapsed <= 0:
        return None
    rate = world.clean.mean
    return window / elapsed * max(0.0, 1.0 - rate * elapsed * min(window, chunk_cap) / window / 2)


@dataclass
class ShadowTrial:
    """Round two: the candidate decides beside the champion, without acting."""

    levers: tuple[str, ...]
    world: MiningWorldModel
    epoch: int = EPOCH
    max_epochs: int = MAX_EPOCHS

    def __post_init__(self) -> None:
        if not applicable(self.levers):
            raise ValueError(f"not live levers: {self.levers}")
        self.candidate = OperatingPolicy(self.world)
        self.status = "shadow"
        self.decisions = 0
        self.informative = 0
        self.wins = self.losses = 0
        self.epochs = 0
        self._sum = 0.0
        self._n = 0

    def observe(self, ctx: PolicyContext, champion: PolicyDecision) -> None:
        """Score one live decision pair; closes an epoch every ``epoch`` decisions."""
        if self.status != "shadow":
            return
        self.decisions += 1
        mine = self.candidate.decide(apply_levers(ctx, self.levers))
        if mine.window != champion.window:
            ours = measured_valid_rate(self.world, ctx.route, mine.window, ctx.chunk_cap)
            theirs = measured_valid_rate(self.world, ctx.route, champion.window, ctx.chunk_cap)
            if ours is not None and theirs:
                self._sum += ours / theirs - 1.0
                self._n += 1
                self.informative += 1
        if self.decisions % self.epoch:
            return
        if self._n:
            self.epochs += 1
            if self._sum > 0:
                self.wins += 1
            elif self._sum < 0:
                self.losses += 1
        self._sum, self._n = 0.0, 0
        verdict = judge(self.wins, self.losses)
        if verdict == "promote":
            self.status = "promoted"
        elif verdict == "reject" or self.decisions >= self.epoch * self.max_epochs:
            self.status = "rejected"

    def context(self, ctx: PolicyContext) -> PolicyContext:
        """The live context: tightened by the levers only once promoted."""
        return apply_levers(ctx, self.levers) if self.status == "promoted" else ctx

    def snapshot(self) -> dict[str, Any]:
        return {
            "round": "shadow",
            "levers": list(self.levers),
            "status": self.status,
            "decisions": self.decisions,
            "informative_decisions": self.informative,
            "epochs": self.epochs,
            "wins": self.wins,
            "losses": self.losses,
            "p_value": sign_test(self.wins, self.losses),
        }
