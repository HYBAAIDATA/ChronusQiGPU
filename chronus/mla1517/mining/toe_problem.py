"""PYTHIA ↔ TOE: a mining observation as a domain-neutral TOE problem.

Authority split (unchanged by this module):

* TOE (installed ``toe`` distribution) advises on ONE operational setting —
  the CPU-reference work-window size — from measured telemetry, under a
  declared latency budget. Its output is an advisory recommendation.
* PYTHIA authorizes or overrides that advice against its own declared
  bounds (:func:`authorize`).
* The proof boundary (:mod:`chronus.mla1517.mining.pow`) alone decides
  validity: every candidate is re-checked with ``check_pow`` on the full
  80-byte header. No TOE output is a validity predicate, and no consensus
  field (nonce, target, header, share …) is ever a TOE decision variable.

The adapter only translates: measured rows → ``Problem``; the backend
estimates the window→throughput and window→latency strengths itself.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Sequence

from toe.adapters.base import ProblemAdapter
from toe.planning import OperatorSpec
from toe.policy import Constraint, Objective
from toe.problem import Problem, Structure

from .pow import build_header, check_pow, compact_target

#: Declared candidate CPU-reference window sizes (nonces per window).
WINDOW_LEVELS: tuple[int, ...] = (1024, 4096, 16384)


@dataclass(frozen=True)
class WorkTemplate:
    """The job fields needed to build headers. Consensus data stays here,
    on the PYTHIA side; only measured telemetry crosses into TOE."""

    version: int
    previous_hash: str
    merkle_root: str
    timestamp: int
    bits: str
    label: str = "fixture"


@dataclass
class WindowRun:
    window_size: int
    hashes: int
    elapsed_s: float
    hashes_per_s: float
    latency_ms: float
    candidates_found: int
    candidates_rechecked_valid: int
    first_candidates: List[int] = field(default_factory=list)

    def telemetry(self) -> Dict[str, float]:
        return {
            "window_size": float(self.window_size),
            "hashes_per_s": self.hashes_per_s,
            "latency_ms": self.latency_ms,
        }


def execute_window(template: WorkTemplate, start: int, window_size: int) -> WindowRun:
    """Scan ``window_size`` consecutive nonces with real double-SHA256.

    A nonce is a candidate only when ``check_pow`` (the proof boundary)
    accepts the complete header; every candidate is then re-checked
    independently by recomputing SHA256d from scratch.
    """
    target = compact_target(template.bits)
    found: List[int] = []
    t0 = time.perf_counter()
    for nonce in range(start, start + window_size):
        header = build_header(
            template.version, template.previous_hash, template.merkle_root,
            template.timestamp, template.bits, nonce & 0xFFFFFFFF,
        )
        if check_pow(header, target):
            found.append(nonce)
    elapsed = time.perf_counter() - t0
    rechecked = 0
    for nonce in found:
        header = build_header(
            template.version, template.previous_hash, template.merkle_root,
            template.timestamp, template.bits, nonce & 0xFFFFFFFF,
        )
        digest = hashlib.sha256(hashlib.sha256(header).digest()).digest()
        rechecked += int.from_bytes(digest, "little") <= target
    return WindowRun(
        window_size=window_size,
        hashes=window_size,
        elapsed_s=elapsed,
        hashes_per_s=window_size / elapsed if elapsed > 0 else 0.0,
        latency_ms=elapsed * 1000.0,
        candidates_found=len(found),
        candidates_rechecked_valid=rechecked,
        first_candidates=found[:5],
    )


class MiningWindowAdapter(ProblemAdapter):
    """Measured window telemetry → TOE problem.

    Declared shape (PYTHIA's assumption): window_size → hashes_per_s and
    window_size → latency_ms. Objective: maximize hashes_per_s subject to
    the 95th-percentile latency staying within ``latency_budget_ms``.
    """

    name = "pythia.mining.window"
    vocabulary = {
        "window_size": "CPU-reference work window (nonces per window)",
        "hashes_per_s": "measured double-SHA256 throughput",
        "latency_ms": "window wall-clock latency",
    }

    def __init__(self, latency_budget_ms: float, levels: Sequence[int] = WINDOW_LEVELS) -> None:
        self.latency_budget_ms = float(latency_budget_ms)
        self.levels = tuple(int(x) for x in levels)

    def to_problem(self, history: Sequence[Mapping[str, float]]) -> Problem:
        rows = list(history)
        cols = ("window_size", "hashes_per_s", "latency_ms")
        samples = {c: [float(r[c]) for r in rows] for c in cols}
        return Problem(
            domain=self.name,
            observation={c: v[-32:] for c, v in samples.items()},
            state={"window_size": samples["window_size"][-1]},
            structure=Structure.of([("window_size", "hashes_per_s"), ("window_size", "latency_ms")]),
            samples=samples,
            operators=(OperatorSpec("set_window", "window_size", tuple(float(x) for x in self.levels)),),
            objective=Objective("hashes_per_s", "maximize"),
            constraints=(
                Constraint("latency p95 within budget", "latency_ms@p95", "<=", self.latency_budget_ms),
            ),
            metadata={"adapter": self.name, "budget_ms": self.latency_budget_ms},
        )


def authorize(episode: Mapping[str, Any], *, allowed: Sequence[int], governor_max: int) -> Dict[str, Any]:
    """PYTHIA's decision on TOE's advice. TOE never executes anything."""
    rec = episode.get("recommendation") or {}
    window = (rec.get("interventions") or {}).get("window_size")
    if episode.get("status") not in ("ACT", "ACQUIRE_EVIDENCE") or window is None:
        return {"authorized": False, "window_size": None, "reason": f"no actionable advice ({episode.get('status')})"}
    window = int(window)
    if window not in allowed:
        return {"authorized": False, "window_size": None, "reason": f"window {window} not a declared level"}
    if window > governor_max:
        return {"authorized": False, "window_size": governor_max, "reason": "exceeds PYTHIA governor; capped"}
    return {"authorized": True, "window_size": window, "reason": "within PYTHIA bounds", "authority": "PYTHIA"}


__all__ = [
    "MiningWindowAdapter",
    "WINDOW_LEVELS",
    "WindowRun",
    "WorkTemplate",
    "authorize",
    "execute_window",
]
