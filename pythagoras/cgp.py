"""
PYTHAGORAS — CARTESIAN GENETIC PROGRAMMING
Primary mutation engine (domain-agnostic).

Evolves program transformations as directed acyclic graphs (DAGs).
Features:
- Substrate geometry: n_cols, levels_back, pop_size
- Transformation primitives are supplied by the active Domain
  (default: CodeDomain — add_annotation, rename_var, extract_constant,
  inline_function, split_function; ENH-01 split_function escapes
  degenerate manifolds)
- Strict DAG validation, tournament selection, crossover, and rate-based mutation
"""

from __future__ import annotations

import random
from typing import Any, Callable, Dict, List, Optional, Tuple
import numpy as np

from .domain import Domain, resolve_domain
from .phi_resonance import PhiResonanceCalculator


class CGPNode:
    """A node in the Cartesian Genetic Programming DAG."""

    def __init__(self, op: str, inputs: List[int], weight: float = 1.0):
        self.op = op
        self.inputs = list(inputs)
        self.weight = float(weight)

    def to_dict(self) -> Dict[str, Any]:
        return {"op": self.op, "inputs": list(self.inputs), "weight": self.weight}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CGPNode:
        return cls(op=data["op"], inputs=data["inputs"], weight=data.get("weight", 1.0))


class CGP:
    """
    Cartesian Genetic Programming engine.
    Evolves program transformations represented as directed acyclic graphs.
    """

    def __init__(
        self,
        n_cols: int = 12,
        levels_back: int = 3,
        pop_size: int = 50,
        n_inputs: int = 1,
        domain: Any = None,
    ):
        self.n_cols = max(2, int(n_cols))
        self.levels_back = max(1, int(levels_back))
        self.pop_size = max(4, int(pop_size))
        self.n_inputs = max(1, int(n_inputs))

        # Transformation primitives come from the active Domain.
        self.domain: Domain = resolve_domain(domain)
        self.primitives: Dict[str, Callable[[str, float], str]] = self.domain.primitives()

        self.population: List[List[CGPNode]] = []
        self.fitness: List[float] = []
        self.phi_calc = getattr(self.domain, "phi_calc", PhiResonanceCalculator())

    def initialize(self) -> None:
        """Initialize population with randomized DAG structures."""
        self.population = [self._random_genome() for _ in range(self.pop_size)]
        self.fitness = [0.0] * self.pop_size

    def _random_genome(self) -> List[CGPNode]:
        """Generate a random valid CGP genome adhering to levels_back."""
        genome: List[CGPNode] = []
        prim_keys = list(self.primitives.keys())
        for col in range(self.n_cols):
            op = random.choice(prim_keys)
            if col == 0:
                inputs: List[int] = []
            else:
                max_inputs = min(col, self.levels_back)
                n_in = random.randint(1, max(1, max_inputs))
                min_col = max(0, col - self.levels_back)
                inputs = [random.randint(min_col, col - 1) for _ in range(n_in)]
            weight = float(np.clip(random.gauss(1.0, 0.2), 0.1, 2.0))
            genome.append(CGPNode(op, inputs, weight))
        return genome

    def apply_genome(self, genome: List[CGPNode], source: str) -> str:
        """
        Execute transformations defined by the genome against source code.
        Fails safely per node if the domain's validity check rejects the
        transformed artifact.
        """
        current = source
        for node in genome:
            if node.op in self.primitives:
                try:
                    transformed = self.primitives[node.op](current, node.weight)
                    # Verify domain validity
                    if self.domain.is_valid(transformed):
                        current = transformed
                except Exception:
                    continue
        return current

    def evaluate(self, genome: List[CGPNode], source: str) -> float:
        """
        Evaluate genome against source code.
        Returns the domain coherence score of the transformed artifact.
        """
        transformed = self.apply_genome(genome, source)
        return self.domain.coherence(transformed)

    def evolve(self, source: str, generations: int = 10) -> Tuple[List[CGPNode], float, str]:
        """
        Evolve population against source code.
        Returns (best_genome, best_fitness, best_transformed_source).
        """
        if not self.population or len(self.population) != self.pop_size:
            self.initialize()

        best_genome: Optional[List[CGPNode]] = None
        best_fitness: float = -1.0
        best_source: str = source

        for gen in range(generations):
            # Evaluate population
            for i, genome in enumerate(self.population):
                score = self.evaluate(genome, source)
                self.fitness[i] = score

            gen_best_idx = int(np.argmax(self.fitness))
            if self.fitness[gen_best_idx] > best_fitness:
                best_fitness = self.fitness[gen_best_idx]
                best_genome = self.population[gen_best_idx]
                best_source = self.apply_genome(best_genome, source)

            # Next generation: elitism + tournament selection
            new_pop: List[List[CGPNode]] = []
            if best_genome is not None:
                new_pop.append([CGPNode(n.op, list(n.inputs), n.weight) for n in best_genome])

            while len(new_pop) < self.pop_size:
                p1 = self._tournament()
                p2 = self._tournament()
                child = self._crossover(p1, p2)
                child = self._mutate(child)
                new_pop.append(child)

            self.population = new_pop

        if best_genome is None:
            best_genome = self._random_genome()
            best_fitness = self.domain.coherence(source)

        return best_genome, best_fitness, best_source

    def _tournament(self, size: int = 3) -> List[CGPNode]:
        """Tournament selection."""
        k = min(size, self.pop_size)
        indices = random.sample(range(self.pop_size), k)
        best_idx = max(indices, key=lambda i: self.fitness[i])
        return self.population[best_idx]

    def _crossover(self, p1: List[CGPNode], p2: List[CGPNode]) -> List[CGPNode]:
        """Single-point crossover preserving levels_back constraints."""
        if len(p1) < 2:
            return [CGPNode(n.op, list(n.inputs), n.weight) for n in p1]
        point = random.randint(1, min(len(p1), len(p2)) - 1)
        child: List[CGPNode] = []
        for i, n in enumerate(p1[:point] + p2[point:]):
            # Validate and clamp inputs within levels_back
            min_col = max(0, i - self.levels_back)
            clamped_inputs = [inp for inp in n.inputs if min_col <= inp < i]
            child.append(CGPNode(n.op, clamped_inputs, n.weight))
        return child

    def _mutate(self, genome: List[CGPNode], rate: float = 0.15) -> List[CGPNode]:
        """Mutate operators, inputs, and weights."""
        new_genome: List[CGPNode] = []
        prim_keys = list(self.primitives.keys())
        for col, node in enumerate(genome):
            if random.random() < rate:
                op = random.choice(prim_keys)
                min_col = max(0, col - self.levels_back)
                if col > 0:
                    n_in = random.randint(1, max(1, min(col, self.levels_back)))
                    inputs = [random.randint(min_col, col - 1) for _ in range(n_in)]
                else:
                    inputs = []
                weight = float(np.clip(node.weight + random.gauss(0.0, 0.1), 0.1, 2.0))
                new_genome.append(CGPNode(op, inputs, weight))
            else:
                new_genome.append(CGPNode(node.op, list(node.inputs), node.weight))
        return new_genome

    # =========================================================================
    # Legacy Code-Domain Primitive Delegates
    # =========================================================================
    # The concrete AST implementations live in pythagoras.domains.code_domain.
    # These delegates preserve the historical private API for callers that
    # exercised the primitives directly on a default (code-domain) CGP.

    def _add_annotation(self, source: str, weight: float) -> str:
        """Primitive: add_annotation (delegates to CodeDomain)."""
        from .domains.code_domain import prim_add_annotation

        return prim_add_annotation(source, weight)

    def _rename_var(self, source: str, weight: float) -> str:
        """Primitive: rename_var (delegates to CodeDomain)."""
        from .domains.code_domain import prim_rename_var

        return prim_rename_var(source, weight)

    def _extract_constant(self, source: str, weight: float) -> str:
        """Primitive: extract_constant (delegates to CodeDomain)."""
        from .domains.code_domain import prim_extract_constant

        return prim_extract_constant(source, weight)

    def _inline_function(self, source: str, weight: float) -> str:
        """Primitive: inline_function (delegates to CodeDomain)."""
        from .domains.code_domain import prim_inline_function

        return prim_inline_function(source, weight)

    def _split_function(self, source: str, weight: float) -> str:
        """Primitive: split_function / ENH-01 (delegates to CodeDomain)."""
        from .domains.code_domain import prim_split_function

        return prim_split_function(source, weight)
