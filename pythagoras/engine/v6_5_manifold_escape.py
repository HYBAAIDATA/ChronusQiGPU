"""
V6.5 Engine: Non-Local AST Restructuring & Degenerate Manifold Escape
=====================================================================
Greedy φ-ascent over real source transforms, with:
  - AL HARAS isolated validity gate (core.sandbox) on every changed candidate
  - EUCLID co-gate: a candidate is accepted only if φ rises AND EUCLID intelligence
    (L(x) at fixed t_p) does not fall — the monotonicity invariant holds by construction
  - PYTHIA surrogate ranking; CGP geometry sets search breadth (n_cols = operators
    evaluated per generation) and composite depth (levels_back = max recipe length)
  - manifold escape: after two stalled generations NON_LOCAL operators get a ranking bonus
  - behaviour-changing operators enabled only when the host supplies a test runner
  - meta_evolution switch (21 March A/B protocol): OFF = fixed base operator set, frozen
    surrogate priors, fixed CGP geometry, no discovery/promotion/transfer
  - ENH-09 phase-transition tagging: an accepted step is tagged when its Δφ is at least
    PHASE_TRANSITION_RATIO × the median of earlier accepted Δφ (needs ≥ 2 earlier steps);
    composite steps are additionally tagged as barrier crossings when their first component
    alone would not have been accepted on the same code
"""
import ast
import math
import random
import statistics
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from pythagoras.core import sandbox
from pythagoras.core.euclid_intelligence import EuclidIntelligenceEngine
from pythagoras.core.phi_metric import PhiResonanceCalculator
from pythagoras.core.primitives import ASTPrimitives, OPERATOR_REGISTRY
from pythagoras.engine.v6_1_surrogate import NeuralSurrogateEvaluator
from pythagoras.engine.v6_2_geometry import CGPGeometryState, CollectiveGeometryCoordinator
from pythagoras.engine.v6_3_primitive_discovery import PrimitiveDiscoveryEngine
from pythagoras.engine.v6_4_cross_file_reuse import CrossFilePrimitiveRepository


class NonLocalASTMutators:
    function_split_refactor = staticmethod(OPERATOR_REGISTRY["NON_LOCAL:function_split_refactor"])
    conditional_flattening = staticmethod(OPERATOR_REGISTRY["NON_LOCAL:conditional_flattening"])
    class_decomposition = staticmethod(OPERATOR_REGISTRY["NON_LOCAL:class_decomposition"])

    @classmethod
    def get_non_local_operators(cls) -> List[Tuple[str, Callable[[str, int], Tuple[str, str]]]]:
        return [
            ("NON_LOCAL:function_split_refactor", cls.function_split_refactor),
            ("NON_LOCAL:conditional_flattening", cls.conditional_flattening),
            ("NON_LOCAL:class_decomposition", cls.class_decomposition),
        ]


PHASE_TRANSITION_RATIO = 3.0


@dataclass
class AnnealingConfig:
    enabled: bool = False
    initial_temperature: float = 0.02
    cooling_rate: float = 0.90
    minimum_temperature: float = 0.001
    activate_after_stalls: int = 2


def phase_transition_ratio(delta: float, prior_deltas: List[float]) -> Optional[float]:
    """Δφ of a step relative to the median of earlier accepted steps (None if < 2 earlier steps)."""
    if len(prior_deltas) < 2:
        return None
    med = statistics.median(prior_deltas)
    return delta / med if med > 0 else None


class V65ManifoldEscapeEngine:
    def __init__(self, repository: Optional[CrossFilePrimitiveRepository] = None,
                 target_phi: float = 0.618033988749895, seed: int = 42,
                 sandbox_config: Optional[sandbox.SandboxConfig] = None, euclid_gate: bool = True,
                 meta_evolution: bool = True, allow_behaviour_changing: Optional[bool] = None,
                 annealing: Optional[AnnealingConfig] = None,
                 geometry_signal: str = "measured_phi",
                 collective_geometry: Optional[CollectiveGeometryCoordinator] = None):
        self.seed = seed
        self.calculator = PhiResonanceCalculator(target_phi)
        self.euclid = EuclidIntelligenceEngine()
        self.non_local_operators = NonLocalASTMutators.get_non_local_operators()
        self.surrogate = NeuralSurrogateEvaluator(learning_rate=0.05)
        self.discovery_engine = PrimitiveDiscoveryEngine()
        self.cross_file_repo = repository or CrossFilePrimitiveRepository()
        self.sandbox_config = sandbox_config or sandbox.DEFAULT_CONFIG
        self.euclid_gate = euclid_gate
        self.meta_evolution = meta_evolution
        self.allow_behaviour_changing = allow_behaviour_changing  # None: enabled iff a test runner is given
        self.annealing = annealing or AnnealingConfig()
        if geometry_signal not in ("measured_phi", "surrogate_velocity"):
            raise ValueError("geometry_signal must be 'measured_phi' or 'surrogate_velocity'")
        self.geometry_signal = geometry_signal
        self.collective_geometry = collective_geometry or CollectiveGeometryCoordinator()
        self.last_geometry_state: Dict[str, Any] = {}

    @property
    def base_operators(self):
        return ASTPrimitives.get_all_operators()

    def verify_validity(self, code_str: str, external_test_runner: Optional[Callable[[str], bool]] = None) -> Tuple[bool, bool, bool]:
        """parse_v, compile_v, runtime_v — via the AL HARAS isolated gate (core.sandbox)."""
        return sandbox.verify_validity(code_str, external_test_runner, self.sandbox_config)

    def _learn(self, features, op_name, delta, p_v, r_v):
        """Surrogate learns only under meta-evolution; with meta OFF predictions are still
        recorded so RMSE is comparable across conditions."""
        if self.meta_evolution:
            self.surrogate.update(features, op_name, delta, p_v, r_v)
        else:
            self.surrogate.prediction_history.append((self.surrogate.predict_gain(features, op_name), delta))

    def _intelligence(self, code: str) -> float:
        return self.euclid.compute_intelligence_scale(code, 0.0)["intelligence_score"]

    def _active_operators(self, behaviour_changing: bool):
        ops: Dict[str, Callable] = {}
        for name, fn in ASTPrimitives.get_all_operators(include_behaviour_changing=behaviour_changing):
            ops[name] = fn
        for name, fn in self.non_local_operators:
            ops.setdefault(name, fn)
        if not self.meta_evolution:
            return list(ops.items())
        for name, fn in self.discovery_engine.promoted_vocabulary.items():
            ops.setdefault(name, fn)
        for name, cand in self.discovery_engine.sandbox_pool.items():
            if not cand.is_promoted:
                ops.setdefault(name, cand.op_func)
        return list(ops.items())

    def _would_accept(self, code: str, op_name: str, current_score: float, current_intel: float,
                      external_test_runner) -> bool:
        cand, _ = OPERATOR_REGISTRY[op_name](code, self.seed)
        if cand == code:
            return False
        rec = sandbox.validate(cand, external_test_runner, self.sandbox_config)
        if not (rec["parse_valid"] and rec["compile_valid"] and rec["runtime_valid"]):
            return False
        if self.calculator.compute_phi(cand) <= current_score:
            return False
        return not (self.euclid_gate and self._intelligence(cand) < current_intel)

    def run_optimization(self, target_name: str, initial_code: str, max_generations: int = 20,
                         external_test_runner: Optional[Callable[[str], bool]] = None) -> Dict[str, Any]:
        start_time = time.time()
        current_code = initial_code
        current_score = self.calculator.compute_phi(current_code)
        current_intel = self._intelligence(current_code)
        current_n = self.euclid.calculate_lucas_index(current_code)[0]
        initial_score = current_score
        best_code, best_score, best_intel = current_code, current_score, current_intel

        behaviour_changing = external_test_runner is not None if self.allow_behaviour_changing is None \
            else (self.allow_behaviour_changing and external_test_runner is not None)
        geometry = self.collective_geometry.initial_state()
        initial_geometry = geometry.to_dict()
        initial_ops = {n for n, _ in self._active_operators(behaviour_changing)}
        geometry_steps, meta_steps, accepted_generations = [], 0, 0
        prior_deltas: List[float] = []
        accepted_steps, discovery_events, promoted_summary = [], [], []
        cross_file_reuses, escapes, phase_transitions, validity_failures, annealing_escapes = [], [], [], [], []
        total_attempted = total_valid = no_site = euclid_rejections = 0
        stall_counter = 0
        previous_surrogate_signal: Optional[float] = None
        rng = random.Random(self.seed)

        if self.meta_evolution:
            for pname, pfunc in self.cross_file_repo.get_all_transfer_primitives():
                self.discovery_engine.promoted_vocabulary[pname] = pfunc
            initial_ops = {n for n, _ in self._active_operators(behaviour_changing)}

        for gen in range(1, max_generations + 1):
            self.discovery_engine.max_recipe_len = geometry.levels_back
            vocab_before = len(self.discovery_engine.promoted_vocabulary) + len(self.discovery_engine.sandbox_pool)
            features = self.calculator.extract_features(current_code)
            gen_start_score = current_score

            ranked = []
            for op_name, op_func in self._active_operators(behaviour_changing):
                if self.surrogate.is_anti_primitive(op_name):
                    continue
                pred = self.surrogate.predict_gain(features, op_name)
                if stall_counter >= 2 and op_name.startswith("NON_LOCAL:"):
                    pred += 0.05
                ranked.append((pred, op_name, op_func))
            ranked.sort(key=lambda x: x[0], reverse=True)
            ranked = ranked[: max(1, geometry.n_cols)]
            surrogate_signal = max((x[0] for x in ranked), default=0.0)

            candidates, downhill = [], []
            for pred, op_name, op_func in ranked:
                cand_code, _ = op_func(current_code, self.seed + gen)
                if cand_code == current_code:
                    no_site += 1
                    self._learn(features, op_name, 0.0, True, True)
                    continue
                total_attempted += 1

                rec = sandbox.validate(cand_code, external_test_runner, self.sandbox_config)
                p_v, c_v, r_v = rec["parse_valid"], rec["compile_valid"], rec["runtime_valid"]
                if p_v and c_v and r_v:
                    total_valid += 1
                    cand_score = self.calculator.compute_phi(cand_code)
                    delta = round(cand_score - current_score, 6)
                else:
                    cand_score, delta = 0.1000, -0.5000
                    validity_failures.append({"generation": gen, "operator": op_name, "reason": rec["reason"]})

                if self.meta_evolution and op_name in self.discovery_engine.sandbox_pool:
                    cand = self.discovery_engine.sandbox_pool[op_name]
                    cand.record_trial(delta, p_v, r_v)
                    if cand.check_promotion_eligibility():
                        self.discovery_engine.promoted_vocabulary[op_name] = cand.op_func
                        self.cross_file_repo.register_promoted_primitive(op_name, cand.op_func, target_name,
                                                                         cand.cumulative_delta_phi)
                        promoted_summary.append({"primitive_name": op_name, "promotion_gen": gen,
                                                 "recipe": cand.recipe,
                                                 "cumulative_delta_phi": round(cand.cumulative_delta_phi, 6)})

                self._learn(features, op_name, delta, p_v, r_v)

                if cand_score > current_score and p_v and c_v and r_v:
                    cand_intel = self._intelligence(cand_code)
                    if self.euclid_gate and cand_intel < current_intel:
                        euclid_rejections += 1
                        continue
                    candidates.append({"candidate_code": cand_code, "candidate_score": cand_score,
                                       "candidate_intel": cand_intel, "delta_phi": delta,
                                       "op_name": op_name, "op_func": op_func, "predicted_gain": pred})
                elif p_v and c_v and r_v and cand_score < current_score:
                    cand_intel = self._intelligence(cand_code)
                    downhill.append({"candidate_code": cand_code, "candidate_score": cand_score,
                                     "candidate_intel": cand_intel, "delta_phi": delta,
                                     "op_name": op_name, "op_func": op_func, "predicted_gain": pred})

            if candidates:
                candidates.sort(key=lambda x: x["candidate_score"], reverse=True)
                win = candidates[0]
                prev_code = current_code
                current_code, current_score, current_intel = win["candidate_code"], win["candidate_score"], win["candidate_intel"]

                is_escape = stall_counter >= 2 and win["op_name"].startswith("NON_LOCAL:")
                if is_escape:
                    escapes.append({"generation": gen, "escape_operator": win["op_name"], "delta_phi": win["delta_phi"],
                                    "phi_after_escape": current_score, "stall_duration": stall_counter})
                stall_counter = 0

                is_reuse = win["op_name"] in self.cross_file_repo.repository
                if is_reuse:
                    self.cross_file_repo.record_cross_file_use(win["op_name"], target_name, win["delta_phi"])
                    cross_file_reuses.append({"generation": gen, "primitive_name": win["op_name"],
                                              "target_reused_on": target_name, "delta_phi": win["delta_phi"]})

                new_n = self.euclid.calculate_lucas_index(current_code)[0]
                if new_n != current_n:
                    phase_transitions.append({"generation": gen, "lucas_index_from": current_n, "lucas_index_to": new_n})
                    current_n = new_n

                ratio = phase_transition_ratio(win["delta_phi"], prior_deltas)
                recipe = list(getattr(win["op_func"], "recipe", []) or [])
                barrier = None
                if len(recipe) >= 2:
                    barrier = not self._would_accept(prev_code, recipe[0], win["candidate_score"] - win["delta_phi"],
                                                     self._intelligence(prev_code), external_test_runner)
                accepted_steps.append({"generation": gen, "winning_operator": win["op_name"],
                                       "is_manifold_escape": is_escape, "is_transferred_reuse": is_reuse,
                                       "delta_phi": win["delta_phi"], "new_phi": current_score,
                                       "delta_ratio_to_prior_median": round(ratio, 3) if ratio else None,
                                       "is_phase_transition": bool(ratio and ratio >= PHASE_TRANSITION_RATIO),
                                       "operator_newly_available": win["op_name"] not in initial_ops,
                                       "is_barrier_crossing": barrier})
                prior_deltas.append(win["delta_phi"])
                accepted_generations += 1
                if current_score > best_score:
                    best_code, best_score, best_intel = current_code, current_score, current_intel

                if self.meta_evolution:
                    disc = self.discovery_engine.discover_from_transformation(prev_code, current_code, win["op_name"],
                                                                             gen, target_name, win["op_func"])
                    if disc:
                        discovery_events.append({"generation": gen, "discovered_primitive": disc.name,
                                                 "recipe": disc.recipe})
            elif (self.annealing.enabled and stall_counter >= self.annealing.activate_after_stalls
                  and downhill):
                downhill.sort(key=lambda x: x["candidate_score"], reverse=True)
                proposal = downhill[0]
                temperature = max(
                    self.annealing.minimum_temperature,
                    self.annealing.initial_temperature * (self.annealing.cooling_rate ** (gen - 1)),
                )
                probability = math.exp(proposal["delta_phi"] / max(temperature, 1e-12))
                if rng.random() < probability:
                    current_code = proposal["candidate_code"]
                    current_score = proposal["candidate_score"]
                    current_intel = proposal["candidate_intel"]
                    annealing_escapes.append({
                        "generation": gen,
                        "operator": proposal["op_name"],
                        "delta_phi": proposal["delta_phi"],
                        "temperature": round(temperature, 6),
                        "accept_probability": round(probability, 6),
                    })
                    stall_counter = 0
                else:
                    stall_counter += 1
            else:
                stall_counter += 1

            if self.meta_evolution:
                measured_velocity = current_score - gen_start_score
                if self.geometry_signal == "surrogate_velocity":
                    signal = measured_velocity if previous_surrogate_signal is None \
                        else surrogate_signal - previous_surrogate_signal
                    previous_surrogate_signal = surrogate_signal
                else:
                    signal = measured_velocity
                changed, msg = geometry.adapt(signal)
                if changed:
                    geometry_steps.append({"generation": gen, "change": msg,
                                           "signal": self.geometry_signal,
                                           "velocity": round(signal, 6)})
            vocab_after = len(self.discovery_engine.promoted_vocabulary) + len(self.discovery_engine.sandbox_pool)
            if (geometry_steps and geometry_steps[-1]["generation"] == gen) or vocab_after != vocab_before:
                meta_steps += 1

        self.collective_geometry.observe(target_name, geometry, best_score - initial_score)
        self.last_geometry_state = geometry.to_dict()
        return {
            "engine": "V6.5_NON_LOCAL_MANIFOLD_ESCAPE",
            "meta_evolution": self.meta_evolution,
            "generations": max_generations,
            "accept_rate": round(accepted_generations / max(max_generations, 1), 4),
            "geometry_evolution_steps": geometry_steps,
            "meta_steps": meta_steps,
            "phase_transitions": [s for s in accepted_steps if s["is_phase_transition"]],
            "target": target_name,
            "seed": self.seed,
            "initial_phi": initial_score,
            "final_phi": best_score,
            "total_delta_phi": round(best_score - initial_score, 6),
            "wall_time_ms": round((time.time() - start_time) * 1000.0, 2),
            "runtime_validation": "host_test_runner" if external_test_runner is not None else "isolated_module_execution",
            "behaviour_changing_operators_enabled": behaviour_changing,
            "total_evals_attempted": total_attempted,
            "total_evals_valid": total_valid,
            "operators_without_site": no_site,
            "euclid_gate_rejections": euclid_rejections,
            "validity_failures": validity_failures,
            "accepted_steps_count": len(accepted_steps),
            "accepted_steps": accepted_steps,
            "lucas_phase_transitions": phase_transitions,
            "manifold_escapes_count": len(escapes),
            "manifold_escapes": escapes,
            "annealing_enabled": self.annealing.enabled,
            "annealing_escapes": annealing_escapes,
            "discovery_events_count": len(discovery_events),
            "discovery_events": discovery_events,
            "promoted_primitives": promoted_summary,
            "cross_file_reuses_count": len(cross_file_reuses),
            "surrogate_rmse": self.surrogate.compute_rmse(),
            "initial_geometry_state": initial_geometry,
            "final_geometry_state": geometry.to_dict(),
            "collective_geometry_state": self.collective_geometry.to_dict(),
            "geometry_signal": self.geometry_signal,
            "final_code": best_code,
        }
