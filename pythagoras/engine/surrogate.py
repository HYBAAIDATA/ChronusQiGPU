"""Surrogate guidance used by the production PYTHAGORAS evolution engine.

This module intentionally contains no historical staged engine. The surrogate is a
reusable component: it ranks operators, learns from measured candidate outcomes and
records anti-primitives as explicit negative evidence.
"""

import math
from typing import Any, Dict, List, Optional, Tuple


class NeuralSurrogateEvaluator:
    """Small online surrogate over structural features and operator identity."""

    def __init__(self, learning_rate: float = 0.05):
        self.learning_rate = learning_rate
        self.operator_weights: Dict[str, List[float]] = {
            "ADD:AnnAssign": [0.1, 0.2, 0.8, 0.3, 0.2],
            "NON_LOCAL:function_split_refactor": [0.5, 0.6, 0.1, 0.4, 0.5],
            "MUTATE:rename_variable": [0.0, 0.0, -0.1, 0.0, 0.0],
            "MUTATE:swap_binary_operator": [-0.2, -0.1, 0.0, 0.0, -0.2],
            "MUTATE:inject_docstring": [0.0, 0.0, 0.1, 0.0, 0.0],
            "MUTATE:dead_code_branch": [0.0, 0.0, 0.0, 0.0, 0.0],
            "MUTATE:list_comprehension": [-0.5, -0.4, -0.2, -0.3, -0.4],
        }
        self.anti_primitives: Dict[str, int] = {}
        self.adversarial_catalog: Dict[str, Dict[str, Any]] = {}
        self.prediction_history: List[Tuple[float, float]] = []

    def _extract_feature_vector(self, features: Dict[str, Any]) -> List[float]:
        return [
            min(features.get("node_count", 10) / 100.0, 1.0),
            min(features.get("depth", 3) / 10.0, 1.0),
            float(features.get("annotation_density", 0.0)),
            min(features.get("function_count", 1) / 5.0, 1.0),
            min(features.get("statement_count", 5) / 20.0, 1.0),
        ]

    def predict_gain(self, features: Dict[str, Any], op_name: str) -> float:
        if self.anti_primitives.get(op_name, 0) >= 3:
            return -0.05
        weights = self.operator_weights.get(op_name, [0.0] * 5)
        vector = self._extract_feature_vector(features)
        dot = sum(weight * feature for weight, feature in zip(weights, vector))
        return round((1.0 / (1.0 + math.exp(-dot)) - 0.5) * 0.10, 6)

    def is_anti_primitive(self, op_name: str) -> bool:
        return self.anti_primitives.get(op_name, 0) >= 3

    def update(
        self,
        features: Dict[str, Any],
        op_name: str,
        actual_delta: float,
        parse_valid: bool,
        test_valid: bool,
    ) -> None:
        if op_name not in self.operator_weights:
            self.operator_weights[op_name] = [0.0] * 5
        prediction = self.predict_gain(features, op_name)
        self.prediction_history.append((prediction, actual_delta))

        if not parse_valid or not test_valid or actual_delta < -0.05:
            self.anti_primitives[op_name] = self.anti_primitives.get(op_name, 0) + 1
        else:
            self.anti_primitives[op_name] = max(0, self.anti_primitives.get(op_name, 0) - 1)

        error = actual_delta - prediction
        vector = self._extract_feature_vector(features)
        self.operator_weights[op_name] = [
            round(weight + self.learning_rate * error * feature, 6)
            for weight, feature in zip(self.operator_weights[op_name], vector)
        ]
        if self.is_anti_primitive(op_name):
            self._generate_adversarial_model(op_name, actual_delta)

    def _generate_adversarial_model(self, op_name: str, actual_delta: float) -> None:
        """Create a non-executable negative operator model for discrimination."""
        anti_name = f"ANTI:{op_name}"
        base = self.operator_weights.get(op_name, [0.0] * 5)
        self.adversarial_catalog[anti_name] = {
            "source_operator": op_name,
            "failures": self.anti_primitives.get(op_name, 0),
            "last_delta": round(float(actual_delta), 6),
            "weights": [round(-abs(weight) - 0.05, 6) for weight in base],
        }

    def export_state(self) -> Dict[str, Any]:
        return {
            "learning_rate": self.learning_rate,
            "operator_weights": self.operator_weights,
            "anti_primitives": self.anti_primitives,
            "adversarial_catalog": self.adversarial_catalog,
        }

    def import_state(self, state: Optional[Dict[str, Any]]) -> None:
        if not state:
            return
        self.learning_rate = float(state.get("learning_rate", self.learning_rate))
        self.operator_weights.update(
            {
                str(key): [float(value) for value in values]
                for key, values in state.get("operator_weights", {}).items()
            }
        )
        self.anti_primitives = {
            str(key): int(value) for key, value in state.get("anti_primitives", {}).items()
        }
        self.adversarial_catalog = dict(state.get("adversarial_catalog", {}))

    def compute_rmse(self) -> float:
        if not self.prediction_history:
            return 0.0
        mse = sum((predicted - actual) ** 2 for predicted, actual in self.prediction_history)
        mse /= len(self.prediction_history)
        return round(math.sqrt(mse), 6)
