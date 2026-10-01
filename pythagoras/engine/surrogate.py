"""
V6.1 Engine: Neural Surrogate Guidance
"""
import math
from typing import Dict, List, Tuple, Any, Optional, Callable
from pythagoras.core.phi_metric import PhiResonanceCalculator
from pythagoras.core import sandbox
from pythagoras.core.primitives import ASTPrimitives

class NeuralSurrogateEvaluator:
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
        self.adversarial_catalog: Dict[str, Dict[str, Any]] = {}
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
        if self.anti_primitives.get(op_name, 0) >= 3:
            return -0.05
        w = self.operator_weights.get(op_name, [0.0]*5)
        f = self._extract_feature_vector(features)
        dot = sum(wi * fi for wi, fi in zip(w, f))
        return round((1.0 / (1.0 + math.exp(-dot)) - 0.5) * 0.10, 6)

    def is_anti_primitive(self, op_name: str) -> bool:
        return self.anti_primitives.get(op_name, 0) >= 3

    def update(self, features: Dict[str, Any], op_name: str, actual_delta: float, parse_valid: bool, test_valid: bool):
        if op_name not in self.operator_weights:
            self.operator_weights[op_name] = [0.0]*5
        pred = self.predict_gain(features, op_name)
        self.prediction_history.append((pred, actual_delta))

        if not parse_valid or not test_valid or actual_delta < -0.05:
            self.anti_primitives[op_name] = self.anti_primitives.get(op_name, 0) + 1
        else:
            self.anti_primitives[op_name] = max(0, self.anti_primitives.get(op_name, 0) - 1)

        error = actual_delta - pred
        f = self._extract_feature_vector(features)
        self.operator_weights[op_name] = [
            round(wi + self.learning_rate * error * fi, 6)
            for wi, fi in zip(self.operator_weights[op_name], f)
        ]
        if self.is_anti_primitive(op_name):
            self._generate_adversarial_model(op_name, actual_delta)

    def _generate_adversarial_model(self, op_name: str, actual_delta: float) -> None:
        """Creates a non-executable negative operator model for discrimination.

        Anti-primitives are never offered as source transforms.  They are explicit
        learned counterexamples with a stable signature and pessimistic weights.
        """
        anti_name = f"ANTI:{op_name}"
        base = self.operator_weights.get(op_name, [0.0] * 5)
        self.adversarial_catalog[anti_name] = {
            "source_operator": op_name,
            "failures": self.anti_primitives.get(op_name, 0),
            "last_delta": round(float(actual_delta), 6),
            "weights": [round(-abs(w) - 0.05, 6) for w in base],
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
        self.operator_weights.update({
            str(k): [float(x) for x in v]
            for k, v in state.get("operator_weights", {}).items()
        })
        self.anti_primitives = {str(k): int(v) for k, v in state.get("anti_primitives", {}).items()}
        self.adversarial_catalog = dict(state.get("adversarial_catalog", {}))

    def compute_rmse(self) -> float:
        if not self.prediction_history:
            return 0.0
        mse = sum((p - a)**2 for p, a in self.prediction_history) / len(self.prediction_history)
        return round(math.sqrt(mse), 6)

class V61SurrogateEngine:
    def __init__(self, target_phi: float = 0.618033988749895):
        self.calculator = PhiResonanceCalculator(target_phi)
        self.operators = ASTPrimitives.get_all_operators()
        self.surrogate = NeuralSurrogateEvaluator(learning_rate=0.05)

    def verify_validity(self, code_str: str, external_test_runner: Optional[Callable[[str], bool]] = None) -> Tuple[bool, bool, bool]:
        """Delegates to the AL HARAS isolated validity gate (pythagoras.core.sandbox)."""
        return sandbox.verify_validity(code_str, external_test_runner)

    def run_optimization(
        self, 
        target_name: str, 
        initial_code: str, 
        generations: int = 20, 
        seed: int = 42,
        external_test_runner: Optional[Callable[[str], bool]] = None
    ) -> Dict[str, Any]:
        current_code = initial_code
        current_score = self.calculator.compute_phi(current_code)
        initial_score = current_score

        evaluations_attempted = 0
        evaluations_skipped_by_surrogate = 0
        valid_evaluations_count = 0
        accepted_steps = []

        for gen in range(1, generations + 1):
            features = self.calculator.extract_features(current_code)
            ranked_ops = []
            for op_name, op_func in self.operators:
                if self.surrogate.is_anti_primitive(op_name):
                    evaluations_skipped_by_surrogate += 1
                    continue
                pred_gain = self.surrogate.predict_gain(features, op_name)
                ranked_ops.append((pred_gain, op_name, op_func))

            ranked_ops.sort(key=lambda x: x[0], reverse=True)
            valid_candidates = []

            for pred_gain, op_name, op_func in ranked_ops:
                evaluations_attempted += 1
                cand_code, _ = op_func(current_code, seed + gen)
                p_v, c_v, r_v = self.verify_validity(cand_code, external_test_runner)

                if p_v and c_v and r_v:
                    valid_evaluations_count += 1
                    cand_score = self.calculator.compute_phi(cand_code)
                    actual_delta = round(cand_score - current_score, 6)
                else:
                    cand_score = 0.1000
                    actual_delta = -0.5000

                self.surrogate.update(features, op_name, actual_delta, p_v, r_v)

                if (cand_score > current_score) and p_v and c_v and r_v:
                    valid_candidates.append({
                        "candidate_code": cand_code,
                        "candidate_score": cand_score,
                        "delta_phi": actual_delta,
                        "op_name": op_name
                    })

            if valid_candidates:
                valid_candidates.sort(key=lambda x: x["candidate_score"], reverse=True)
                winner = valid_candidates[0]
                current_code = winner["candidate_code"]
                current_score = winner["candidate_score"]
                accepted_steps.append({
                    "generation": gen,
                    "winning_operator": winner["op_name"],
                    "delta_phi": winner["delta_phi"],
                    "new_phi": current_score
                })

        return {
            "target": target_name,
            "seed": seed,
            "initial_phi": initial_score,
            "final_phi": current_score,
            "total_delta_phi": round(current_score - initial_score, 6),
            "evaluations_attempted": evaluations_attempted,
            "evaluations_skipped_by_surrogate": evaluations_skipped_by_surrogate,
            "valid_evaluations_count": valid_evaluations_count,
            "accepted_steps_count": len(accepted_steps),
            "accepted_steps": accepted_steps,
            "final_code": current_code
        }
