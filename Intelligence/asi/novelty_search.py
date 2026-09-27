# pythagoras/asi/novelty_search.py — NEW

import math
from dataclasses import dataclass


@dataclass
class NoveltyDescriptor:
    behaviour_vector: list[float]  # behavioural characterization
    novelty_score: float = 0.0
    is_novel: bool = False


class NoveltySearchEngine:
    """Objective-free search that rewards behavioural diversity.

    Instead of optimising φ directly, this explores transformations
    that produce novel behavioural signatures. Novelty can lead to
    discoveries that fitness-guided search would miss in deceptive landscapes.
    """

    def __init__(self, k: int = 15, novelty_threshold: float = 0.1):
        self.k = k  # number of nearest neighbours for novelty computation
        self.novelty_threshold = novelty_threshold
        self.archive: list[NoveltyDescriptor] = []

    def compute_novelty(self, behaviour_vector: list[float]) -> NoveltyDescriptor:
        """Novelty = average distance to k-nearest neighbours in behaviour space."""
        if len(self.archive) < self.k:
            novelty = float("inf")
        else:
            distances = [
                self._euclidean(behaviour_vector, d.behaviour_vector) for d in self.archive
            ]
            distances.sort()
            novelty = sum(distances[: self.k]) / self.k

        is_novel = novelty > self.novelty_threshold
        descriptor = NoveltyDescriptor(behaviour_vector, novelty, is_novel)

        if is_novel:
            self.archive.append(descriptor)

        return descriptor

    def _euclidean(self, a: list[float], b: list[float]) -> float:
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

    def get_novelty_archive(self) -> list[dict]:
        return [{"novelty": d.novelty_score, "is_novel": d.is_novel} for d in self.archive]

    def quality_diversity_search(
        self, evaluate_fn: callable, generate_fn: callable, n_iterations: int = 100
    ) -> dict:
        """Quality-Diversity (QD) search: maintain both novelty AND quality.

        QD archives solutions that are both diverse and high-performing,
        rather than keeping only the single best solution.
        """
        archive = []  # list of (behaviour, quality, solution)
        for _ in range(n_iterations):
            solution = generate_fn()
            behaviour = evaluate_fn(solution, return_behaviour=True)
            quality = evaluate_fn(solution, return_behaviour=False)
            novelty = self.compute_novelty(behaviour)
            if novelty.is_novel or quality > 0:
                archive.append(
                    {"behaviour": behaviour, "quality": quality, "novelty": novelty.novelty_score}
                )

        return {
            "archive_size": len(archive),
            "max_quality": max((a["quality"] for a in archive), default=0),
            "mean_novelty": sum(a["novelty"] for a in archive) / max(len(archive), 1),
            "diversity": len(set(tuple(a["behaviour"]) for a in archive)),
        }
