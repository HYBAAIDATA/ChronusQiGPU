"""
PYTHAGORAS — DOMAIN ABSTRACTION LAYER
The pluggable domain contract for the meta-evolutionary engine.

Theoretical Foundation:
- PYTHAGORAS is not code intelligence. It is the optimization of the optimizer:
  operator-space exploration, surrogate-guided mutation, geometry evolution,
  cross-session memory, and phase-transition telemetry.
- The domain is pluggable. Code was the first domain, not the only one.
  Any domain with a structural coherence metric is a valid substrate:
  circuits, molecules, markets, networks, proofs, architectures.

Engine contract:
- The evolutionary loop operates on serialized source text. parse()/unparse()
  expose the internal representation for domain-level consumers and for
  implementing coherence/primitives/tests/features internally.
- The domain provides: representation, a φ-resonance coherence metric,
  transformation primitives (two engine layers), domain tests, and the
  abstract 8-dimensional feature basis.
- The engine provides: the meta-evolutionary loop, surrogate model,
  phase-transition detection, geometry evolution, and cross-session memory.

Feature basis (8 slots, domain-agnostic semantics):
    1. log element count          (AST nodes / gates / atoms / edges)
    2. max depth                  (AST depth / circuit depth / chain / longest path)
    3. primary unit count         (functions / qubits / residues / nodes)
    4. secondary unit count       (classes / 2q gates / chains / edges)
    5. interaction count          (branches / entangling ops / bonds / cycles)
    6. density                    (nodes/depth, gates/(depth*qubits), ...)
    7. ratio metric               (expr ratio / 1q:total / hetero ratio / degree ratio)
    8. current coherence          (domain φ-score of the unperturbed source)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Tuple

import numpy as np


# A CGP-layer primitive transforms serialized source, modulated by a weight.
WeightedPrimitive = Callable[[str, float], str]
# A mutation-layer primitive transforms serialized source directly.
MutationPrimitive = Callable[[str], str]


class Domain(ABC):
    """
    Abstract base class for a PYTHAGORAS evolutionary domain.

    A Domain supplies everything the meta-evolutionary engine needs to
    evolve artifacts in that domain: parsing, a coherence metric,
    transformation primitives, validity tests, and a feature basis.
    """

    #: Canonical domain identifier (registry key).
    name: str = "abstract"

    #: File extensions the CLI globs for this domain (e.g. (".py",)).
    file_extensions: Tuple[str, ...] = ()

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------

    @abstractmethod
    def parse(self, source: str) -> Any:
        """Parse serialized source into the domain representation."""

    @abstractmethod
    def unparse(self, rep: Any) -> str:
        """Serialize the domain representation back to source text."""

    @abstractmethod
    def is_valid(self, source: str) -> bool:
        """Return True if the source parses and satisfies structural invariants."""

    # ------------------------------------------------------------------
    # Coherence metric (φ-resonance)
    # ------------------------------------------------------------------

    @abstractmethod
    def coherence(self, source: str) -> float:
        """
        Compute the φ-resonance coherence of a serialized artifact.
        Returns a float in [0.0, 1.0].
        """

    def compute_components(self, source: str) -> Dict[str, float]:
        """
        Per-component breakdown of the coherence score.
        Domains should override to expose their component metrics.
        """
        return {"composite": float(self.coherence(source))}

    # ------------------------------------------------------------------
    # Transformation primitives
    # ------------------------------------------------------------------

    @abstractmethod
    def primitives(self) -> Dict[str, WeightedPrimitive]:
        """
        CGP-layer primitives: weighted transforms (source, weight) -> source.
        These populate the CGP node's operator table.
        """

    @abstractmethod
    def mutation_primitives(self) -> Dict[str, MutationPrimitive]:
        """
        Mutation-layer primitives: transforms source -> source.
        These populate the surrogate-guided mutation operator table.
        """

    @abstractmethod
    def mutation_weights(self) -> Dict[str, float]:
        """Prior selection weights for the mutation-layer primitives."""

    # ------------------------------------------------------------------
    # Domain tests
    # ------------------------------------------------------------------

    @abstractmethod
    def tests(self, source: str) -> bool:
        """
        Domain validity test battery (unit tests, physical constraints, ...).
        Returns True if the artifact passes the domain's own tests.
        """

    # ------------------------------------------------------------------
    # Feature basis
    # ------------------------------------------------------------------

    @abstractmethod
    def features(self, source: str) -> np.ndarray:
        """Extract the abstract 8-dimensional feature basis vector."""

    # ------------------------------------------------------------------
    # Engine hooks (optional overrides)
    # ------------------------------------------------------------------

    def normalize(self, source: str) -> str:
        """Canonicalize source before/after evolution. Identity by default."""
        return source

    def sample_source(self) -> str:
        """Canonical small example for smoke tests and self_test gates."""
        raise NotImplementedError(f"{type(self).__name__} has no sample_source")

    def diagnose_manifold(self, source: str) -> Dict[str, Any]:
        """
        φ-sensitivity diagnostic, domain-agnostic default.
        Probes the fitness manifold by applying each mutation-layer primitive
        once and measuring the coherence gradient magnitude.
        """
        base_phi = float(self.coherence(source))
        deltas: List[float] = []

        for prim in self.mutation_primitives().values():
            try:
                candidate = prim(source)
                if self.is_valid(candidate):
                    deltas.append(float(self.coherence(candidate)) - base_phi)
            except Exception:
                continue

        max_abs_delta = max((abs(d) for d in deltas), default=0.0)
        is_degenerate = max_abs_delta < 1e-5

        return {
            "base_phi": base_phi,
            "components": self.compute_components(source),
            "perturbation_deltas": deltas,
            "max_abs_gradient": max_abs_delta,
            "is_degenerate_manifold": is_degenerate,
            "recommended_escape": (
                "non_local_restructure (split_refactor / simulated_annealing)"
                if is_degenerate
                else "gradient_following_cgp"
            ),
        }


def resolve_domain(domain: Any = None) -> Domain:
    """
    Resolve a domain argument into a Domain instance.
    Accepts a Domain instance (passthrough), a registered name string,
    or None (defaults to the code domain).
    """
    if isinstance(domain, Domain):
        return domain
    from .domains import get_domain

    return get_domain(domain or "code")
