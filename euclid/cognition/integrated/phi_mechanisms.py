"""φ / Fibonacci mechanisms as operational search machinery, with neutral twins.

Each mechanism is paired with the conventional method it competes against so
that the ``mathematical_structure`` ablation removes it at the source and the
research programme can measure the difference.  Evidence classes are declared
per mechanism and are *not* upgraded by this module:

* :func:`fibonacci_search` — discrete Fibonacci search for the maximum of a
  strictly unimodal sequence.  Its minimax optimality among sequential
  comparison methods is a known theorem (Kiefer, 1953).  Evidence class:
  ``known-theorem-operationalised``.  Neutral twins: :func:`ternary_search`,
  :func:`difference_bisection`.
* :func:`golden_weyl_points` — golden-ratio Kronecker sequence for anytime
  coverage (three-gap theorem).  Evidence class: ``exploratory``.  Neutral
  twin: :func:`grid_points`.
* :func:`fibonacci_schedule` — Fibonacci depth bounds for iterative
  deepening.  Evidence class: ``exploratory``; the expectation from tree
  search theory is *no* advantage over unit increments for exponential trees,
  and the programme reports whatever it measures.

Exact Fibonacci integers are computed locally (no float), so the module adds
no dependency to the EUCLID package.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

from ..worlds.mechanisms import Mechanism, State

PHI = (1.0 + 5.0 ** 0.5) / 2.0

EVIDENCE_CLASS = {
    "fibonacci_search": "known-theorem-operationalised",
    "golden_weyl_points": "exploratory",
    "fibonacci_schedule": "exploratory",
}


def fibonacci_numbers(limit: int) -> list[int]:
    """Exact ``F_0 .. F_k`` with ``F_k >= limit`` (``F_0 = 0, F_1 = 1``)."""
    fib = [0, 1]
    while fib[-1] < limit:
        fib.append(fib[-1] + fib[-2])
    return fib


@dataclass
class SearchTrace:
    method: str
    best: int
    evaluations: int
    evaluated: dict[int, float] = field(default_factory=dict)
    exhausted: bool = False
    unimodal_violation: bool = False

    def to_json(self) -> dict:
        return {
            "method": self.method,
            "best": self.best,
            "evaluations": self.evaluations,
            "exhausted": self.exhausted,
            "unimodal_violation": self.unimodal_violation,
            "evaluated": {str(k): v for k, v in sorted(self.evaluated.items())},
        }


class _Oracle:
    def __init__(self, evaluate: Callable[[int], float], size: int, budget: int,
                 known: Mapping[int, float] | None = None) -> None:
        self.evaluate = evaluate
        self.size = size
        self.budget = budget
        self.values: dict[int, float] = dict(known or {})
        self.used = 0

    def __call__(self, x: int) -> float:
        if x < 0 or x >= self.size:
            return float("-inf")
        if x not in self.values:
            if self.used >= self.budget:
                raise StopIteration
            self.used += 1
            self.values[x] = float(self.evaluate(x))
        return self.values[x]

    def best(self, default: int) -> int:
        if not self.values:
            return default
        return max(self.values, key=lambda k: (self.values[k], -k))


def unimodal_violation(values: Mapping[int, float]) -> bool:
    """True when sampled values contain an interior strict local minimum."""
    ordered = [values[k] for k in sorted(values)]
    falling = False
    for left, right in zip(ordered, ordered[1:]):
        if right < left:
            falling = True
        elif right > left and falling:
            return True
    return False


def fibonacci_search(
    evaluate: Callable[[int], float],
    size: int,
    budget: int,
    *,
    lo: int = 0,
    hi: int | None = None,
    known: Mapping[int, float] | None = None,
) -> SearchTrace:
    """Discrete Fibonacci search for the argmax of a unimodal sequence.

    The open interval ``(a, a + F_k)`` holds the candidates; each step keeps
    one interior probe, so every iteration after the first costs exactly one
    evaluation.  Points outside ``[lo, hi]`` evaluate to ``-inf`` for free.
    """
    hi = size - 1 if hi is None else hi
    width = hi - lo + 1
    oracle = _Oracle(
        lambda x: evaluate(x), size, budget, known,
    )

    def value(x: int) -> float:
        return oracle(x) if lo <= x <= hi else float("-inf")

    fib = fibonacci_numbers(width + 1)
    k = len(fib) - 1
    a = lo - 1
    exhausted = False
    try:
        while k >= 4:
            x1 = a + fib[k - 2]
            x2 = a + fib[k - 1]
            if value(x1) < value(x2):
                a = x1
            k -= 1
        best = a + 1
    except StopIteration:
        exhausted = True
        best = oracle.best(a + 1)
    best = min(max(best, lo), hi)
    return SearchTrace("fibonacci", best, oracle.used, dict(oracle.values), exhausted,
                       unimodal_violation(oracle.values))


def ternary_search(
    evaluate: Callable[[int], float], size: int, budget: int,
    *, lo: int = 0, hi: int | None = None, known: Mapping[int, float] | None = None,
) -> SearchTrace:
    """Conventional ternary search: two fresh evaluations per iteration."""
    hi = size - 1 if hi is None else hi
    oracle = _Oracle(evaluate, size, budget, known)
    exhausted = False
    try:
        while hi - lo > 2:
            third = (hi - lo) // 3
            m1, m2 = lo + third, hi - third
            if oracle(m1) < oracle(m2):
                lo = m1 + 1
            else:
                hi = m2 - 1 if oracle(m1) > oracle(m2) else m2
        best = max(range(lo, hi + 1), key=lambda x: (oracle(x), -x))
    except StopIteration:
        exhausted = True
        best = oracle.best((lo + hi) // 2)
    return SearchTrace("ternary", best, oracle.used, dict(oracle.values), exhausted,
                       unimodal_violation(oracle.values))


def difference_bisection(
    evaluate: Callable[[int], float], size: int, budget: int,
    *, lo: int = 0, hi: int | None = None, known: Mapping[int, float] | None = None,
) -> SearchTrace:
    """Bisection on the discrete derivative: compare ``f(m)`` with ``f(m+1)``."""
    hi = size - 1 if hi is None else hi
    oracle = _Oracle(evaluate, size, budget, known)
    exhausted = False
    try:
        while lo < hi:
            mid = (lo + hi) // 2
            if oracle(mid) < oracle(mid + 1):
                lo = mid + 1
            else:
                hi = mid
        best = lo
    except StopIteration:
        exhausted = True
        best = oracle.best((lo + hi) // 2)
    return SearchTrace("difference-bisection", best, oracle.used, dict(oracle.values),
                       exhausted, unimodal_violation(oracle.values))


def golden_weyl_points(count: int, size: int, *, offset: float = 0.5) -> list[int]:
    """First ``count`` distinct points of the golden Kronecker sequence on [0, size)."""
    points: list[int] = []
    index = 0
    while len(points) < min(count, size):
        x = int(((offset + index / PHI) % 1.0) * size)
        if x not in points:
            points.append(x)
        index += 1
    return points


def grid_points(count: int, size: int) -> list[int]:
    """Evenly spaced points (the neutral coverage baseline when ``count`` is known)."""
    count = min(count, size)
    if count <= 0:
        return []
    step = size / count
    return sorted({min(size - 1, int(step * (i + 0.5))) for i in range(count)})


def explore_then_refine(
    evaluate: Callable[[int], float],
    size: int,
    budget: int,
    *,
    exploration: int,
    golden: bool = True,
    known: Mapping[int, float] | None = None,
) -> SearchTrace:
    """Global coverage pass, then local Fibonacci/ternary refinement.

    Robust to bimodality at the price of exploration evaluations.  ``golden``
    selects the φ pair (Weyl coverage + Fibonacci refinement) versus the
    neutral pair (grid coverage + ternary refinement).
    """
    points = golden_weyl_points(exploration, size) if golden else grid_points(exploration, size)
    oracle = _Oracle(evaluate, size, budget, known)
    try:
        for x in points:
            oracle(x)
    except StopIteration:
        return SearchTrace("explore", oracle.best(0), oracle.used, dict(oracle.values), True)
    best = oracle.best(0)
    sampled = sorted(oracle.values)
    position = sampled.index(best)
    lo = sampled[position - 1] + 1 if position > 0 else 0
    hi = sampled[position + 1] - 1 if position + 1 < len(sampled) else size - 1
    refine = fibonacci_search if golden else ternary_search
    trace = refine(evaluate, size, budget - oracle.used, lo=lo, hi=hi,
                   known={k: v for k, v in oracle.values.items() if lo <= k <= hi})
    merged = dict(oracle.values)
    merged.update(trace.evaluated)
    final = max(merged, key=lambda k: (merged[k], -k)) if merged else trace.best
    chosen = trace.best if merged.get(trace.best, float("-inf")) >= merged.get(final) else final
    return SearchTrace(
        "explore-golden-refine-fibonacci" if golden else "explore-grid-refine-ternary",
        chosen, oracle.used + trace.evaluations, merged, trace.exhausted,
        unimodal_violation(merged),
    )


# -- iterative deepening schedules ------------------------------------------------------------
def linear_schedule(limit: int) -> list[int]:
    return list(range(1, limit + 1))


def doubling_schedule(limit: int) -> list[int]:
    bounds, depth = [], 1
    while depth < limit:
        bounds.append(depth)
        depth *= 2
    return bounds + [limit]


def fibonacci_schedule(limit: int) -> list[int]:
    bounds = sorted({f for f in fibonacci_numbers(limit)[2:] if f < limit})
    return bounds + [limit]


SCHEDULES = {
    "linear": linear_schedule,
    "doubling": doubling_schedule,
    "fibonacci": fibonacci_schedule,
}


def iterative_deepening(
    table: Mapping[str, Mechanism],
    operators: Sequence[str],
    start: State,
    goal: Sequence[tuple[int, int]],
    domains: Sequence[int],
    *,
    schedule: Sequence[int],
    node_budget: int,
) -> dict:
    """Depth-limited DFS under a depth-bound schedule; counts every expansion."""
    expanded = 0

    def dfs(state: State, depth: int, bound: int, path: list[str], seen: dict) -> list[str] | None:
        nonlocal expanded
        if all(state[i] == v for i, v in goal):
            return list(path)
        if depth == bound or expanded >= node_budget:
            return None
        expanded += 1
        for op in operators:
            nxt = table[op].apply(state, domains)
            if seen.get(nxt, 1 << 30) <= depth + 1:
                continue
            seen[nxt] = depth + 1
            path.append(op)
            found = dfs(nxt, depth + 1, bound, path, seen)
            path.pop()
            if found is not None:
                return found
        return None

    for bound in schedule:
        found = dfs(tuple(start), 0, bound, [], {tuple(start): 0})
        if found is not None:
            return {"program": found, "length": len(found), "expanded": expanded,
                    "bound": bound, "exhausted": False}
        if expanded >= node_budget:
            break
    return {"program": None, "length": None, "expanded": expanded, "bound": None,
            "exhausted": expanded >= node_budget}


__all__ = [
    "EVIDENCE_CLASS",
    "PHI",
    "SCHEDULES",
    "SearchTrace",
    "difference_bisection",
    "doubling_schedule",
    "explore_then_refine",
    "fibonacci_numbers",
    "fibonacci_schedule",
    "fibonacci_search",
    "golden_weyl_points",
    "grid_points",
    "iterative_deepening",
    "linear_schedule",
    "ternary_search",
    "unimodal_violation",
]
