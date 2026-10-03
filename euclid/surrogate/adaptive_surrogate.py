"""
EUCLID Adaptive Operator Surrogate Model
===========================================
Predicts expected operator gain (delta_phi) using online feature-driven gradient updates.
Maintains anti-primitive suppression lists for repeatedly failing transformations.
"""

import math
from typing import Dict, List, Tuple, Any

class AdaptiveOperatorSurrogate:
    """
    Adaptive Operator Surrogate Model.
    Predicts expected gain given AST feature vector and operator,
    updating weights via online error feedback.
    """
    def __init__(self, learning_rate: float = 0.05):
        self.learning_rate = learning_rate
        self.operator_weights: Dict[str, List[float]] = {
            "ADD:AnnAssign": [0.1, 0.2, 0.8, 0.3, 0.2],
            "NON_LOCAL:function_split_refactor": [0.5, 0.6, 0.1, 0.4, 0.5],
            "MUTATE:rename_variable": [0.0, 0.0, -0.1, 0.0, 0.0],
            "MUTATE:swap_binary_operator": [-0.2, -0.1, 0.0, 0.0, -0.2],
            "MUTATE:inject_docstring": [0.0, 0.0, 0.1, 0.0, 0.0],
            "MUTATE:dead_code_branch": [0.0, 0.0, 0.0, 0.0, 0.0],
            "MUTATE:list_comprehension": [-0.5, -0.4, -0.2, -0.3, -0.4]
        }
        self.anti_primitives: Dict[str, int] = {}
        self.prediction_history: List[Tuple[float, float]] = []

    def _extract_feature_vector(self, features: Dict[str, Any]) -> List[float]:
        return [
            min(features.get("node_count", 10) / 100.0, 1.0),
            min(features.get("depth", 3) / 10.0, 1.0),
            float(features.get("annotation_density", 0.0)),
            min(features.get("function_count", 1) / 5.0, 1.0),
            min(features.get("statement_count", 5) / 20.0, 1.0)
        ]

    def predict_gain(self, features: Dict[str, Any], op_name: str) -> float:
        if self.is_anti_primitive(op_name):
            return -0.0500

        w = self.operator_weights.get(op_name, [0.0] * 5)
        f = self._extract_feature_vector(features)
        dot = sum(wi * fi for wi, fi in zip(w, f))
        pred = (1.0 / (1.0 + math.exp(-dot)) - 0.5) * 0.10
        return round(pred, 6)

    def is_anti_primitive(self, op_name: str) -> bool:
        return self.anti_primitives.get(op_name, 0) >= 3

    def update(self, features: Dict[str, Any], op_name: str, actual_delta: float, parse_v: bool, test_v: bool):
        if op_name not in self.operator_weights:
            self.operator_weights[op_name] = [0.0] * 5

        pred = self.predict_gain(features, op_name)
        self.prediction_history.append((pred, actual_delta))

        # Register anti-primitive if candidate broke syntax/test repeatedly
        if not parse_v or not test_v or actual_delta < -0.05:
            self.anti_primitives[op_name] = self.anti_primitives.get(op_name, 0) + 1
        else:
            self.anti_primitives[op_name] = max(0, self.anti_primitives.get(op_name, 0) - 1)

        # Online SGD update
        error = actual_delta - pred
        f = self._extract_feature_vector(features)
        self.operator_weights[op_name] = [
            round(wi + self.learning_rate * error * fi, 6)
            for wi, fi in zip(self.operator_weights[op_name], f)
        ]

    def compute_rmse(self) -> float:
        if not self.prediction_history:
            return 0.0
        mse = sum((p - a) ** 2 for p, a in self.prediction_history) / len(self.prediction_history)
        return round(math.sqrt(mse), 6)

# Alias for backward compatibility
NeuralSurrogateEvaluator = AdaptiveOperatorSurrogate
