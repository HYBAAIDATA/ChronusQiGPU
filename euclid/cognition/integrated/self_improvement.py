"""Self-improving intelligence policy under the propose→sandbox→accept protocol.

EUCLID may propose changes to its own policy parameters — planning breadth,
search exploration, transfer prior strength, strategy-prior backoff — but no
change is exempt from evidence:

``propose → sandbox → evaluate → compare → validate → accept / rollback``

* **propose** — a line search over the parameter's declared range.  With the
  mathematical substrate enabled it is discrete Fibonacci (golden-section)
  search, otherwise a neutral uniform grid with the same evaluation budget;
  the number of sandbox evaluations each method used is recorded.
* **sandbox** — every evaluation runs on a frozen *copy* of the agent's
  knowledge, on the development partition only (never evaluation tasks).
* **compare / validate** — the proposal must beat the current value with a
  paired bootstrap interval excluding zero and must not regress any task
  family by more than the declared tolerance.
* **accept / rollback** — accepted values are written to the knowledge;
  rejected ones leave it untouched.  Both are ledgered.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from ..research.stats import paired_bootstrap
from .phi_mechanisms import fibonacci_search

TUNABLE: dict[str, dict[str, Any]] = {
    "plan_samples": {"values": [1, 2, 3, 4, 5, 6], "policy": "planning breadth"},
    "explore_fraction": {"values": [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5],
                         "policy": "search exploration"},
    "analogy_mass_cap": {"values": [0.3, 0.45, 0.6, 0.75, 0.9, 0.95],
                         "policy": "transfer prior strength"},
    "strategy_prior_weight": {"values": [0.0, 1.0, 2.0, 3.0, 4.0, 6.0],
                              "policy": "strategy-selection backoff"},
}

Evaluator = Callable[[Mapping[str, float]], Sequence[tuple[str, float]]]


@dataclass
class ImprovementRecord:
    parameter: str
    policy: str
    current: float
    proposed: float
    method: str
    sandbox_evaluations: int
    search_trace: dict[str, float] = field(default_factory=dict)
    comparison: dict[str, Any] = field(default_factory=dict)
    family_deltas: dict[str, float] = field(default_factory=dict)
    decision: str = "pending"
    reason: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "parameter": self.parameter, "policy": self.policy, "current": self.current,
            "proposed": self.proposed, "method": self.method,
            "sandbox_evaluations": self.sandbox_evaluations,
            "search_trace": {str(k): v for k, v in self.search_trace.items()},
            "comparison": self.comparison, "family_deltas": self.family_deltas,
            "decision": self.decision, "reason": self.reason,
        }


class PolicySelfImprovement:
    def __init__(self, evaluate: Evaluator, *, golden: bool = True, budget: int = 5,
                 tolerance: float = 0.05, seed: int = 0) -> None:
        self.evaluate = evaluate
        self.golden = bool(golden)
        self.budget = int(budget)
        self.tolerance = float(tolerance)
        self.seed = int(seed)
        self.ledger: list[ImprovementRecord] = []

    def _mean(self, params: Mapping[str, float], cache: dict) -> float:
        key = tuple(sorted(params.items()))
        if key not in cache:
            rows = list(self.evaluate(params))
            cache[key] = (sum(u for _, u in rows) / max(1, len(rows)), rows)
        return cache[key][0]

    def propose(self, name: str, params: Mapping[str, float]) -> tuple[float, int, dict, str]:
        values = TUNABLE[name]["values"]
        cache: dict = {}

        def score(index: int) -> float:
            trial = dict(params)
            trial[name] = values[index]
            return self._mean(trial, cache)

        if self.golden:
            trace = fibonacci_search(score, len(values), self.budget)
            best = values[trace.best]
            evaluated = {values[i]: v for i, v in trace.evaluated.items()}
            used, method = trace.evaluations, "fibonacci-search"
        else:
            count = min(self.budget, len(values))
            step = (len(values) - 1) / max(1, count - 1)
            indices = sorted({round(i * step) for i in range(count)})
            evaluated = {values[i]: score(i) for i in indices}
            best = max(evaluated, key=lambda v: (evaluated[v], -abs(v - params[name])))
            used, method = len(indices), "uniform-grid"
        return best, used, evaluated, method

    def run(self, params: dict[str, float], names: Sequence[str] = tuple(TUNABLE)) -> dict[str, float]:
        """Return the accepted parameters; ``params`` itself is never mutated."""
        accepted = dict(params)
        for name in names:
            proposal, used, trace, method = self.propose(name, accepted)
            record = ImprovementRecord(name, TUNABLE[name]["policy"], accepted[name], proposal,
                                       method, used, trace)
            if proposal == accepted[name]:
                record.decision, record.reason = "no-change", "search kept the current value"
                self.ledger.append(record)
                continue
            baseline = list(self.evaluate(accepted))
            trial_params = dict(accepted)
            trial_params[name] = proposal
            trial = list(self.evaluate(trial_params))
            comparison = paired_bootstrap([u for _, u in trial], [u for _, u in baseline],
                                          seed=self.seed)
            record.comparison = comparison
            families: dict[str, list[float]] = {}
            for (family, new), (_, old) in zip(trial, baseline):
                families.setdefault(family, []).append(new - old)
            record.family_deltas = {f: sum(v) / len(v) for f, v in sorted(families.items())}
            regressed = [f for f, d in record.family_deltas.items() if d < -self.tolerance]
            if comparison["low95"] is not None and comparison["low95"] > 0.0 and not regressed:
                accepted = trial_params
                record.decision = "accepted"
                record.reason = "paired interval excludes zero with no family regression"
            else:
                record.decision = "rolled-back"
                record.reason = (f"families regressed: {regressed}" if regressed
                                 else "improvement not established on development tasks")
            self.ledger.append(record)
        return accepted


__all__ = ["ImprovementRecord", "PolicySelfImprovement", "TUNABLE"]
