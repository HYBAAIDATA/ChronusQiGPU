"""
EUCLID Adaptive Operator Surrogate — quantum-substrate formulation
==================================================================
Predicts expected operator gain (delta_phi) as a Born-rule expectation over an
amplitude-encoded empirical distribution of *measured* candidate deltas:

    |psi_op>  ∝  sum_x sqrt(count_x) |x>   +  sqrt(prior_mass) |0>
    prediction =  <psi_op| D |psi_op>      (D = delta observable, diagonal)

The prediction is therefore the expectation value of the measured-delta
observable on the exact substrate (``kellogg.quantum_tensor.QuantumState``);
there are no learned weights, no sigmoid squashing, and no invented prior
gains.  An operator with no measured history falls back to the pooled
cross-operator evidence state, and with no evidence at all to the declared
symmetric prior whose expectation is 0.0 — an honest "unknown" answer.

Anti-primitive status is likewise measured: a count of observed invalid or
strongly-negative outcomes, not an invented suppression constant.
"""

import math
from typing import Dict, List, Optional, Tuple, Any

from kellogg.quantum_tensor import Complex, ComplexMatrix, QuantumState


class AdaptiveOperatorSurrogate:
    """
    Born-rule surrogate over measured operator outcomes.

    Parameters are declared estimation policy, not learned constants:

    * ``delta_span`` — measured deltas are clamped to [-span, +span] before
      encoding (declared support bound for the delta observable).
    * ``prior_mass`` — pseudo-count amplitude mass assigned to the neutral
      outcome (delta 0); the uninformative symmetric prior.
    * ``anti_failure_threshold`` — number of measured invalid trials that
      qualifies an operator as anti-primitive.
    * ``anti_delta_threshold`` — a measured delta below this counts as
      negative evidence toward anti-primitive status.
    """

    def __init__(
        self,
        *,
        delta_span: float = 1.0,
        prior_mass: float = 1.0,
        anti_failure_threshold: int = 3,
        anti_delta_threshold: float = -0.05,
    ):
        if delta_span <= 0:
            raise ValueError("delta_span must be positive")
        if prior_mass <= 0:
            raise ValueError("prior_mass must be positive")
        self.delta_span = float(delta_span)
        self.prior_mass = float(prior_mass)
        self.anti_failure_threshold = int(anti_failure_threshold)
        self.anti_delta_threshold = float(anti_delta_threshold)
        # measured evidence: op_name -> {measured_delta: count}
        self._outcomes: Dict[str, Dict[float, int]] = {}
        # pooled measured evidence across all operators (back-off state)
        self._pooled: Dict[float, int] = {}
        # measured failure counts (invalid candidate produced)
        self.anti_primitives: Dict[str, int] = {}
        # (predicted, measured) pairs for RMSE — measured outcomes only
        self.prediction_history: List[Tuple[float, float]] = []

    @staticmethod
    def _born_expectation(distribution: Dict[float, int], prior_mass: float) -> float:
        """Expectation of the delta observable over an amplitude-encoded state.

        |psi> ∝ sum_x sqrt(n_x)|x> + sqrt(prior_mass)|0>; the Born probability
        of support point x is n_x / (prior_mass + sum n), so the expectation is
        the count-weighted mean under the symmetric neutral prior.
        """
        support = sorted(distribution)
        amplitudes = [math.sqrt(distribution[x]) for x in support]
        support.append(0.0)
        amplitudes.append(math.sqrt(prior_mass))
        state = QuantumState.from_real_vector(amplitudes)
        observable = ComplexMatrix.diagonal([Complex(float(x)) for x in support])
        return float(state.expectation(observable))

    def predict_gain(self, features: Dict[str, Any], op_name: str) -> float:
        """Born expectation of the measured delta observable for ``op_name``.

        ``features`` is accepted for signature compatibility; the prediction is
        conditioned on the operator's measured record. With no per-operator
        evidence, pooled measured evidence is used; with no evidence at all the
        symmetric prior yields 0.0 (an honest "no measured information").
        """
        distribution = self._outcomes.get(op_name) or self._pooled
        if not distribution:
            return 0.0
        return round(self._born_expectation(distribution, self.prior_mass), 6)

    def prediction_uncertainty(self, op_name: str) -> float:
        """Normalised measurement entropy of the operator's evidence state.

        1.0 = maximally uncertain (uniform over support incl. prior),
        0.0 = a single definite measured outcome.
        """
        distribution = dict(self._outcomes.get(op_name) or self._pooled)
        if not distribution:
            return 1.0
        support = sorted(distribution)
        amplitudes = [math.sqrt(distribution[x]) for x in support]
        amplitudes.append(math.sqrt(self.prior_mass))
        state = QuantumState.from_real_vector(amplitudes)
        if state.dim <= 1:
            return 0.0
        return float(state.measurement_entropy() / math.log(state.dim))

    def is_anti_primitive(self, op_name: str) -> bool:
        """Measured suppression: True when the operator's recorded count of
        invalid or strongly-negative trials reaches the declared threshold."""
        return self.anti_primitives.get(op_name, 0) >= self.anti_failure_threshold

    def update(
        self,
        features: Dict[str, Any],
        op_name: str,
        actual_delta: Optional[float],
        parse_v: bool,
        test_v: bool,
    ) -> None:
        """Record measured evidence for ``op_name``.

        ``actual_delta`` is only meaningful when the candidate was valid
        (``parse_v and test_v``); invalid candidates contribute a measured
        failure count, never a fabricated delta.
        """
        measured = bool(parse_v and test_v) and actual_delta is not None
        if measured:
            delta = max(-self.delta_span, min(self.delta_span, float(actual_delta)))
            prediction = self.predict_gain(features, op_name)
            self.prediction_history.append((prediction, delta))
            bucket = round(delta, 6)
            self._outcomes.setdefault(op_name, {})[bucket] = (
                self._outcomes.setdefault(op_name, {}).get(bucket, 0) + 1
            )
            self._pooled[bucket] = self._pooled.get(bucket, 0) + 1
            if delta <= self.anti_delta_threshold:
                self.anti_primitives[op_name] = self.anti_primitives.get(op_name, 0) + 1
            else:
                self.anti_primitives[op_name] = max(
                    0, self.anti_primitives.get(op_name, 0) - 1
                )
        else:
            # invalid candidate: measured failure evidence, no delta fabricated
            self.anti_primitives[op_name] = self.anti_primitives.get(op_name, 0) + 1

    def compute_rmse(self) -> float:
        """RMSE over (predicted, measured) pairs only — no fabricated targets."""
        if not self.prediction_history:
            return 0.0
        mse = sum((p - a) ** 2 for p, a in self.prediction_history) / len(
            self.prediction_history
        )
        return round(math.sqrt(mse), 6)


# Alias for backward compatibility
NeuralSurrogateEvaluator = AdaptiveOperatorSurrogate
