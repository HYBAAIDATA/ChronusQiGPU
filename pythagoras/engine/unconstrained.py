"""
V6.0 Minimal Unconstrained Research Engine
"""
from typing import Dict, Tuple, Any, Optional, Callable
from pythagoras.core.phi_metric import PhiResonanceCalculator
from pythagoras.core import sandbox
from pythagoras.core.primitives import ASTPrimitives

class V60UnconstrainedEngine:
    def __init__(self, target_phi: float = 0.618033988749895):
        self.calculator = PhiResonanceCalculator(target_phi)
        self.operators = ASTPrimitives.get_all_operators()

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
        valid_evaluations_count = 0
        accepted_steps = []

        for gen in range(1, generations + 1):
            valid_candidates = []
            for op_name, op_func in self.operators:
                evaluations_attempted += 1
                cand_code, _ = op_func(current_code, seed + gen)
                p_v, c_v, r_v = self.verify_validity(cand_code, external_test_runner)

                if p_v and c_v and r_v:
                    valid_evaluations_count += 1
                    cand_score = self.calculator.compute_phi(cand_code)
                    actual_delta = round(cand_score - current_score, 6)
                    if cand_score > current_score:
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
            "valid_evaluations_count": valid_evaluations_count,
            "accepted_steps_count": len(accepted_steps),
            "accepted_steps": accepted_steps,
            "final_code": current_code
        }
