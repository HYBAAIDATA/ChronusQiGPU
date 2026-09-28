"""Measured-only model of the mining environment.

The world model answers "what is this machine and this pool actually doing?"
from evidence the miner already records. It never predicts hashes: SHA256d
outcomes are outside its authority. It estimates the quantities an operating
policy needs, each with its own uncertainty and sample count:

* ``bind``  -- rate of Stratum identity changes (any new job drains the
  precomputed plan queue);
* ``clean`` -- rate of work-invalidating events (``clean_jobs``, reconnects),
  which abandon an in-flight window at the next chunk boundary;
* per executed route, the fixed per-window overhead ``o`` and hash rate
  ``H`` in ``elapsed = o + hashes / H``, and the elapsed time each window
  size actually took (so a device the line cannot describe, one that slows
  as a window runs, is still judged by what it delivers). When the device reports kernel time
  the split is measured directly; otherwise it is fitted by discounted least
  squares, which needs windows of different sizes to separate ``o`` from
  ``H`` (see ``RouteModel.identifiable``);
* plan build latency: a smoothed mean, the all-time worst case, and the
  90th percentile of the most recent builds (so one stall does not set the
  precompute depth forever).

Rates are Gamma posteriors over exposure time with exponential forgetting, so
the model follows a pool whose behaviour drifts. Every estimate reports
``None`` until it has evidence; nothing is fabricated.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from .search_plan import CompletionState, ExecutionRecord

_Z = {0.5: 0.0, 0.8: 0.8416, 0.9: 1.2816, 0.95: 1.6449}


@dataclass
class GammaRate:
    """Events per second: Gamma(prior + events, prior + exposure) with forgetting."""

    prior_events: float = 1.0
    prior_seconds: float = 600.0
    half_life_s: float = 3600.0
    events: float = 0.0
    exposure_s: float = 0.0
    observed_events: int = 0

    def advance(self, seconds: float) -> None:
        if seconds <= 0:
            return
        decay = 0.5 ** (seconds / self.half_life_s)
        self.events *= decay
        self.exposure_s = self.exposure_s * decay + seconds

    def event(self, count: int = 1) -> None:
        self.events += count
        self.observed_events += count

    @property
    def shape(self) -> float:
        return self.prior_events + self.events

    @property
    def rate(self) -> float:
        return self.prior_seconds + self.exposure_s

    @property
    def mean(self) -> float:
        return self.shape / self.rate

    def quantile(self, p: float) -> float:
        """Wilson-Hilferty approximation of the Gamma quantile."""
        z = _Z.get(p)
        if z is None:
            raise ValueError(f"unsupported quantile {p}")
        a = self.shape
        c = 1.0 / (9.0 * a)
        return a * max(0.0, 1.0 - c + z * math.sqrt(c)) ** 3 / self.rate

    def snapshot(self) -> dict[str, Any]:
        return {
            "per_hour_mean": self.mean * 3600.0,
            "per_hour_p90": self.quantile(0.9) * 3600.0,
            "observed_events": self.observed_events,
            "exposure_s": self.exposure_s,
        }


@dataclass
class RouteModel:
    """``elapsed = overhead + hashes / hash_rate`` for one executed route."""

    forgetting: float = 0.995
    direct_samples: int = 0
    fit_samples: int = 0
    # Discounted sufficient statistics for least squares on (hashes, elapsed).
    _w: float = 0.0
    _h: float = 0.0
    _hh: float = 0.0
    _y: float = 0.0
    _hy: float = 0.0
    # Discounted direct measurements when kernel time is reported.
    _d_w: float = 0.0
    _d_overhead: float = 0.0
    _d_hashes: float = 0.0
    _d_kernel: float = 0.0
    # Window size -> [discounted count, discounted elapsed sum, samples].
    rungs: dict = field(default_factory=dict)

    def observe(self, hashes: int, elapsed_s: float, kernel_s: float) -> None:
        if hashes <= 0 or elapsed_s <= 0:
            return
        f = self.forgetting
        if 0 < kernel_s <= elapsed_s:
            self._d_w = self._d_w * f + 1.0
            self._d_overhead = self._d_overhead * f + (elapsed_s - kernel_s)
            self._d_hashes = self._d_hashes * f + hashes
            self._d_kernel = self._d_kernel * f + kernel_s
            self.direct_samples += 1
        self._w = self._w * f + 1.0
        self._h = self._h * f + hashes
        self._hh = self._hh * f + hashes * hashes
        self._y = self._y * f + elapsed_s
        self._hy = self._hy * f + hashes * elapsed_s
        self.fit_samples += 1
        rung = self.rungs.setdefault(int(hashes), [0.0, 0.0, 0])
        rung[0] = rung[0] * f + 1.0
        rung[1] = rung[1] * f + elapsed_s
        rung[2] += 1
        if len(self.rungs) > _MAX_RUNGS:  # forget the least-evidenced size
            del self.rungs[min(self.rungs, key=lambda k: self.rungs[k][0])]

    def measured_elapsed(self, window: int, min_samples: int = 3) -> float | None:
        """Mean elapsed of windows of exactly this size, once measured enough."""
        rung = self.rungs.get(int(window))
        if rung is None or rung[2] < min_samples or rung[0] <= 0:
            return None
        return rung[1] / rung[0]

    def misfit(self, min_samples: int = 3) -> float:
        """Largest relative gap between the line and a measured window size.

        Near zero when ``elapsed = o + hashes / H`` describes the device; large
        when it cannot (a rate that sags within a window bends the curve, and
        the fitted overhead is then meaningless, often clamped to zero).
        """
        estimate = self.estimate()
        if estimate is None:
            return 0.0
        overhead, per_hash = estimate
        worst = 0.0
        for hashes in self.rungs:
            measured = self.measured_elapsed(hashes, min_samples)
            predicted = overhead + hashes * per_hash
            if measured is not None and predicted > 0:
                worst = max(worst, abs(measured / predicted - 1.0))
        return worst

    @property
    def _spread(self) -> float:
        """Coefficient of variation of window sizes seen (fit identifiability)."""
        if self._w <= 0 or self._h <= 0:
            return 0.0
        mean = self._h / self._w
        var = max(0.0, self._hh / self._w - mean * mean)
        return math.sqrt(var) / mean

    @property
    def identifiable(self) -> bool:
        # The slope's standard error scales with 1 / (spread * sqrt(n)), so a
        # small spread over many samples identifies it as well as a large one.
        n = self._w
        return self.direct_samples >= 3 or (
            self.fit_samples >= 16 and self._spread * math.sqrt(n) >= 0.5
        )

    def estimate(self) -> tuple[float, float] | None:
        """(overhead_s, seconds_per_hash) or None when not identifiable."""
        if self.direct_samples >= 3 and self._d_hashes > 0 and self._d_kernel > 0:
            return self._d_overhead / self._d_w, self._d_kernel / self._d_hashes
        if not self.identifiable:
            return None
        det = self._w * self._hh - self._h * self._h
        if det <= 0:
            return None
        slope = (self._w * self._hy - self._h * self._y) / det
        intercept = (self._y - slope * self._h) / self._w
        if slope <= 0:
            return None
        return max(0.0, intercept), slope

    def snapshot(self) -> dict[str, Any]:
        est = self.estimate()
        return {
            "overhead_ms": None if est is None else est[0] * 1e3,
            "hash_rate_hs": None if est is None else 1.0 / est[1],
            "method": (
                "direct"
                if self.direct_samples >= 3
                else "fit" if est is not None else "insufficient_evidence"
            ),
            "direct_samples": self.direct_samples,
            "fit_samples": self.fit_samples,
            "window_spread": round(self._spread, 4),
            "measured_windows": sum(1 for r in self.rungs.values() if r[2] >= 3),
            "misfit": round(self.misfit(), 4),
        }


@dataclass
class MiningWorldModel:
    bind: GammaRate = field(default_factory=lambda: GammaRate(prior_seconds=120.0))
    clean: GammaRate = field(default_factory=GammaRate)
    routes: dict[str, RouteModel] = field(default_factory=dict)
    plan_latency_s: float | None = None
    plan_latency_max_s: float = 0.0
    plan_samples: int = 0
    plan_latency_recent: deque = field(default_factory=lambda: deque(maxlen=64))
    completions: dict[str, int] = field(default_factory=dict)
    _last_at: float | None = None

    # -- evidence ---------------------------------------------------------

    def tick(self, now: float) -> None:
        """Advance exposure time; call with a monotonic clock."""
        if self._last_at is not None and now > self._last_at:
            dt = now - self._last_at
            self.bind.advance(dt)
            self.clean.advance(dt)
        self._last_at = now

    def observe_bind(self, now: float, *, clean_jobs: bool, new_session: bool = False) -> None:
        self.tick(now)
        self.bind.event()
        if clean_jobs or new_session:
            self.clean.event()

    def observe_execution(self, record: ExecutionRecord) -> None:
        state = record.completion_state.value
        self.completions[state] = self.completions.get(state, 0) + 1
        if record.completion_state in (CompletionState.INVALIDATED,):
            return
        route = record.executed_route or record.device_used or "unknown"
        model = self.routes.setdefault(route, RouteModel())
        model.observe(record.hash_count, record.elapsed_seconds, record.kernel_ms / 1e3)

    def observe_plan_latency(self, seconds: float) -> None:
        if seconds < 0:
            return
        self.plan_samples += 1
        self.plan_latency_recent.append(seconds)
        self.plan_latency_max_s = max(self.plan_latency_max_s, seconds)
        if self.plan_latency_s is None:
            self.plan_latency_s = seconds
        else:
            self.plan_latency_s = 0.9 * self.plan_latency_s + 0.1 * seconds

    # -- queries ----------------------------------------------------------

    def route(self, name: str) -> RouteModel | None:
        return self.routes.get(name)

    def plan_latency_quantile(self, p: float = 0.9) -> float | None:
        """Nearest-rank ``p`` quantile of the recent plan build latencies."""
        if not self.plan_latency_recent:
            return None
        ordered = sorted(self.plan_latency_recent)
        return ordered[max(0, math.ceil(p * len(ordered)) - 1)]

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema": "pythia.world/1",
            "bind_rate": self.bind.snapshot(),
            "invalidation_rate": self.clean.snapshot(),
            "routes": {name: model.snapshot() for name, model in sorted(self.routes.items())},
            "plan_latency_ms": None if self.plan_latency_s is None else self.plan_latency_s * 1e3,
            "plan_latency_max_ms": self.plan_latency_max_s * 1e3 if self.plan_samples else None,
            "plan_latency_p90_ms": (
                None if not self.plan_latency_recent else self.plan_latency_quantile(0.9) * 1e3
            ),
            "completions": dict(self.completions),
        }

    # -- memory -----------------------------------------------------------

    def export_state(self) -> dict[str, Any]:
        def rate(r: GammaRate) -> dict[str, float]:
            return {"events": r.events, "exposure_s": r.exposure_s, "observed": r.observed_events}

        return {
            "schema": "pythia.world.state/1",
            "bind": rate(self.bind),
            "clean": rate(self.clean),
            "routes": {
                name: {
                    **{k: getattr(m, k) for k in _ROUTE_STATE},
                    "rungs": {str(k): list(v) for k, v in m.rungs.items()},
                }
                for name, m in self.routes.items()
            },
            "plan_latency_s": self.plan_latency_s,
            "plan_latency_max_s": self.plan_latency_max_s,
            "plan_samples": self.plan_samples,
            "plan_latency_recent": list(self.plan_latency_recent),
        }

    def import_state(self, state: dict[str, Any]) -> None:
        if state.get("schema") != "pythia.world.state/1":
            raise ValueError("unsupported world-model state schema")
        for name in ("bind", "clean"):
            raw = state[name]
            target: GammaRate = getattr(self, name)
            target.events = float(raw["events"])
            target.exposure_s = float(raw["exposure_s"])
            target.observed_events = int(raw["observed"])
        self.routes = {}
        for name, raw in state["routes"].items():
            model = RouteModel()
            for key in _ROUTE_STATE:
                setattr(model, key, type(getattr(model, key))(raw[key]))
            model.rungs = {
                int(k): [float(v[0]), float(v[1]), int(v[2])]
                for k, v in (raw.get("rungs") or {}).items()
            }
            self.routes[str(name)] = model
        latency = state.get("plan_latency_s")
        self.plan_latency_s = None if latency is None else float(latency)
        self.plan_latency_max_s = float(state.get("plan_latency_max_s", 0.0))
        self.plan_samples = int(state.get("plan_samples", 0))
        self.plan_latency_recent.clear()
        self.plan_latency_recent.extend(float(x) for x in state.get("plan_latency_recent", ()))


_MAX_RUNGS = 64

_ROUTE_STATE = (
    "direct_samples",
    "fit_samples",
    "_w",
    "_h",
    "_hh",
    "_y",
    "_hy",
    "_d_w",
    "_d_overhead",
    "_d_hashes",
    "_d_kernel",
)
