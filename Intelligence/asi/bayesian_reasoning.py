# pythagoras/asi/bayesian_reasoning.py — NEW

import math
from dataclasses import dataclass


@dataclass
class BayesianBelief:
    mean: float
    variance: float
    n_observations: int = 0


class BayesianReasoningEngine:
    """Bayesian belief updating for mutation effect prediction.

    Maintains posterior distributions over mutation effects and updates
    them rationally as new evidence comes in.
    """

    def __init__(self, prior_mean: float = 0.0, prior_variance: float = 1.0):
        self.beliefs: dict[str, BayesianBelief] = {}  # mutation_type -> belief
        self.prior = BayesianBelief(prior_mean, prior_variance)

    def update(self, mutation_type: str, observed_effect: float, observation_variance: float = 0.1):
        """Bayesian update: posterior = combine prior with observation."""
        if mutation_type not in self.beliefs:
            self.beliefs[mutation_type] = BayesianBelief(self.prior.mean, self.prior.variance)

        belief = self.beliefs[mutation_type]

        # Gaussian conjugate update
        posterior_precision = 1.0 / belief.variance + 1.0 / observation_variance
        posterior_mean = (
            belief.mean / belief.variance + observed_effect / observation_variance
        ) / posterior_precision
        posterior_variance = 1.0 / posterior_precision

        self.beliefs[mutation_type] = BayesianBelief(
            posterior_mean, posterior_variance, belief.n_observations + 1
        )

    def predict(self, mutation_type: str) -> tuple[float, float]:
        """Return (predicted_mean, predicted_variance) for a mutation type."""
        belief = self.beliefs.get(mutation_type, self.prior)
        return belief.mean, belief.variance

    def credible_interval(
        self, mutation_type: str, confidence: float = 0.95
    ) -> tuple[float, float]:
        """Compute credible interval for the predicted effect."""
        mean, var = self.predict(mutation_type)
        z = 1.96 if confidence == 0.95 else 2.576 if confidence == 0.99 else 1.0
        return (mean - z * math.sqrt(var), mean + z * math.sqrt(var))

    def uncertainty_quantification(self) -> dict:
        """Report epistemic uncertainty across all mutation types."""
        return {
            mtype: {"mean": b.mean, "variance": b.variance, "n_obs": b.n_observations}
            for mtype, b in self.beliefs.items()
        }
