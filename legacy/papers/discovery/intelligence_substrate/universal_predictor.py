"""
Universal Predictor for Euclid
===============================
Domain-agnostic predictive intelligence engine.

This provides a flexible prediction framework that can be adapted to different
domains by changing the input data interface and configuration.

This is a practical ML framework, NOT "magic code" that replaces all systems.
The predictive-causal transition path below is part of this same canonical
backend: there is no second predictive substrate.
"""

from typing import Any, Dict, List, Optional, Sequence
from dataclasses import dataclass
import logging
import statistics
from datetime import datetime, timezone

logger = logging.getLogger("hyba.euclid.predictor")


@dataclass
class PredictionConfig:
    """Configuration for the universal predictor"""

    ensemble_weights: Dict[str, float] = None
    confidence_threshold: float = 0.7
    max_features: int = 100
    scaling_method: str = "standard"

    def __post_init__(self):
        if self.ensemble_weights is None:
            self.ensemble_weights = {"rf": 0.25, "xgb": 0.25, "lgbm": 0.25, "gb": 0.25}


class UniversalFeatureExtractor:
    """Extracts features from data for prediction"""

    def extract_indicators(self, data: Dict[str, List]) -> Dict[str, float]:
        """
        Extract statistical indicators from data lists.

        Args:
            data: Dictionary with lists of numerical data

        Returns:
            Dictionary of computed indicators (mean, variance, trend, etc.)
        """
        indicators = {}

        for key, values in data.items():
            if not values or not isinstance(values, list):
                continue

            try:
                numeric_values = [float(v) for v in values if v is not None]
                if len(numeric_values) == 0:
                    continue

                indicators[f"{key}_mean"] = statistics.mean(numeric_values)
                indicators[f"{key}_std"] = (
                    statistics.stdev(numeric_values) if len(numeric_values) > 1 else 0.0
                )
                indicators[f"{key}_min"] = min(numeric_values)
                indicators[f"{key}_max"] = max(numeric_values)
                indicators[f"{key}_count"] = len(numeric_values)

                if len(numeric_values) >= 2:
                    trend = (numeric_values[-1] - numeric_values[0]) / len(numeric_values)
                    indicators[f"{key}_trend"] = trend

            except (ValueError, TypeError, statistics.StatisticsError):
                continue

        return indicators


class EnsembleIntelligenceEngine:
    """Simple ensemble prediction engine"""

    def __init__(self, config: PredictionConfig):
        self.config = config

    def predict_ensemble(self, indicators: Dict[str, float]) -> Dict[str, float]:
        """Generate ensemble predictions from indicators."""
        predictions = {}
        total_weight = sum(self.config.ensemble_weights.values())

        for model, weight in self.config.ensemble_weights.items():
            norm_weight = weight / total_weight
            model_prediction = self._heuristic_prediction(indicators, model)
            predictions[model] = model_prediction * norm_weight

        ensemble_pred = sum(predictions.values())
        return {
            "ensemble": ensemble_pred,
            "individual_models": predictions,
            "confidence": self._calculate_confidence(indicators),
        }

    def _heuristic_prediction(self, indicators: Dict[str, float], model_type: str) -> float:
        """Generate heuristic prediction based on indicators."""
        values = list(indicators.values())
        if not values:
            return 0.5
        min_val = min(values)
        max_val = max(values)
        if max_val == min_val:
            return 0.5
        normalized = [(v - min_val) / (max_val - min_val) for v in values]
        return statistics.mean(normalized)

    def _calculate_confidence(self, indicators: Dict[str, float]) -> float:
        """Calculate confidence based on indicator quality."""
        if not indicators:
            return 0.0
        count = len(indicators)
        values = list(indicators.values())
        variance = statistics.variance(values) if len(values) > 1 else 0.0
        return min(1.0, (count / 20.0) + (variance / (variance + 1.0)) * 0.5)


class UniversalRiskAssessor:
    """Assesses risk profiles from predictions"""

    def assess_risk(self, predictions: Dict[str, float]) -> Dict[str, Any]:
        """Assess risk from prediction outputs."""
        ensemble_pred = predictions.get("ensemble", 0.5)
        confidence = predictions.get("confidence", 0.5)

        if ensemble_pred > 0.8:
            risk_level = "CRITICAL"
        elif ensemble_pred > 0.6:
            risk_level = "HIGH"
        elif ensemble_pred > 0.4:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        actions = {
            "CRITICAL": ["immediate_intervention", "escalate", "monitor_continuous"],
            "HIGH": ["intervention", "monitor_frequent", "prepare_contingency"],
            "MEDIUM": ["monitor", "review", "prepare_mitigation"],
            "LOW": ["monitor_periodic", "maintain_baseline"],
        }

        return {
            "risk_level": risk_level,
            "risk_score": ensemble_pred,
            "confidence": confidence,
            "factors": self._extract_risk_factors(predictions),
            "recommended_actions": actions.get(risk_level, []),
        }

    def _extract_risk_factors(self, predictions: Dict[str, float]) -> List[str]:
        factors = []
        individual = predictions.get("individual_models", {})
        for model, score in individual.items():
            if score > 0.7:
                factors.append(f"{model}_high_risk")
            elif score < 0.3:
                factors.append(f"{model}_low_risk")
        return factors if factors else ["baseline_indicators"]


class InterventionFramework:
    """Framework for generating intervention recommendations"""

    def generate_interventions(self, risk_assessment: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate intervention recommendations based on risk assessment."""
        interventions = []
        risk_level = risk_assessment.get("risk_level", "LOW")
        actions = risk_assessment.get("recommended_actions", [])

        for action in actions:
            interventions.append(
                {
                    "action": action,
                    "priority": self._action_priority(action, risk_level),
                    "estimated_impact": self._estimate_impact(action, risk_level),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        return interventions

    def _action_priority(self, action: str, risk_level: str) -> str:
        if "immediate" in action or risk_level == "CRITICAL":
            return "P0"
        elif risk_level == "HIGH":
            return "P1"
        elif risk_level == "MEDIUM":
            return "P2"
        return "P3"

    def _estimate_impact(self, action: str, risk_level: str) -> str:
        if "immediate" in action or "escalate" in action:
            return "HIGH"
        elif "intervention" in action:
            return "MEDIUM"
        return "LOW"


class UniversalPredictor:
    """
    Domain-agnostic predictive intelligence engine.

    The transition/counterfactual methods are intentionally implemented here,
    alongside the existing feature/ensemble path. This is the canonical
    one-backend predictive primitive used by all adapters and Oracle callers.
    """

    def __init__(self, config: Optional[PredictionConfig] = None):
        self.config = config or PredictionConfig()
        self.feature_extractor = UniversalFeatureExtractor()
        self.ensemble_engine = EnsembleIntelligenceEngine(self.config)
        self.risk_assessor = UniversalRiskAssessor()
        self.intervention_framework = InterventionFramework()
        self.transition_matrix: Optional[Any] = None
        self.transition_history: List[Dict[str, Any]] = []
        logger.info("Universal Predictor initialized")

    def predict(self, entity_data: Dict[str, List]) -> Dict[str, Any]:
        """Generate predictions for entity data."""
        try:
            indicators = self.feature_extractor.extract_indicators(entity_data)
            predictions = self.ensemble_engine.predict_ensemble(indicators)
            risk_assessment = self.risk_assessor.assess_risk(predictions)
            interventions = self.intervention_framework.generate_interventions(risk_assessment)
            return {
                "status": "success",
                "indicators": indicators,
                "predictions": predictions,
                "risk_assessment": risk_assessment,
                "interventions": interventions,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def predict_transition(
        self,
        history: Sequence[Sequence[float]],
        horizon: int = 1,
        learning_rate: float = 0.05,
    ) -> Dict[str, Any]:
        """Predict the next state from observed state transitions.

        This is the predictive-causal primitive:
        STATE_t -> T -> STATE_hat(t+1) -> OBSERVATION -> epsilon -> adaptation.
        T is learned from the supplied history only; no domain labels or
        domain-specific branches participate in the transition calculation.
        """
        if horizon < 1:
            raise ValueError("horizon must be >= 1")
        rows = []
        for state in history:
            row = [float(v) for v in state]
            if row:
                rows.append(row)
        if len(rows) < 2:
            return {
                "status": "INSUFFICIENT_DATA",
                "states_observed": len(rows),
                "prediction": None,
                "transition_matrix": None,
                "causal_signal": 0.0,
            }

        dim = min(len(r) for r in rows)
        x = __import__("numpy").asarray([r[:dim] for r in rows[:-1]], dtype=float)
        y = __import__("numpy").asarray([r[:dim] for r in rows[1:]], dtype=float)
        # Least-squares transition operator is data-derived, not a hard-coded
        # domain model. Bias is excluded so the causal primitive remains a
        # state-transition operator rather than a trend extrapolator.
        transition, _, _, _ = __import__("numpy").linalg.lstsq(x, y, rcond=None)
        t = transition.T
        self.transition_matrix = t

        current = __import__("numpy").asarray(rows[-1][:dim], dtype=float)
        predictions = []
        for _ in range(horizon):
            current = t @ current
            predictions.append(current.copy())

        fitted = (t @ x.T).T
        residual = y - fitted
        rmse = float(__import__("numpy").sqrt(__import__("numpy").mean(residual**2)))
        signal = float(1.0 / (1.0 + rmse))
        result = {
            "status": "success",
            "states_observed": len(rows),
            "dimension": dim,
            "prediction": predictions[-1].tolist(),
            "trajectory": [p.tolist() for p in predictions],
            "transition_matrix": t.tolist(),
            "prediction_rmse": rmse,
            "causal_signal": signal,
            "adaptation_ready": True,
        }
        self.transition_history.append(result)
        return result

    def adapt_transition(
        self,
        predicted_state: Sequence[float],
        actual_state: Sequence[float],
        learning_rate: float = 0.05,
    ) -> Dict[str, Any]:
        """Adapt the learned transition operator from prediction error."""
        if self.transition_matrix is None:
            return {"status": "NO_MODEL", "error_norm": None}
        import numpy as np

        pred = np.asarray(predicted_state, dtype=float)
        actual = np.asarray(actual_state, dtype=float)
        dim = min(pred.size, actual.size, self.transition_matrix.shape[0])
        pred = pred[:dim]
        actual = actual[:dim]
        epsilon = actual - pred
        error_norm = float(np.linalg.norm(epsilon))
        denom = float(np.dot(pred, pred)) + 1e-12
        self.transition_matrix[:dim, :dim] += float(learning_rate) * np.outer(epsilon, pred) / denom
        spectral_radius = float(np.max(np.abs(np.linalg.eigvals(self.transition_matrix))))
        if spectral_radius > 1.2:
            self.transition_matrix /= spectral_radius
            spectral_radius = float(np.max(np.abs(np.linalg.eigvals(self.transition_matrix))))
        return {
            "status": "adapted",
            "error_norm": error_norm,
            "spectral_radius": spectral_radius,
            "transition_matrix": self.transition_matrix.tolist(),
        }

    def counterfactual(
        self,
        current_state: Sequence[float],
        perturbations: Dict[str, Sequence[float]],
        horizon: int = 1,
    ) -> Dict[str, Any]:
        """Compare future trajectories under explicit state perturbations."""
        if self.transition_matrix is None:
            raise ValueError("predict_transition must establish a transition model first")
        import numpy as np

        base = np.asarray(current_state, dtype=float)
        outcomes: Dict[str, Any] = {}
        for name, delta in perturbations.items():
            candidate = base + np.asarray(delta, dtype=float)
            for _ in range(horizon):
                candidate = self.transition_matrix @ candidate
            outcomes[name] = {
                "state": candidate.tolist(),
                "norm": float(np.linalg.norm(candidate)),
            }
        return {"status": "success", "horizon": horizon, "scenarios": outcomes}
