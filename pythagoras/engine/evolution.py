"""Production PYTHAGORAS evolutionary search.

The engine performs greedy measured-phi ascent over real AST/source transforms with:
- AL HARAS isolated candidate validation;
- an EUCLID co-gate at fixed topological time;
- PYTHIA surrogate ranking;
- bounded adaptive search geometry;
- evidence-based primitive discovery and cross-file reuse;
- deterministic, opt-in simulated annealing for stalled search;
- phase-transition and barrier-crossing provenance.

Historical staged V6 engines are intentionally not part of the production surface.
"""

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
from pythagoras.engine.geometry import CollectiveGeometryCoordinator
from pythagoras.engine.primitive_discovery import PrimitiveDiscoveryEngine
from pythagoras.engine.primitive_repository import CrossFilePrimitiveRepository
from pythagoras.engine.surrogate import NeuralSurrogateEvaluator


class NonLocalASTMutators:
    """Version-neutral accessors for the production non-local operator set."""

    function_split_refactor = staticmethod(
        OPERATOR_REGISTRY["NON_LOCAL:function_split_refactor"]
    )
    conditional_flattening = staticmethod(
        OPERATOR_REGISTRY["NON_LOCAL:conditional_flattening"]
    )
    class_decomposition = staticmethod(
        OPERATOR_REGISTRY["NON_LOCAL:class_decomposition"]
    )

    @classmethod
    def get_non_local_operators(
        cls,
    ) -> List[Tuple[str, Callable[[str, int], Tuple[str, str]]]]:
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


def phase_transition_ratio(
    delta: float,
    prior_deltas: List[float],
) -> Optional[float]:
    """Return delta relative to the median of earlier accepted positive steps."""
    if len(prior_deltas) < 2:
        return None
    median = statistics.median(prior_deltas)
    return delta / median if median > 0 else None


class PythagorasEvolutionEngine:
    """Canonical production PYTHAGORAS source-evolution engine."""

    def __init__(
        self,
        repository: Optional[CrossFilePrimitiveRepository] = None,
        target_phi: float = 0.618033988749895,
        seed: int = 42,
        sandbox_config: Optional[sandbox.SandboxConfig] = None,
        euclid_gate: bool = True,
        meta_evolution: bool = True,
        allow_behaviour_changing: Optional[bool] = None,
        annealing: Optional[AnnealingConfig] = None,
        geometry_signal: str = "measured_phi",
        collective_geometry: Optional[CollectiveGeometryCoordinator] = None,
    ):
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
        self.allow_behaviour_changing = allow_behaviour_changing
        self.annealing = annealing or AnnealingConfig()
        if geometry_signal not in ("measured_phi", "surrogate_velocity"):
            raise ValueError(
                "geometry_signal must be 'measured_phi' or 'surrogate_velocity'"
            )
        self.geometry_signal = geometry_signal
        self.collective_geometry = (
            collective_geometry or CollectiveGeometryCoordinator()
        )
        self.last_geometry_state: Dict[str, Any] = {}

    @property
    def base_operators(self):
        return ASTPrimitives.get_all_operators()

    def verify_validity(
        self,
        code_str: str,
        external_test_runner: Optional[Callable[[str], bool]] = None,
    ) -> Tuple[bool, bool, bool]:
        """Return parse/compile/runtime validity through the AL HARAS isolated gate."""
        return sandbox.verify_validity(
            code_str,
            external_test_runner,
            self.sandbox_config,
        )

    def _learn(
        self,
        features: Dict[str, Any],
        op_name: str,
        delta: float,
        parse_valid: bool,
        runtime_valid: bool,
    ) -> None:
        if self.meta_evolution:
            self.surrogate.update(
                features,
                op_name,
                delta,
                parse_valid,
                runtime_valid,
            )
        else:
            self.surrogate.prediction_history.append(
                (self.surrogate.predict_gain(features, op_name), delta)
            )

    def _intelligence(self, code: str) -> float:
        return self.euclid.compute_intelligence_scale(code, 0.0)[
            "intelligence_score"
        ]

    def _active_operators(
        self,
        behaviour_changing: bool,
    ) -> List[Tuple[str, Callable[[str, int], Tuple[str, str]]]]:
        operators: Dict[str, Callable[[str, int], Tuple[str, str]]] = {}
        for name, function in ASTPrimitives.get_all_operators(
            include_behaviour_changing=behaviour_changing
        ):
            operators[name] = function
        for name, function in self.non_local_operators:
            operators.setdefault(name, function)
        if not self.meta_evolution:
            return list(operators.items())
        for name, function in self.discovery_engine.promoted_vocabulary.items():
            operators.setdefault(name, function)
        for name, candidate in self.discovery_engine.sandbox_pool.items():
            if not candidate.is_promoted:
                operators.setdefault(name, candidate.op_func)
        return list(operators.items())

    def _would_accept(
        self,
        code: str,
        op_name: str,
        current_score: float,
        current_intel: float,
        external_test_runner: Optional[Callable[[str], bool]],
    ) -> bool:
        candidate, _ = OPERATOR_REGISTRY[op_name](code, self.seed)
        if candidate == code:
            return False
        record = sandbox.validate(
            candidate,
            external_test_runner,
            self.sandbox_config,
        )
        if not (
            record["parse_valid"]
            and record["compile_valid"]
            and record["runtime_valid"]
        ):
            return False
        if self.calculator.compute_phi(candidate) <= current_score:
            return False
        return not (
            self.euclid_gate and self._intelligence(candidate) < current_intel
        )

    def run_optimization(
        self,
        target_name: str,
        initial_code: str,
        max_generations: int = 20,
        external_test_runner: Optional[Callable[[str], bool]] = None,
    ) -> Dict[str, Any]:
        start_time = time.time()
        current_code = initial_code
        current_score = self.calculator.compute_phi(current_code)
        current_intel = self._intelligence(current_code)
        current_n = self.euclid.calculate_lucas_index(current_code)[0]
        initial_score = current_score
        initial_intel = current_intel
        best_code = current_code
        best_score = current_score
        best_intel = current_intel

        if self.allow_behaviour_changing is None:
            behaviour_changing = external_test_runner is not None
        else:
            behaviour_changing = (
                self.allow_behaviour_changing
                and external_test_runner is not None
            )

        geometry = self.collective_geometry.initial_state()
        initial_geometry = geometry.to_dict()
        initial_ops = {
            name for name, _ in self._active_operators(behaviour_changing)
        }
        geometry_steps: List[Dict[str, Any]] = []
        meta_steps = 0
        accepted_generations = 0
        prior_deltas: List[float] = []
        accepted_steps: List[Dict[str, Any]] = []
        discovery_events: List[Dict[str, Any]] = []
        promoted_summary: List[Dict[str, Any]] = []
        cross_file_reuses: List[Dict[str, Any]] = []
        escapes: List[Dict[str, Any]] = []
        lucas_phase_transitions: List[Dict[str, Any]] = []
        validity_failures: List[Dict[str, Any]] = []
        annealing_escapes: List[Dict[str, Any]] = []
        total_attempted = 0
        total_valid = 0
        no_site = 0
        euclid_rejections = 0
        stall_counter = 0
        previous_surrogate_signal: Optional[float] = None
        rng = random.Random(self.seed)

        if self.meta_evolution:
            for primitive_name, primitive_function in (
                self.cross_file_repo.get_all_transfer_primitives()
            ):
                self.discovery_engine.promoted_vocabulary[
                    primitive_name
                ] = primitive_function
            initial_ops = {
                name for name, _ in self._active_operators(behaviour_changing)
            }

        for generation in range(1, max_generations + 1):
            self.discovery_engine.max_recipe_len = geometry.levels_back
            vocab_before = (
                len(self.discovery_engine.promoted_vocabulary)
                + len(self.discovery_engine.sandbox_pool)
            )
            features = self.calculator.extract_features(current_code)
            gen_start_score = current_score

            ranked = []
            for op_name, op_func in self._active_operators(
                behaviour_changing
            ):
                if self.surrogate.is_anti_primitive(op_name):
                    continue
                prediction = self.surrogate.predict_gain(features, op_name)
                if stall_counter >= 2 and op_name.startswith("NON_LOCAL:"):
                    prediction += 0.05
                ranked.append((prediction, op_name, op_func))
            ranked.sort(key=lambda item: item[0], reverse=True)
            ranked = ranked[: max(1, geometry.n_cols)]
            surrogate_signal = max(
                (item[0] for item in ranked),
                default=0.0,
            )

            candidates: List[Dict[str, Any]] = []
            downhill: List[Dict[str, Any]] = []
            for prediction, op_name, op_func in ranked:
                candidate_code, _ = op_func(
                    current_code,
                    self.seed + generation,
                )
                if candidate_code == current_code:
                    no_site += 1
                    self._learn(
                        features,
                        op_name,
                        0.0,
                        True,
                        True,
                    )
                    continue

                total_attempted += 1
                record = sandbox.validate(
                    candidate_code,
                    external_test_runner,
                    self.sandbox_config,
                )
                parse_valid = record["parse_valid"]
                compile_valid = record["compile_valid"]
                runtime_valid = record["runtime_valid"]
                if parse_valid and compile_valid and runtime_valid:
                    total_valid += 1
                    candidate_score = self.calculator.compute_phi(
                        candidate_code
                    )
                    delta = round(candidate_score - current_score, 6)
                else:
                    candidate_score = 0.1000
                    delta = -0.5000
                    validity_failures.append(
                        {
                            "generation": generation,
                            "operator": op_name,
                            "reason": record["reason"],
                        }
                    )

                if (
                    self.meta_evolution
                    and op_name in self.discovery_engine.sandbox_pool
                ):
                    discovered = self.discovery_engine.sandbox_pool[op_name]
                    discovered.record_trial(
                        delta,
                        parse_valid,
                        runtime_valid,
                    )
                    if discovered.check_promotion_eligibility():
                        self.discovery_engine.promoted_vocabulary[
                            op_name
                        ] = discovered.op_func
                        self.cross_file_repo.register_promoted_primitive(
                            op_name,
                            discovered.op_func,
                            target_name,
                            discovered.cumulative_delta_phi,
                        )
                        promoted_summary.append(
                            {
                                "primitive_name": op_name,
                                "promotion_gen": generation,
                                "recipe": discovered.recipe,
                                "cumulative_delta_phi": round(
                                    discovered.cumulative_delta_phi,
                                    6,
                                ),
                            }
                        )

                self._learn(
                    features,
                    op_name,
                    delta,
                    parse_valid,
                    runtime_valid,
                )

                if (
                    candidate_score > current_score
                    and parse_valid
                    and compile_valid
                    and runtime_valid
                ):
                    candidate_intel = self._intelligence(candidate_code)
                    if (
                        self.euclid_gate
                        and candidate_intel < current_intel
                    ):
                        euclid_rejections += 1
                        continue
                    candidates.append(
                        {
                            "candidate_code": candidate_code,
                            "candidate_score": candidate_score,
                            "candidate_intel": candidate_intel,
                            "delta_phi": delta,
                            "op_name": op_name,
                            "op_func": op_func,
                            "predicted_gain": prediction,
                        }
                    )
                elif (
                    parse_valid
                    and compile_valid
                    and runtime_valid
                    and candidate_score < current_score
                ):
                    candidate_intel = self._intelligence(candidate_code)
                    if (
                        self.euclid_gate
                        and candidate_intel < current_intel
                    ):
                        euclid_rejections += 1
                        continue
                    downhill.append(
                        {
                            "candidate_code": candidate_code,
                            "candidate_score": candidate_score,
                            "candidate_intel": candidate_intel,
                            "delta_phi": delta,
                            "op_name": op_name,
                            "op_func": op_func,
                            "predicted_gain": prediction,
                        }
                    )

            if candidates:
                candidates.sort(
                    key=lambda item: item["candidate_score"],
                    reverse=True,
                )
                winner = candidates[0]
                previous_code = current_code
                current_code = winner["candidate_code"]
                current_score = winner["candidate_score"]
                current_intel = winner["candidate_intel"]

                is_escape = (
                    stall_counter >= 2
                    and winner["op_name"].startswith("NON_LOCAL:")
                )
                if is_escape:
                    escapes.append(
                        {
                            "generation": generation,
                            "escape_operator": winner["op_name"],
                            "delta_phi": winner["delta_phi"],
                            "phi_after_escape": current_score,
                            "stall_duration": stall_counter,
                        }
                    )
                stall_counter = 0

                is_reuse = (
                    winner["op_name"] in self.cross_file_repo.repository
                )
                if is_reuse:
                    self.cross_file_repo.record_cross_file_use(
                        winner["op_name"],
                        target_name,
                        winner["delta_phi"],
                    )
                    cross_file_reuses.append(
                        {
                            "generation": generation,
                            "primitive_name": winner["op_name"],
                            "target_reused_on": target_name,
                            "delta_phi": winner["delta_phi"],
                        }
                    )

                new_n = self.euclid.calculate_lucas_index(current_code)[0]
                if new_n != current_n:
                    lucas_phase_transitions.append(
                        {
                            "generation": generation,
                            "lucas_index_from": current_n,
                            "lucas_index_to": new_n,
                        }
                    )
                    current_n = new_n

                ratio = phase_transition_ratio(
                    winner["delta_phi"],
                    prior_deltas,
                )
                recipe = list(
                    getattr(winner["op_func"], "recipe", []) or []
                )
                barrier = None
                if len(recipe) >= 2:
                    barrier = not self._would_accept(
                        previous_code,
                        recipe[0],
                        winner["candidate_score"]
                        - winner["delta_phi"],
                        self._intelligence(previous_code),
                        external_test_runner,
                    )
                accepted_steps.append(
                    {
                        "generation": generation,
                        "winning_operator": winner["op_name"],
                        "is_manifold_escape": is_escape,
                        "is_transferred_reuse": is_reuse,
                        "delta_phi": winner["delta_phi"],
                        "new_phi": current_score,
                        "delta_ratio_to_prior_median": (
                            round(ratio, 3) if ratio else None
                        ),
                        "is_phase_transition": bool(
                            ratio
                            and ratio >= PHASE_TRANSITION_RATIO
                        ),
                        "operator_newly_available": (
                            winner["op_name"] not in initial_ops
                        ),
                        "is_barrier_crossing": barrier,
                    }
                )
                prior_deltas.append(winner["delta_phi"])
                accepted_generations += 1
                if current_score > best_score:
                    best_code = current_code
                    best_score = current_score
                    best_intel = current_intel

                if self.meta_evolution:
                    discovered = (
                        self.discovery_engine.discover_from_transformation(
                            previous_code,
                            current_code,
                            winner["op_name"],
                            generation,
                            target_name,
                            winner["op_func"],
                        )
                    )
                    if discovered:
                        discovery_events.append(
                            {
                                "generation": generation,
                                "discovered_primitive": discovered.name,
                                "recipe": discovered.recipe,
                            }
                        )
            elif (
                self.annealing.enabled
                and stall_counter
                >= self.annealing.activate_after_stalls
                and downhill
            ):
                downhill.sort(
                    key=lambda item: item["candidate_score"],
                    reverse=True,
                )
                proposal = downhill[0]
                temperature = max(
                    self.annealing.minimum_temperature,
                    self.annealing.initial_temperature
                    * (self.annealing.cooling_rate ** (generation - 1)),
                )
                probability = math.exp(
                    proposal["delta_phi"] / max(temperature, 1e-12)
                )
                if rng.random() < probability:
                    current_code = proposal["candidate_code"]
                    current_score = proposal["candidate_score"]
                    current_intel = proposal["candidate_intel"]
                    annealing_escapes.append(
                        {
                            "generation": generation,
                            "operator": proposal["op_name"],
                            "delta_phi": proposal["delta_phi"],
                            "temperature": round(temperature, 6),
                            "accept_probability": round(
                                probability,
                                6,
                            ),
                        }
                    )
                    stall_counter = 0
                else:
                    stall_counter += 1
            else:
                stall_counter += 1

            if self.meta_evolution:
                measured_velocity = current_score - gen_start_score
                if self.geometry_signal == "surrogate_velocity":
                    if previous_surrogate_signal is None:
                        signal = measured_velocity
                    else:
                        signal = (
                            surrogate_signal
                            - previous_surrogate_signal
                        )
                    previous_surrogate_signal = surrogate_signal
                else:
                    signal = measured_velocity

                changed, message = geometry.adapt(signal)
                if changed:
                    geometry_steps.append(
                        {
                            "generation": generation,
                            "change": message,
                            "signal": self.geometry_signal,
                            "velocity": round(signal, 6),
                        }
                    )

            vocab_after = (
                len(self.discovery_engine.promoted_vocabulary)
                + len(self.discovery_engine.sandbox_pool)
            )
            if (
                geometry_steps
                and geometry_steps[-1]["generation"] == generation
            ) or vocab_after != vocab_before:
                meta_steps += 1

        self.collective_geometry.observe(
            target_name,
            geometry,
            best_score - initial_score,
        )
        self.last_geometry_state = geometry.to_dict()
        return {
            "engine": "PYTHAGORAS_EVOLUTION",
            "meta_evolution": self.meta_evolution,
            "generations": max_generations,
            "accept_rate": round(
                accepted_generations / max(max_generations, 1),
                4,
            ),
            "geometry_evolution_steps": geometry_steps,
            "meta_steps": meta_steps,
            "phase_transitions": [
                step
                for step in accepted_steps
                if step["is_phase_transition"]
            ],
            "target": target_name,
            "seed": self.seed,
            "initial_phi": initial_score,
            "final_phi": best_score,
            "initial_euclid_intelligence": initial_intel,
            "best_euclid_intelligence": best_intel,
            "total_delta_phi": round(best_score - initial_score, 6),
            "wall_time_ms": round(
                (time.time() - start_time) * 1000.0,
                2,
            ),
            "runtime_validation": (
                "host_test_runner"
                if external_test_runner is not None
                else "isolated_module_execution"
            ),
            "behaviour_changing_operators_enabled": behaviour_changing,
            "total_evals_attempted": total_attempted,
            "total_evals_valid": total_valid,
            "operators_without_site": no_site,
            "euclid_gate_rejections": euclid_rejections,
            "validity_failures": validity_failures,
            "accepted_steps_count": len(accepted_steps),
            "accepted_steps": accepted_steps,
            "lucas_phase_transitions": lucas_phase_transitions,
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
            "collective_geometry_state": (
                self.collective_geometry.to_dict()
            ),
            "geometry_signal": self.geometry_signal,
            "final_code": best_code,
        }
