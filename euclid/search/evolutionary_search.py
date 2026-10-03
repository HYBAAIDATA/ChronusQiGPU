"""
EUCLID Multi-Objective Meta-Evolutionary Search Engine v16.0
===============================================================
Executes unconstrained evolutionary optimization over AST program graphs.
Combines adaptive surrogate guidance, dynamic CGP topology control, AST-delta primitive discovery,
process isolation validation, and multi-objective fitness evaluation.
"""

import time
import random
import logging
from typing import Dict, List, Tuple, Any, Optional, Callable

from euclid.core.phi_metric import PhiResonanceCalculator
from euclid.core.primitives import ASTPrimitives
from euclid.validation.process_sandbox import IsolatedProcessEvaluator
from euclid.surrogate.adaptive_surrogate import AdaptiveOperatorSurrogate
from euclid.geometry.search_topology import CGPSearchTopologyController
from euclid.discovery.ast_delta_discovery import ASTDeltaDiscoveryEngine
from euclid.transfer.persistent_repository import PersistentPrimitiveRepository

logger = logging.getLogger(__name__)

class EvolutionarySearchEngine:
    """
    Production Evolutionary Search Engine.
    Combines multi-objective fitness, adaptive operator selection, isolated process execution,
    dynamic topology scaling, and AST-delta primitive discovery.
    """
    def __init__(
        self, 
        repository: Optional[PersistentPrimitiveRepository] = None,
        target_phi: float = 0.618033988749895, 
        seed: int = 42
    ):
        self.seed = seed
        random.seed(seed)
        self.calculator = PhiResonanceCalculator(target_phi)
        self.base_operators = ASTPrimitives.get_all_operators()
        self.evaluator = IsolatedProcessEvaluator(timeout_sec=2.0)
        self.surrogate = AdaptiveOperatorSurrogate(learning_rate=0.05)
        self.discovery_engine = ASTDeltaDiscoveryEngine()
        self.repository = repository or PersistentPrimitiveRepository()

    def run_optimization(
        self, 
        target_name: str, 
        initial_code: str, 
        max_generations: int = 20,
        external_test_runner: Optional[Callable[[str], bool]] = None,
        external_test_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Runs unconstrained evolutionary search over target code.
        Returns 100% measured execution telemetry.
        """
        start_time = time.time()
        current_code = initial_code
        
        # Verify initial code validity
        p_v, c_v, r_v, diag = self.evaluator.evaluate_validity(
            current_code, external_test_runner, external_test_code
        )
        
        current_score = self.calculator.compute_phi(current_code) if (p_v and r_v) else 0.1000
        initial_score = current_score
        initial_node_count = self.calculator.extract_features(current_code).get("node_count", 50)

        topology = CGPSearchTopologyController(initial_n_cols=12, initial_levels_back=3, pop_size=10)
        accepted_steps = []
        discovery_events = []
        promoted_primitives_summary = []
        cross_file_reuses_triggered = []

        total_evals_attempted = 0
        total_evals_valid = 0
        evals_skipped_by_surrogate = 0

        # Load transferred primitives into active discovery engine
        transferred = self.repository.get_all_primitives()
        for pname, pfunc in transferred:
            self.discovery_engine.promoted_vocabulary[pname] = pfunc

        for gen in range(1, max_generations + 1):
            features = self.calculator.extract_features(current_code)
            gen_start_score = current_score

            # Active Operators = Base + Promoted + Sandbox
            active_ops = list(self.base_operators)
            for pname, pfunc in self.discovery_engine.promoted_vocabulary.items():
                if (pname, pfunc) not in active_ops:
                    active_ops.append((pname, pfunc))

            for sname, scand in self.discovery_engine.sandbox_pool.items():
                if not scand.is_promoted and (sname, scand.op_func) not in active_ops:
                    active_ops.append((sname, scand.op_func))

            # Prioritize operators using Surrogate Model
            ranked_ops = []
            for op_name, op_func in active_ops:
                if self.surrogate.is_anti_primitive(op_name):
                    evals_skipped_by_surrogate += 1
                    continue
                pred_gain = self.surrogate.predict_gain(features, op_name)
                ranked_ops.append((pred_gain, op_name, op_func))

            # Stochastic sampling weighted by predicted gain
            ranked_ops.sort(key=lambda x: x[0] + random.uniform(-0.01, 0.01), reverse=True)
            
            # Substrate topology dictates population candidate limit
            cand_limit = topology.get_candidate_population_size()
            selected_ops = ranked_ops[:cand_limit]

            valid_candidates = []

            for pred_gain, op_name, op_func in selected_ops:
                total_evals_attempted += 1
                cand_code, returned_name = op_func(current_code, self.seed + gen + total_evals_attempted)

                # Isolated process evaluation
                parse_v, compile_v, test_v, msg = self.evaluator.evaluate_validity(
                    cand_code, external_test_runner, external_test_code
                )

                if parse_v and compile_v and test_v:
                    total_evals_valid += 1
                    cand_fitness = self.calculator.compute_multi_objective_fitness(
                        cand_code, initial_node_count=initial_node_count, tests_passed=True
                    )
                    actual_delta = round(cand_fitness - current_score, 6)
                else:
                    cand_fitness = 0.1000
                    actual_delta = -0.5000

                # Sandbox candidate generalization trial
                if op_name in self.discovery_engine.sandbox_pool:
                    cand = self.discovery_engine.sandbox_pool[op_name]
                    cand.record_trial(actual_delta, parse_v, test_v)
                    if cand.check_promotion_eligibility():
                        self.discovery_engine.promoted_vocabulary[op_name] = cand.op_func
                        # Register primitive in persistent repository
                        self.repository.register_primitive(
                            name=op_name, 
                            op_func=cand.op_func, 
                            rule_type=op_name, 
                            origin_target=target_name, 
                            cum_gain=cand.cumulative_delta_phi, 
                            pattern_hash=cand.pattern_hash
                        )
                        promoted_primitives_summary.append({
                            "primitive_name": op_name,
                            "promotion_gen": gen,
                            "cumulative_delta_phi": round(cand.cumulative_delta_phi, 6)
                        })

                # Online surrogate update
                self.surrogate.update(features, op_name, actual_delta, parse_v, test_v)

                # Acceptance boundary: fitness must strictly increase
                if (cand_fitness > current_score) and parse_v and compile_v and test_v:
                    valid_candidates.append({
                        "candidate_code": cand_code,
                        "candidate_fitness": cand_fitness,
                        "delta_phi": actual_delta,
                        "op_name": op_name
                    })

            # Selection
            if valid_candidates:
                valid_candidates.sort(key=lambda x: x["candidate_fitness"], reverse=True)
                winner = valid_candidates[0]

                prev_code = current_code
                current_code = winner["candidate_code"]
                current_score = winner["candidate_fitness"]

                is_transferred_reuse = winner["op_name"] in self.repository.repository
                if is_transferred_reuse:
                    self.repository.record_cross_file_reuse(winner["op_name"], target_name, winner["delta_phi"])
                    cross_file_reuses_triggered.append({
                        "generation": gen,
                        "primitive_name": winner["op_name"],
                        "target_reused_on": target_name,
                        "delta_phi": winner["delta_phi"]
                    })

                accepted_steps.append({
                    "generation": gen,
                    "status": "MUTATION_ACCEPTED",
                    "winning_operator": winner["op_name"],
                    "is_transferred_reuse": is_transferred_reuse,
                    "delta_phi": winner["delta_phi"],
                    "new_phi": current_score,
                    "topology": topology.to_dict()
                })

                # AST-delta primitive discovery scan
                disc = self.discovery_engine.discover_from_transformation(
                    prev_code, current_code, winner["op_name"], gen, target_name
                )
                if disc:
                    discovery_events.append({
                        "generation": gen,
                        "discovered_primitive": disc.name,
                        "pattern_hash": disc.pattern_hash
                    })

            # Generation velocity & topology adaptation
            gen_velocity = current_score - gen_start_score
            topology.adapt_topology(gen_velocity)

        wall_time_ms = round((time.time() - start_time) * 1000.0, 2)

        return {
            "target": target_name,
            "seed": self.seed,
            "initial_phi": initial_score,
            "final_phi": current_score,
            "total_delta_phi": round(current_score - initial_score, 6),
            "wall_time_ms": wall_time_ms,
            "total_evals_attempted": total_evals_attempted,
            "total_evals_valid": total_evals_valid,
            "evals_skipped_by_surrogate": evals_skipped_by_surrogate,
            "accepted_steps_count": len(accepted_steps),
            "accepted_steps": accepted_steps,
            "discovery_events_count": len(discovery_events),
            "promoted_primitives_count": len(promoted_primitives_summary),
            "cross_file_reuses_count": len(cross_file_reuses_triggered),
            "final_topology": topology.to_dict(),
            "surrogate_rmse": self.surrogate.compute_rmse(),
            "final_code": current_code
        }
