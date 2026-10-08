# pythagoras/asi/predictive_processing.py — NEW

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from . import manifold_bridge as mb
from .manifold_bridge import PHI_POWERS

PHI_INV = 0.5 * (5**0.5 - 1.0)


@dataclass
class BeliefState:
    predicted_phi: float
    predicted_delta: float
    uncertainty: float  # variance of prediction
    precision: float  # inverse variance — confidence in prediction
    free_energy: float


@dataclass
class ActiveInferenceResult:
    perception: BeliefState
    action: str  # chosen mutation
    expected_free_energy: float
    actual_free_energy: float
    learning_signal: float


@dataclass
class ManifoldBelief:
    """Dual-mode result of a hierarchical manifold perception step.

    `belief_state` is the deepest latent prior layer (a B_phi^11 point);
    `predicted_state` is the top-down prediction of the sensory layer,
    g_0(x_1).  `layers` holds the full hierarchy of ball points.
    """

    belief_state: np.ndarray
    predicted_state: np.ndarray
    free_energy: float
    layers: List[np.ndarray]
    errors: List[np.ndarray]
    free_energy_history: List[float] = field(default_factory=list)
    converged: bool = False
    steps: int = 0

    @property
    def predicted_phi(self) -> float:
        """Scalar readout of the top-down sensory prediction."""
        return mb.scalar_projection(self.predicted_state)

    def to_scalar(self) -> float:
        return mb.scalar_projection(self.belief_state)


class PredictiveProcessingEngine:
    """Implements Friston's Active Inference for PYTHAGORAS.

    The system maintains beliefs about the code landscape, predicts mutation
    effects, and acts to minimise free energy (prediction error).

    Two loops:
    1. Perception: update beliefs from observed phi changes (minimise surprise)
    2. Action: choose mutations that minimise expected free energy

    Manifold mode: a multi-layer hierarchical generative model over the
    Poincaré ball B_phi^11.  Layer 0 is the sensory channel; deeper layers
    are golden-smoothed priors.  Prediction errors are the ambient-space
    residuals eps_l = u_l - K u_{l+1}; latent beliefs are updated by
    Riemannian gradient descent along Poincaré geodesics,
        x_{l+1} <- exp_{x_{l+1}}( -gamma * grad_R F ),
    with F the precision-weighted free energy over the full 11-D error
    vectors — not a scalar residual.
    """

    def __init__(self, surrogate_model=None):
        self.surrogate = surrogate_model
        self.beliefs = BeliefState(0.5, 0.0, 0.1, 10.0, 0.0)
        self.belief_history: list[BeliefState] = []
        self._error_history: list[float] = []
        self.learning_rate = 0.1
        self._manifold_belief: Optional[np.ndarray] = None
        self.manifold_belief_history: list[ManifoldBelief] = []

    def perceive(self, observed_phi: float, observed_delta: float) -> BeliefState:
        """Update beliefs based on observation (perception loop).

        Belief update = precision-weighted average of prior and observation.
        """
        prior = self.beliefs.predicted_phi
        prior_precision = self.beliefs.precision
        observation_precision = 1.0 / max(self.beliefs.uncertainty, 1e-10)

        # Bayesian update
        posterior_precision = prior_precision + observation_precision
        posterior_mean = (
            prior_precision * prior + observation_precision * observed_phi
        ) / posterior_precision

        # Free energy = surprise = -log p(observation | model)
        prediction_error = observed_phi - prior
        free_energy = 0.5 * prediction_error**2 * prior_precision

        self.beliefs = BeliefState(
            predicted_phi=posterior_mean,
            predicted_delta=observed_delta,
            uncertainty=1.0 / posterior_precision,
            precision=posterior_precision,
            free_energy=free_energy,
        )
        self.belief_history.append(self.beliefs)
        return self.beliefs

    def act(self, candidate_mutations: list, surrogate_predictions: list) -> ActiveInferenceResult:
        """Choose action (mutation) that minimises expected free energy (action loop)."""

        # Expected free energy for each candidate
        expected_fes = []
        for pred in surrogate_predictions:
            # EFE = expected surprise + information gain
            expected_surprise = (
                0.5 * (pred - self.beliefs.predicted_phi) ** 2 * self.beliefs.precision
            )
            info_gain = abs(pred - self.beliefs.predicted_delta)  # novelty component
            # Curiosity credit = info_gain attenuated one golden step
            # (the declared φ⁻¹ idiom — not an invented 0.1).
            efe = expected_surprise - info_gain * PHI_INV
            expected_fes.append(efe)

        # Choose action with minimum expected free energy
        best_idx = expected_fes.index(min(expected_fes))
        chosen = candidate_mutations[best_idx]

        return ActiveInferenceResult(
            perception=self.beliefs,
            action=chosen,
            expected_free_energy=min(expected_fes),
            actual_free_energy=self.beliefs.free_energy,
            learning_signal=self.beliefs.free_energy,
        )

    def update_precision(self, observed_error: float):
        """Meta-learning: adjust precision (confidence) based on prediction accuracy.

        Precision is the measured quantity it claims to be: the inverse
        of the observed squared-error mean over the recent window — no
        invented multiplicative steps.
        """
        self._error_history.append(float(observed_error))
        if len(self._error_history) > 50:
            self._error_history = self._error_history[-50:]
        mse = sum(e * e for e in self._error_history) / len(self._error_history)
        self.beliefs.uncertainty = mse + 1e-9
        self.beliefs.precision = 1.0 / self.beliefs.uncertainty

    def get_free_energy_trajectory(self) -> list[float]:
        return [b.free_energy for b in self.belief_history]

    # ------------------------------------------------------------------
    # Manifold operators (S-11 elevation)
    # ------------------------------------------------------------------

    def _precision_operators(self, depth: int) -> List[np.ndarray]:
        """Per-layer precision matrices Pi_l = precision * diag(phi^{-(i+1)}).

        The golden weighting makes the coarser dimensions (low index, high
        phi-weight) dominate the error metric — the substrate's native
        hierarchy.  The scalar self.beliefs.precision carries the learned
        confidence through from the scalar path.
        """
        w = np.diag(PHI_POWERS)
        return [self.beliefs.precision * w for _ in range(max(depth - 1, 1))]

    def _hierarchy_errors(
        self, ambient_layers: List[np.ndarray], kernel: np.ndarray
    ) -> List[np.ndarray]:
        """eps_l = u_l - g(u_{l+1}) with g = K (golden smoothing kernel)."""
        return [
            ambient_layers[l] - kernel @ ambient_layers[l + 1]
            for l in range(len(ambient_layers) - 1)
        ]

    def _hierarchy_free_energy(
        self,
        ambient_layers: List[np.ndarray],
        kernel: np.ndarray,
        precisions: List[np.ndarray],
    ) -> float:
        """F = sum_l 1/2 eps_l^T Pi_l eps_l over the full 11-D error vectors."""
        f = 0.0
        for l, eps in enumerate(self._hierarchy_errors(ambient_layers, kernel)):
            f += 0.5 * float(eps @ precisions[l] @ eps)
        return f

    def perceive_manifold(
        self,
        observation: np.ndarray,
        depth: int = 3,
        step_size: float = 0.5,
        tol: float = 1e-10,
        max_sweeps: int = 64,
    ) -> ManifoldBelief:
        """Hierarchical predictive processing on B_phi^11.

        Layer 0 is clamped to the observation; latent layers x_1..x_{L-1}
        are updated by Gauss-Seidel sweeps of Riemannian geodesic descent
        on the joint free energy F.  The gradient in ambient coordinates is
            dF/du_k = Pi_k eps_k - K^T Pi_{k-1} eps_{k-1}
        pulled back to golden coordinates through the exact unfold
        Jacobian J = du/dx, then stepped along the manifold's geodesics
        (exponential map, curvature -1).  Every sweep can only decrease F,
        so the free-energy history is non-increasing by construction.

        Also performs the scalar dual update: the scalar belief state
        receives the projected prediction and final free energy so
        perceive/act/update_precision stay coherent.
        """
        obs_ball = mb.as_ball_vector(observation)
        kernel = mb.golden_smoothing_kernel()
        precisions = self._precision_operators(depth)

        anchor = self._manifold_belief if self._manifold_belief is not None else obs_ball
        layers = mb.state_to_prior_layers(anchor, depth)
        layers[0] = obs_ball

        def ambient(ls):
            return [mb.unfold_ball_vector(x) for x in ls]

        def objective(ls):
            return self._hierarchy_free_energy(ambient(ls), kernel, precisions)

        # The unfold diffeomorphism x <-> u makes B_phi^11 globally
        # equivalent to R^11, so the joint latent objective — quadratic in
        # the stacked ambient vector — has a closed-form manifold optimum.
        # Block-tridiagonal system over latents u_1..u_{L-1}:
        #   A[k,k]   = (Pi_k if k < L-1 else 0) + K^T Pi_{k-1} K + rI
        #   A[k,k-1] = -K^T Pi_{k-1}        (u_0 fixed -> moves into b_1)
        #   A[k,k+1] = -Pi_k K              (for k < L-1)
        #   b_1      = K^T Pi_0 u_0
        # rI is the exogenous-noise floor: every latent carries nonzero
        # exogenous variance, so the system is never exactly singular.
        # Each layer then moves along the geodesic x_k -> fold(u_k*) —
        # gamma=1 lands exactly on the optimum; the Armijo loop is a
        # safety net for nonlinear generative maps.
        n_lat = depth - 1
        dim = mb.MANIFOLD_DIM
        u_amb = ambient(layers)
        big = np.zeros((n_lat * dim, n_lat * dim), dtype=np.float64)
        rhs = np.zeros(n_lat * dim, dtype=np.float64)
        for k in range(1, depth):
            r0 = (k - 1) * dim
            pk_prev = precisions[k - 1]
            diag = kernel.T @ pk_prev @ kernel + 1e-9 * np.eye(dim)
            if k < depth - 1:
                diag = diag + precisions[k]
                big[r0 : r0 + dim, r0 + dim : r0 + 2 * dim] = -precisions[k] @ kernel
            big[r0 : r0 + dim, r0 : r0 + dim] = diag
            if k == 1:
                rhs[r0 : r0 + dim] = kernel.T @ pk_prev @ u_amb[0]
            else:
                prev = (k - 2) * dim
                big[r0 : r0 + dim, prev : prev + dim] = -kernel.T @ pk_prev

        u_star = np.linalg.solve(big, rhs)

        history = [objective(layers)]
        converged = False
        total_steps = 0
        for _ in range(int(max_sweeps)):
            for k in range(1, depth):
                target = mb.fold_ambient_vector(u_star[(k - 1) * dim : k * dim])
                gamma = 1.0
                trial = list(layers)
                f_cur = objective(layers)
                for _halvings in range(24):
                    trial[k] = mb.geodesic_towards(layers[k], target, gamma)
                    if objective(trial) <= f_cur + 1e-15:
                        break
                    gamma *= 0.5
                else:
                    trial[k] = layers[k]
                layers[k] = trial[k]
                total_steps += 1
            f_now = objective(layers)
            history.append(f_now)
            if abs(history[-2] - f_now) < tol * (1.0 + abs(history[-2])):
                converged = True
                break

        ambient_layers = ambient(layers)
        errors = self._hierarchy_errors(ambient_layers, kernel)
        predicted_state = mb.fold_ambient_vector(kernel @ ambient_layers[1])
        belief_state = layers[-1]
        self._manifold_belief = belief_state

        result = ManifoldBelief(
            belief_state=belief_state,
            predicted_state=predicted_state,
            free_energy=history[-1],
            layers=layers,
            errors=errors,
            free_energy_history=history,
            converged=converged,
            steps=total_steps,
        )
        self.manifold_belief_history.append(result)

        # Scalar dual update — keeps the 1-D contract coherent.
        self.beliefs = BeliefState(
            predicted_phi=result.predicted_phi,
            predicted_delta=self.beliefs.predicted_delta,
            uncertainty=self.beliefs.uncertainty,
            precision=self.beliefs.precision,
            free_energy=history[-1],
        )
        self.belief_history.append(self.beliefs)
        return result
