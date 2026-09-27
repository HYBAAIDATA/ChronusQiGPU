"""
PYTHAGORAS — MUTATION LAYER
Directed refinement via domain-level primitives guided by a surrogate fitness model.

Features:
- Domain-supplied primitives (default CodeDomain):
  - ADD:AnnAssign: Injects type annotations (weight=0.657, empirical avg_gain=0.0775)
  - ADD:Return: Injects explicit return statements and return type annotations
  - ADD:Docstring: Injects structured PEP-257 compliant docstrings
  - REFACTOR:Split: Non-local function decomposition
  - REFACTOR:Extract: Extracts magic literals into structured constants
  - ADVERSARIAL:Perturb (ENH-12): Anti-primitive injection to sharpen surrogate discrimination
- Online Surrogate Fitness Model (ENH-11 Transfer Learning):
  - Consumes the abstract 8-dimensional domain feature basis
  - Predicts expected Δφ per primitive
  - Updates weights continuously via passive-aggressive / ridge online regression
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple
import numpy as np

from .domain import Domain, resolve_domain
from .phi_resonance import PhiResonanceCalculator


class SurrogateFitnessModel:
    """
    Online surrogate model predicting Δφ-gain from AST topological features.
    Enables directed mutation sampling rather than blind random search.
    """

    def __init__(self, feature_dim: int = 8):
        self.feature_dim = feature_dim
        # Initialize linear model weights: small positive priors for annotations and docstrings
        self.weights = np.zeros(feature_dim, dtype=float)
        self.bias = 0.0
        self.learning_rate = 0.05
        self.sample_count = 0
        self.feature_history: List[np.ndarray] = []
        self.gain_history: List[float] = []

    def extract_features(self, source: str, domain_or_calc: Any) -> np.ndarray:
        """
        Extract the abstract 8-dimensional feature basis for the artifact.

        Preferred: pass the active Domain — the feature basis is delegated
        to domain.features(source). For backward compatibility a
        PhiResonanceCalculator may be passed, which yields the code-domain
        AST feature vector computed with that calculator.
        """
        if isinstance(domain_or_calc, Domain):
            return domain_or_calc.features(source)
        # Legacy path: a bare PhiResonanceCalculator implies the code domain.
        from .domains.code_domain import ast_feature_vector

        return ast_feature_vector(source, domain_or_calc)

    def predict(self, features: np.ndarray) -> float:
        """Predict expected Δφ gain given AST feature vector."""
        if len(features) != self.feature_dim:
            return 0.0
        prediction = float(np.dot(self.weights, features) + self.bias)
        return prediction

    def update(self, features: np.ndarray, actual_gain: float) -> float:
        """
        Online passive-aggressive update step with L2 regularisation.
        Returns prediction error.
        """
        if len(features) != self.feature_dim:
            return 0.0
        pred = self.predict(features)
        err = actual_gain - pred

        # Update weights and bias
        self.weights += self.learning_rate * err * features - 0.001 * self.weights
        self.bias += self.learning_rate * err
        self.sample_count += 1

        self.feature_history.append(features)
        self.gain_history.append(actual_gain)
        return err

    def transfer_from(self, prior_model: SurrogateFitnessModel) -> None:
        """
        ENH-11: Surrogate transfer learning.
        Warm-starts weights from prior file/session.
        """
        self.weights = np.copy(prior_model.weights)
        self.bias = float(prior_model.bias)
        self.sample_count = prior_model.sample_count


class PythagorasMutator:
    """
    Directed refinement pass applying domain-level primitives
    weighted by the surrogate fitness model.
    """

    def __init__(self, domain: Any = None):
        self.domain: Domain = resolve_domain(domain)
        self.phi_calc = getattr(self.domain, "phi_calc", PhiResonanceCalculator())
        self.surrogate = SurrogateFitnessModel(feature_dim=8)

        # Prior weights supplied by the active domain.
        self.weights: Dict[str, float] = dict(self.domain.mutation_weights())

        # Mutation primitives supplied by the active domain.
        self.primitives: Dict[str, Callable[[str], str]] = dict(self.domain.mutation_primitives())

    def mutate(self, source: str, n_mutations: int = 5) -> Tuple[str, Dict[str, float]]:
        """
        Apply directed mutations with surrogate guidance and feedback learning.
        Returns (transformed_source, {primitive_name: empirical_gain}).
        """
        current = source
        applied_gains: Dict[str, float] = {}

        for _ in range(n_mutations):
            base_phi = self.domain.coherence(current)
            features = self.surrogate.extract_features(current, self.domain)

            # Compute selection probabilities combining prior weights and surrogate expectation
            prim_names = list(self.primitives.keys())
            combined_scores = []
            for p in prim_names:
                prior_w = self.weights.get(p, 0.2)
                predicted_gain = self.surrogate.predict(features)
                combined = max(0.01, prior_w + 0.5 * predicted_gain)
                combined_scores.append(combined)

            total = sum(combined_scores)
            probs = [s / total for s in combined_scores]

            chosen_prim = np.random.choice(prim_names, p=probs)

            try:
                candidate = self.primitives[chosen_prim](current)
                # Verify domain validity
                if not self.domain.is_valid(candidate):
                    continue
                new_phi = self.domain.coherence(candidate)
                gain = new_phi - base_phi

                # Online update of surrogate
                self.surrogate.update(features, gain)
                applied_gains[chosen_prim] = gain

                # Greedy or improving acceptance
                if gain >= 0.0 or chosen_prim.startswith("ADVERSARIAL"):
                    current = candidate
            except Exception:
                continue

        return current, applied_gains

    def set_weights(self, weights: Dict[str, float]) -> None:
        """Update primitive weights from meta-evolution controller."""
        self.weights.update(weights)

    # =========================================================================
    # Legacy Code-Domain Primitive Delegates
    # =========================================================================
    # The concrete AST implementations live in pythagoras.domains.code_domain.
    # These delegates preserve the historical private API for callers that
    # exercised the primitives directly on a default (code-domain) mutator.

    def _add_ann_assign(self, source: str) -> str:
        """ADD:AnnAssign primitive (delegates to CodeDomain)."""
        from .domains.code_domain import mut_add_ann_assign

        return mut_add_ann_assign(source)

    def _add_return(self, source: str) -> str:
        """ADD:Return primitive (delegates to CodeDomain)."""
        from .domains.code_domain import mut_add_return

        return mut_add_return(source)

    def _add_docstring(self, source: str) -> str:
        """ADD:Docstring primitive (delegates to CodeDomain)."""
        from .domains.code_domain import mut_add_docstring

        return mut_add_docstring(source)

    def _split_function(self, source: str) -> str:
        """REFACTOR:Split primitive (delegates to CodeDomain)."""
        from .domains.code_domain import mut_split_function

        return mut_split_function(source)

    def _extract_constant(self, source: str) -> str:
        """REFACTOR:Extract primitive (delegates to CodeDomain)."""
        from .domains.code_domain import mut_extract_constant

        return mut_extract_constant(source)

    def _adversarial_perturb(self, source: str) -> str:
        """ENH-12: ADVERSARIAL:Perturb primitive (delegates to CodeDomain)."""
        from .domains.code_domain import mut_adversarial_perturb

        return mut_adversarial_perturb(source)
