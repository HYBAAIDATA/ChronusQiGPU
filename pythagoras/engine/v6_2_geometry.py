"""V6.2 Engine: dynamic CGP-inspired search geometry.

``n_cols`` is the number of ranked operators evaluated per generation.
``levels_back`` is the maximum composite-recipe length.  No DAG population is
represented or evolved.
"""
from typing import Dict, List, Tuple, Any, Optional, Callable
from pythagoras.core.phi_metric import PhiResonanceCalculator
from pythagoras.core import sandbox
from pythagoras.core.primitives import ASTPrimitives
from pythagoras.engine.v6_1_surrogate import NeuralSurrogateEvaluator

class CGPGeometryState:
    def __init__(self, initial_n_cols: int = 12, initial_levels_back: int = 3, pop_size: int = 10):
        self.n_cols: int = initial_n_cols
        self.levels_back: int = initial_levels_back
        _ = pop_size  # retained only for constructor compatibility; search has no population
        self.total_expansions: int = 0
        self.total_contractions: int = 0
        self.stall_counter: int = 0

    def adapt(self, generation_velocity: float) -> Tuple[bool, str]:
        if generation_velocity > 0.005:
            self.n_cols += 2
            self.levels_back += 1
            self.total_expansions += 1
            self.stall_counter = 0
            return True, f"EXPANDED: n_cols={self.n_cols}, levels_back={self.levels_back}"
        elif abs(generation_velocity) < 1e-6:
            self.stall_counter += 1
            if self.stall_counter >= 2 and self.n_cols > 8:
                self.n_cols -= 1
                self.total_contractions += 1
                self.stall_counter = 0
                return True, f"STALL_RECONFIGURED: n_cols={self.n_cols}, levels_back={self.levels_back}"
        else:
            self.stall_counter = 0

        return False, "UNCHANGED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_cols": self.n_cols,
            "levels_back": self.levels_back,
            "total_expansions": self.total_expansions,
            "total_contractions": self.total_contractions
        }

    @classmethod
    def from_dict(cls, state: Optional[Dict[str, Any]] = None) -> "CGPGeometryState":
        state = state or {}
        obj = cls(
            initial_n_cols=int(state.get("n_cols", 12)),
            initial_levels_back=int(state.get("levels_back", 3)),
        )
        obj.total_expansions = int(state.get("total_expansions", 0))
        obj.total_contractions = int(state.get("total_contractions", 0))
        return obj


class CollectiveGeometryCoordinator:
    """Shares bounded geometry knowledge across files and sessions.

    Each completed file contributes its terminal geometry.  The next file starts
    from the robust median of prior observations, bounded to conservative limits.
    This is deliberately consensus, not an unbounded ratchet.
    """
    def __init__(self, state: Optional[Dict[str, Any]] = None):
        state = state or {}
        self.observations: List[Dict[str, Any]] = list(state.get("observations", []))[-100:]

    def initial_state(self) -> CGPGeometryState:
        if not self.observations:
            return CGPGeometryState()
        cols = sorted(int(x["n_cols"]) for x in self.observations)
        levels = sorted(int(x["levels_back"]) for x in self.observations)
        mid = len(cols) // 2
        return CGPGeometryState(
            initial_n_cols=max(8, min(32, cols[mid])),
            initial_levels_back=max(2, min(8, levels[mid])),
        )

    def observe(self, target: str, geometry: CGPGeometryState, delta_phi: float) -> None:
        self.observations.append({
            "target": target,
            "n_cols": geometry.n_cols,
            "levels_back": geometry.levels_back,
            "delta_phi": round(float(delta_phi), 6),
        })
        self.observations = self.observations[-100:]

    def to_dict(self) -> Dict[str, Any]:
        return {"observations": list(self.observations)}

class V62DynamicGeometryEngine:
    def __init__(self, target_phi: float = 0.618033988749895, seed: int = 42):
        self.seed = seed
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
        max_generations: int = 20,
        external_test_runner: Optional[Callable[[str], bool]] = None
    ) -> Dict[str, Any]:
        current_code = initial_code
        current_score = self.calculator.compute_phi(current_code)
        initial_score = current_score

        geometry = CGPGeometryState(initial_n_cols=12, initial_levels_back=3, pop_size=10)
        accepted_steps = []
        total_evals_attempted = 0
        total_evals_valid = 0
        evals_skipped_by_surrogate = 0

        for gen in range(1, max_generations + 1):
            features = self.calculator.extract_features(current_code)
            gen_start_score = current_score

            ranked_ops = []
            for op_name, op_func in self.operators:
                if self.surrogate.is_anti_primitive(op_name):
                    evals_skipped_by_surrogate += 1
                    continue
                pred_gain = self.surrogate.predict_gain(features, op_name)
                ranked_ops.append((pred_gain, op_name, op_func))

            ranked_ops.sort(key=lambda x: x[0], reverse=True)
            valid_candidates = []

            for pred_gain, op_name, op_func in ranked_ops:
                total_evals_attempted += 1
                cand_code, _ = op_func(current_code, self.seed + gen)
                p_v, c_v, r_v = self.verify_validity(cand_code, external_test_runner)

                if p_v and c_v and r_v:
                    total_evals_valid += 1
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
                    "new_phi": current_score,
                    "geometry_state": geometry.to_dict()
                })

            gen_velocity = current_score - gen_start_score
            geometry.adapt(gen_velocity)

        return {
            "target": target_name,
            "seed": self.seed,
            "initial_phi": initial_score,
            "final_phi": current_score,
            "total_delta_phi": round(current_score - initial_score, 6),
            "total_evals_attempted": total_evals_attempted,
            "total_evals_valid": total_evals_valid,
            "accepted_steps_count": len(accepted_steps),
            "final_geometry_state": geometry.to_dict()
        }
