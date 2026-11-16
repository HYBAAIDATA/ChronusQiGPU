"""Evidence-first A/B execution for general finite search problems.

Same exact finite objective, same complete domain, different enumeration
order. Records wall-clock observations and oracle counts; NEVER labels
ordering effects quantum advantage. No synthetic benchmark is silently
reported as production measurement. Input provenance is SHA-256 bound.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import json
import platform
from time import perf_counter_ns

from chronus.geodesic.problems import FiniteProblem
from chronus.geodesic.spectral import H4GraphLaplacian


def h4_graph_order(domain_size: int) -> tuple[int, ...]:
    """Exact H4 BFS order across full 120-element blocks; bijective."""
    if type(domain_size) is not int or not 1 <= domain_size <= 4096:
        raise ValueError("benchmark domain must have 1..4096 candidates")
    adj = H4GraphLaplacian.canonical().adjacency
    visited = {0}
    queue = [0]
    for v in queue:
        for u in adj[v]:
            if u not in visited:
                visited.add(u)
                queue.append(u)
    if len(queue) != 120:
        raise AssertionError("H4 crossbar graph disconnected")
    order = tuple(block*120 + v
                  for block in range((domain_size+119)//120)
                  for v in queue if block*120+v < domain_size)
    if len(order) != domain_size or len(set(order)) != domain_size:
        raise AssertionError("H4 enumeration lost or duplicated candidates")
    return order


@dataclass(frozen=True)
class Trial:
    algorithm: str
    duration_ns: int
    oracle_calls: int
    first_minimum_oracle_call: int
    objective_minimum: Fraction
    argmin: tuple[int, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "algorithm":self.algorithm,
            "duration_ns":self.duration_ns,
            "oracle_calls":self.oracle_calls,
            "first_minimum_oracle_call":self.first_minimum_oracle_call,
            "objective_minimum":str(self.objective_minimum),
            "argmin":list(self.argmin),
        }


def run_trial(problem: FiniteProblem, order: tuple[int, ...],
              algorithm: str) -> Trial:
    """Evaluate ALL candidates and report exact minima + observed timings."""
    n = problem.domain_size
    if (len(order) != n or len(set(order)) != n or
            any(type(x) is not int or not 0 <= x < n for x in order)):
        raise ValueError("trial must visit each candidate exactly once")
    started = perf_counter_ns()
    best: Fraction | None = None
    winners: list[int] = []
    first_at = 0
    for calls, candidate in enumerate(order, 1):
        score = Fraction(problem.objective(candidate))
        if best is None or score < best:
            best = score
            winners = [candidate]
            first_at = calls
        elif score == best:
            winners.append(candidate)
    duration = perf_counter_ns() - started
    assert best is not None
    return Trial(algorithm,duration,n,first_at,best,tuple(sorted(winners)))


def benchmark(problem: FiniteProblem, repetitions: int = 3,
              git_commit: str = "UNAVAILABLE",
              input_classification: str = "USER_SUPPLIED_OR_TEST_FIXTURE"
              ) -> dict[str, object]:
    if type(repetitions) is not int or not 1 <= repetitions <= 50:
        raise ValueError("repetitions must be 1..50")
    if type(problem.domain_size) is not int or not 1 <= problem.domain_size <= 4096:
        raise ValueError("domain must be 1..4096 candidates")
    declaration = problem.describe()
    payload = json.dumps(declaration,sort_keys=True,separators=(",",":")).encode()
    input_digest = sha256(payload).hexdigest()
    baseline = tuple(range(problem.domain_size))
    geometric = h4_graph_order(problem.domain_size)
    trials: list[Trial] = []
    for _ in range(repetitions):
        a = run_trial(problem, baseline, "SEQUENTIAL_EXHAUSTIVE")
        b = run_trial(problem, geometric, "H4_BFS_EXHAUSTIVE")
        if a.objective_minimum != b.objective_minimum or a.argmin != b.argmin:
            raise AssertionError("A/B methods have unequal exact results")
        trials.extend([a,b])
    return {
        "schema":"chronus.geodesic.benchmark/1",
        "classification":"MEASURED_LOCAL_SOFTWARE_NOT_QUANTUM_ADVANTAGE",
        "input_classification":input_classification,
        "input_sha256":input_digest,
        "git_commit":git_commit,
        "host_python":platform.python_version(),
        "host_platform":platform.platform(),
        "problem":declaration,
        "repetitions":repetitions,
        "trials":[t.as_dict() for t in trials],
        "minima_parity_verified":True,
        "same_oracle_call_count_verified":True,
        "quantum_speedup_claimed":False,
        "hardware_speedup_claimed":False,
        "pool_acceptance_or_production_claimed":False,
    }


def benchmark_json(problem: FiniteProblem, **kwargs: object) -> str:
    """Stable schema / key order, except for genuinely measured timing data."""
    return json.dumps(benchmark(problem, **kwargs),sort_keys=True,indent=2) + "\n"
