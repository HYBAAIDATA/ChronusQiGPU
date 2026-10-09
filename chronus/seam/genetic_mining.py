"""Deterministic genetic optimization of mining dispatch geometry.

The optimizer chooses only batch/window/thread breadth.  It never receives or
changes a Bitcoin header, nonce, target, digest, credential or share result.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass
from typing import Any, Callable

from Intelligence.lucas_scales import nearest_ladder_index


@dataclass(frozen=True)
class MiningGenome:
    request_delta: int
    thread_bias: int


@dataclass(frozen=True)
class GeneticMiningResult:
    batch: int
    threads: int
    window: int
    fitness: float
    generation: int
    genome: MiningGenome
    generations_run: int
    population_size: int
    evidence_hash: str

    def to_evidence(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "genome": asdict(self.genome),
            "passed": (
                self.batch > 0
                and self.window > 0
                and self.threads > 0
                and self.fitness >= 0.0
                and len(self.evidence_hash) == 64
            ),
            "authority": "dispatch-geometry-only",
        }


def _fitness(requested: int, work_items: int, threads: int) -> float:
    requested = max(1, int(requested))
    work_items = max(1, int(work_items))
    threads = max(1, int(threads))
    coverage = min(work_items, requested) / requested
    overshoot = max(0, work_items - requested) / requested
    thread_cost = min(1.0, threads / requested)
    return max(0.0, coverage - 0.20 * overshoot - 0.02 * thread_cost)


def evolve_mining_config(
    requested: int,
    scale: Callable[[str, int], Any],
    *,
    generations: int = 5,
    population_size: int = 8,
    seed: int | None = None,
) -> GeneticMiningResult:
    """Evolve a bounded dispatch configuration with reproducible evidence."""
    requested = int(requested)
    if requested <= 0:
        raise ValueError("requested work must be positive")
    if not 1 <= int(generations) <= 100:
        raise ValueError("generations must be in [1,100]")
    if not 4 <= int(population_size) <= 128:
        raise ValueError("population_size must be in [4,128]")
    # LUCAS_SCALED (lemma_lucas_universal): the search-effort envelopes are
    # ladder stops inside the validated bounds.
    generations = nearest_ladder_index(int(generations), 1, 100)
    population_size = nearest_ladder_index(int(population_size), 4, 128)
    if seed is None:
        seed = int.from_bytes(
            hashlib.sha256(
                f"euclid-genetic-mining-v1:{requested}:{generations}:{population_size}".encode()
            ).digest()[:8],
            "big",
        )
    rng = random.Random(seed)
    radius = max(1, requested // 2)
    population = [
        MiningGenome(rng.randint(-radius, radius), rng.randint(-3, 3))
        for _ in range(population_size)
    ]
    population[0] = MiningGenome(0, 0)
    history: list[dict[str, Any]] = []
    best: tuple[float, int, MiningGenome, int, int] | None = None

    for generation in range(generations):
        scored: list[tuple[float, MiningGenome, int, int]] = []
        for index, genome in enumerate(population):
            candidate = max(1, min(requested * 2, requested + genome.request_delta))
            scaled = scale(f"genetic-{generation}-{index}", candidate)
            raw_work_items = int(getattr(scaled, "work_items"))
            if raw_work_items <= 0:
                raise ValueError("scale returned non-positive work")
            work_items = min(requested * 2, raw_work_items)
            ladder_index = int(getattr(scaled, "ladder_index", 1))
            threads = max(1, ladder_index + genome.thread_bias)
            score = _fitness(requested, work_items, threads)
            if not math.isfinite(score):
                raise ValueError("non-finite genetic fitness")
            scored.append((score, genome, work_items, threads))
        scored.sort(key=lambda row: (-row[0], row[2], row[3], row[1].request_delta))
        winner = scored[0]
        history.append(
            {
                "generation": generation,
                "fitness": winner[0],
                "genome": asdict(winner[1]),
                "work_items": winner[2],
                "threads": winner[3],
            }
        )
        candidate_best = (winner[0], generation, winner[1], winner[2], winner[3])
        if best is None or candidate_best[:2] > best[:2]:
            best = candidate_best

        elites = [row[1] for row in scored[: max(2, population_size // 4)]]
        next_population = list(elites)
        while len(next_population) < population_size:
            left, right = rng.choice(elites), rng.choice(elites)
            child = MiningGenome(
                rng.choice((left.request_delta, right.request_delta)),
                rng.choice((left.thread_bias, right.thread_bias)),
            )
            if rng.random() < 0.35:
                child = MiningGenome(
                    max(-radius, min(radius, child.request_delta + rng.randint(-radius, radius))),
                    max(-4, min(4, child.thread_bias + rng.choice((-1, 1)))),
                )
            next_population.append(child)
        population = next_population

    assert best is not None
    score, generation, genome, work_items, threads = best
    evidence = {
        "schema": "chronus.genetic-mining/1",
        "requested": requested,
        "seed": seed,
        "generations": history,
        "authority": "dispatch-geometry-only",
    }
    evidence_hash = hashlib.sha256(
        json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return GeneticMiningResult(
        batch=max(1, work_items),
        threads=max(1, threads),
        window=max(1, work_items),
        fitness=float(score),
        generation=generation,
        genome=genome,
        generations_run=generations,
        population_size=population_size,
        evidence_hash=evidence_hash,
    )


__all__ = ["MiningGenome", "GeneticMiningResult", "evolve_mining_config"]