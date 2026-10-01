"""
V6.3 Engine: Auto-Primitive Discovery & Operator-Space Exploration
"""
from typing import Dict, List, Tuple, Any, Optional, Callable
from pythagoras.core.phi_metric import PhiResonanceCalculator
from pythagoras.core import sandbox
from pythagoras.core.primitives import ASTPrimitives, OPERATOR_REGISTRY, compose
from pythagoras.engine.v6_1_surrogate import NeuralSurrogateEvaluator
from pythagoras.engine.v6_2_geometry import CGPGeometryState

class DiscoveredPrimitiveCandidate:
    def __init__(self, name: str, op_func: Callable[[str, int], Tuple[str, str]], discovery_gen: int,
                 origin_target: str, recipe: Optional[List[str]] = None):
        self.name = name
        self.op_func = op_func
        self.recipe = recipe or list(getattr(op_func, "recipe", []) or [])
        self.discovery_gen = discovery_gen
        self.origin_target = origin_target
        self.evaluation_trials: int = 0
        self.successful_gains: int = 0
        self.cumulative_delta_phi: float = 0.0
        self.is_promoted: bool = False

    def record_trial(self, delta_phi: float, parse_v: bool, test_v: bool):
        self.evaluation_trials += 1
        if parse_v and test_v and delta_phi > 0:
            self.successful_gains += 1
            self.cumulative_delta_phi += delta_phi

    def check_promotion_eligibility(self) -> bool:
        if self.is_promoted:
            return False
        if self.evaluation_trials >= 2 and self.successful_gains >= 1 and self.cumulative_delta_phi > 0:
            self.is_promoted = True
            return True
        return False


class PrimitiveDiscoveryEngine:
    """
    Discovers macro-operators from the search trajectory: when consecutive generations are
    won by operators A then B, the composite A+B (and longer chains, up to `max_recipe_len`,
    which the CGP-inspired geometry's levels_back recipe-depth limit controls) enters the sandbox pool. A composite is
    promoted once it has produced a real φ gain. Composites are recipes over the operator
    registry, so they persist and restore exactly.
    """
    def __init__(self):
        self.sandbox_pool: Dict[str, DiscoveredPrimitiveCandidate] = {}
        self.promoted_vocabulary: Dict[str, Callable[[str, int], Tuple[str, str]]] = {}
        self.winner_history: List[List[str]] = []
        self.max_recipe_len: int = 3

    @staticmethod
    def _recipe_of(op_name: str, op_func: Optional[Callable] = None) -> List[str]:
        if op_func is not None and getattr(op_func, "recipe", None):
            return list(op_func.recipe)
        return [op_name] if op_name in OPERATOR_REGISTRY else []

    def discover_from_transformation(self, code_before: str, code_after: str, winning_op_name: str, gen: int,
                                     target_name: str, winning_op_func: Optional[Callable] = None
                                     ) -> Optional[DiscoveredPrimitiveCandidate]:
        recipe = self._recipe_of(winning_op_name, winning_op_func)
        if not recipe:
            return None
        self.winner_history.append(recipe)
        if len(self.winner_history) < 2:
            return None
        chain: List[str] = []
        for r in reversed(self.winner_history):
            if len(chain) + len(r) > self.max_recipe_len:
                break
            chain = r + chain
            if len(chain) >= 2:
                break
        if len(chain) < 2:
            return None
        op = compose(chain)
        new_name = op.__name__
        if new_name in self.sandbox_pool or new_name in self.promoted_vocabulary:
            return None
        cand = DiscoveredPrimitiveCandidate(new_name, op, gen, target_name, chain)
        self.sandbox_pool[new_name] = cand
        return cand


class V63AutoPrimitiveEngine:
    def __init__(self, target_phi: float = 0.618033988749895, seed: int = 42):
        self.seed = seed
        self.calculator = PhiResonanceCalculator(target_phi)
        self.base_operators = ASTPrimitives.get_all_operators()
        self.surrogate = NeuralSurrogateEvaluator(learning_rate=0.05)
        self.discovery_engine = PrimitiveDiscoveryEngine()

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
        discovery_events = []
        promoted_primitives_summary = []

        total_evals_attempted = 0
        total_evals_valid = 0

        for gen in range(1, max_generations + 1):
            features = self.calculator.extract_features(current_code)
            gen_start_score = current_score

            active_ops = list(self.base_operators)
            for pname, pfunc in self.discovery_engine.promoted_vocabulary.items():
                active_ops.append((pname, pfunc))

            for sname, scand in self.discovery_engine.sandbox_pool.items():
                if not scand.is_promoted:
                    active_ops.append((sname, scand.op_func))

            ranked_ops = []
            for op_name, op_func in active_ops:
                if self.surrogate.is_anti_primitive(op_name):
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

                if op_name in self.discovery_engine.sandbox_pool:
                    cand = self.discovery_engine.sandbox_pool[op_name]
                    cand.record_trial(actual_delta, p_v, r_v)
                    if cand.check_promotion_eligibility():
                        self.discovery_engine.promoted_vocabulary[op_name] = cand.op_func
                        promoted_primitives_summary.append({
                            "primitive_name": op_name,
                            "promotion_gen": gen,
                            "cumulative_delta_phi": round(cand.cumulative_delta_phi, 6)
                        })

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
                prev_code = current_code
                current_code = winner["candidate_code"]
                current_score = winner["candidate_score"]

                accepted_steps.append({
                    "generation": gen,
                    "winning_operator": winner["op_name"],
                    "delta_phi": winner["delta_phi"],
                    "new_phi": current_score
                })

                disc = self.discovery_engine.discover_from_transformation(
                    prev_code, current_code, winner["op_name"], gen, target_name
                )
                if disc:
                    discovery_events.append({
                        "generation": gen,
                        "discovered_primitive": disc.name
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
            "discovery_events_count": len(discovery_events),
            "promoted_primitives_count": len(promoted_primitives_summary)
        }
