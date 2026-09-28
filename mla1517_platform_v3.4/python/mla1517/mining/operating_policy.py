"""Operating policy: HOW MUCH work per window and how far to plan ahead.

Decides only the plan window and lookahead depth from the ``MiningWorldModel``.
It never touches SHA256d, targets, shares or pool outcomes.

Window. Each window costs a fixed overhead ``o`` (plan, lease, launch,
recheck) on top of hashing time ``T = window / H``. A work-invalidating event
arriving during hashing wastes, on average, half of the hashing that runs
before the router's next freshness check, which happens between chunks of at
most ``chunk_cap`` nonces. Per unit of time the expected loss is therefore

    J(T) = o / (o + T)  +  lambda * min(T, T_chunk) / 2

and it is linear in the invalidation rate ``lambda``, so using the posterior
mean of ``lambda`` is Bayes-optimal. Candidates are the Lucas ladder windows
(whole 32-lane epochs) inside the caller's bounds; the policy picks the
argmin of ``J`` and reports every term.

Lookahead (precompute depth). A queued plan is rebuilt ``l`` seconds after
the executor takes the one before it, so with ``d`` plans queued the executor
waits ``max(0, l90 - d * W)`` per window (``l90``: 90th percentile of recent
build latencies; ``W = o + T``). Every new job drains the queue: at job churn
``lambda_b`` the ``d`` queued plans, each costing the mean build time, are
discarded ``lambda_b * W`` times per window. The depth minimises

    C(d) = max(0, l90 - d * W)  +  lambda_b * W * d * l_mean

so job churn sets the precompute depth. One more plan saves at most ``W`` of
waiting and costs ``lambda_b * W * l_mean`` of discarded planning: depth
beyond the wait-free minimum ``ceil(l90 / W)`` is never worth it, and even
that minimum is cut back once jobs arrive about as often as a plan takes to
build (``lambda_b * l_mean`` near 1).

Precedence: recovery (Salamander) > caller bounds (thermal de-rate, lease
space) > missing evidence (legacy window, legacy lookahead) > model. When the
route's overhead and hash rate cannot yet be separated, the policy asks for a
probe window on a neighbouring ladder stop at a bounded rate: an intervention
that makes the model identifiable, reported as such.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .world_model import MiningWorldModel

_PROBE_EVERY = 8


def lucas_ladder(max_window: int, lanes: int) -> list[int]:
    """Lucas numbers rounded down to whole lane epochs, within ``[lanes, max_window]``."""
    out: set[int] = set()
    a, b = 2, 1
    while b <= max_window:
        w = b - b % lanes
        if w >= lanes:
            out.add(w)
        a, b = b, a + b
    cap = max_window - max_window % lanes
    if cap >= lanes:
        out.add(cap)
    return sorted(out)


def precompute_cost(
    depth: int, window_s: float, latency_q_s: float, latency_mean_s: float, churn: float
) -> tuple[float, float, float]:
    """(total, waiting, discarded) seconds lost per window with ``depth`` plans queued."""
    waiting = max(0.0, latency_q_s - depth * window_s)
    discarded = churn * window_s * depth * latency_mean_s
    return waiting + discarded, waiting, discarded


def expected_loss(
    window: int, overhead_s: float, sec_per_hash: float, rate: float, chunk_cap: int
) -> tuple[float, float, float]:
    """(total, overhead_fraction, stale_fraction) per unit time for ``window``."""
    hashing = window * sec_per_hash
    chunk = min(window, chunk_cap) * sec_per_hash
    overhead = overhead_s / (overhead_s + hashing) if overhead_s + hashing > 0 else 1.0
    stale = rate * chunk / 2.0
    return overhead + stale, overhead, stale


@dataclass(frozen=True)
class PolicyContext:
    route: str
    lanes: int
    max_window: int
    legacy_window: int
    legacy_lookahead: int
    capacity: int
    chunk_cap: int
    recovery_active: bool = False
    derate_cap: int | None = None
    # Homeostatic envelope: no window may hash longer than this, so recovery
    # commands and new jobs are never stuck behind one huge window.
    max_window_seconds: float | None = None


@dataclass(frozen=True)
class PolicyDecision:
    window: int
    lookahead: int
    source: str  # "model" | "probe" | "legacy" | "hold"
    reason: str
    expected: dict[str, float] = field(default_factory=dict)
    candidates: tuple[dict[str, Any], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "window": self.window,
            "lookahead": self.lookahead,
            "source": self.source,
            "reason": self.reason,
            "expected": dict(self.expected),
        }


class OperatingPolicy:
    def __init__(self, world: MiningWorldModel) -> None:
        self.world = world
        self.decisions = 0
        self.last: PolicyDecision | None = None

    def _bounded(self, window: int, ctx: PolicyContext) -> int:
        upper = ctx.max_window if ctx.derate_cap is None else min(ctx.max_window, ctx.derate_cap)
        window = max(ctx.lanes, min(window, upper))
        return window - window % ctx.lanes

    def decide(self, ctx: PolicyContext) -> PolicyDecision:
        self.decisions += 1
        legacy = self._bounded(ctx.legacy_window, ctx)
        if ctx.recovery_active:
            return self._keep(
                PolicyDecision(legacy, ctx.legacy_lookahead, "hold", "recovery active")
            )
        route = self.world.route(ctx.route)
        estimate = route.estimate() if route is not None else None
        if estimate is None:
            if route is not None and route.fit_samples >= 4 and self.decisions % _PROBE_EVERY == 0:
                probe = self._probe_window(legacy, ctx)
                if probe != legacy:
                    return self._keep(
                        PolicyDecision(
                            probe,
                            ctx.legacy_lookahead,
                            "probe",
                            "overhead and hash rate not yet separable; probing window size",
                        )
                    )
            return self._keep(
                PolicyDecision(
                    legacy,
                    ctx.legacy_lookahead,
                    "legacy",
                    f"insufficient evidence for route {ctx.route!r}",
                )
            )
        overhead_s, sec_per_hash = estimate
        rate = self.world.clean.mean
        upper = ctx.max_window if ctx.derate_cap is None else min(ctx.max_window, ctx.derate_cap)
        ladder = lucas_ladder(upper, ctx.lanes) or [legacy]
        if ctx.max_window_seconds is not None:
            within = [w for w in ladder if w * sec_per_hash <= ctx.max_window_seconds]
            ladder = within or ladder[:1]
        scored = []
        for w in ladder:
            total, o_frac, s_frac = expected_loss(w, overhead_s, sec_per_hash, rate, ctx.chunk_cap)
            scored.append({"window": w, "loss": total, "overhead": o_frac, "stale": s_frac})
        best = min(scored, key=lambda c: (c["loss"], -c["window"]))
        window = best["window"]
        window_s = overhead_s + window * sec_per_hash
        latency_q = self.world.plan_latency_quantile(0.9)
        churn = self.world.bind.mean
        precompute: dict[str, float] = {}
        if latency_q is not None and window_s > 0:
            latency_mean = self.world.plan_latency_s or 0.0
            costs = [
                (precompute_cost(d, window_s, latency_q, latency_mean, churn), d)
                for d in range(1, max(1, ctx.capacity) + 1)
            ]
            (_, waiting, discarded), lookahead = min(costs, key=lambda c: (c[0][0], c[1]))
            precompute = {
                "precompute_wait_ms": waiting * 1e3,
                "precompute_discard_ms": discarded * 1e3,
                "job_churn_per_hour": churn * 3600.0,
            }
        else:
            lookahead = ctx.legacy_lookahead
        lookahead = max(1, min(lookahead, ctx.capacity))
        legacy_loss = expected_loss(legacy, overhead_s, sec_per_hash, rate, ctx.chunk_cap)[0]
        depth_reason = (
            f"; depth {lookahead}: wait {precompute['precompute_wait_ms']:.3f} ms, "
            f"discarded planning {precompute['precompute_discard_ms']:.4f} ms per window"
            if precompute
            else "; depth: no plan latency measured yet"
        )
        return self._keep(
            PolicyDecision(
                window,
                lookahead,
                "model",
                (
                    f"min expected loss {best['loss']:.4f} "
                    f"(overhead {best['overhead']:.4f}, stale {best['stale']:.6f}) "
                    f"vs legacy {legacy_loss:.4f}{depth_reason}"
                ),
                expected={
                    "loss": best["loss"],
                    "overhead_fraction": best["overhead"],
                    "stale_fraction": best["stale"],
                    "legacy_loss": legacy_loss,
                    "overhead_ms": overhead_s * 1e3,
                    "hash_rate_hs": 1.0 / sec_per_hash,
                    "invalidations_per_hour": rate * 3600.0,
                    **precompute,
                },
                candidates=tuple(scored),
            )
        )

    def _probe_window(self, legacy: int, ctx: PolicyContext) -> int:
        ladder = lucas_ladder(
            ctx.max_window if ctx.derate_cap is None else min(ctx.max_window, ctx.derate_cap),
            ctx.lanes,
        )
        if legacy not in ladder:
            return legacy
        # Probe upward when the ladder allows: a larger window also pays less
        # overhead, so the intervention costs least where overhead dominates.
        i = ladder.index(legacy)
        if i + 1 < len(ladder):
            return ladder[i + 1]
        return ladder[i - 1] if i > 0 else legacy

    def _keep(self, decision: PolicyDecision) -> PolicyDecision:
        self.last = decision
        return decision
