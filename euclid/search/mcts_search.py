"""
EUCLID MCTS Search Engine with Policy Priors v16.0
=====================================================
Implements Monte Carlo Tree Search (MCTS) over program graph AST space following
the AlphaZero / Silver paradigm with PUCT selection, policy priors pi(a|s), value estimates V(s),
process isolation validation, and dynamic macro-primitive discovery.
"""

import time
import math
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

class MCTSNode:
    """
    Monte Carlo Tree Search Node representing a state in program AST space.
    """
    def __init__(self, state_code: str, parent: Optional['MCTSNode'] = None, action_taken: Optional[str] = None, prior_prob: float = 1.0):
        self.state_code: str = state_code
        self.parent: Optional['MCTSNode'] = parent
        self.action_taken: Optional[str] = action_taken
        self.prior_prob: float = prior_prob
        
        self.children: Dict[str, 'MCTSNode'] = {}
        self.visit_count: int = 0
        self.total_value: float = 0.0
        self.mean_value: float = 0.0
        self.is_expanded: bool = False

    def puct_score(self, c_puct: float = 1.5) -> float:
        """
        Calculates Predictor Upper Confidence Bound for Trees (PUCT) score:
        U(s, a) = Q(s, a) + c_puct * P(s, a) * sqrt(N_parent) / (1 + N_child)
        """
        parent_visits = self.parent.visit_count if self.parent else 1
        q_value = self.mean_value
        u_value = c_puct * self.prior_prob * (math.sqrt(parent_visits) / (1.0 + self.visit_count))
        return q_value + u_value

    def update(self, value: float):
        """Backpropagates value through node."""
        self.visit_count += 1
        self.total_value += value
        self.mean_value = self.total_value / self.visit_count


class MCTSSearchEngine:
    """
    Silver-Paradigm Monte Carlo Tree Search Engine over AST program space.
    Integrates policy priors pi(a|s), value predictions V(s), isolated sandbox verification,
    and adaptive AST topology scaling.
    """
    def __init__(
        self, 
        repository: Optional[PersistentPrimitiveRepository] = None,
        target_phi: float = 0.618033988749895, 
        seed: int = 42,
        c_puct: float = 1.5
    ):
        self.seed = seed
        self.c_puct = c_puct
        self.calculator = PhiResonanceCalculator(target_phi)
        self.base_operators = ASTPrimitives.get_all_operators()
        self.evaluator = IsolatedProcessEvaluator(timeout_sec=2.0)
        self.surrogate = AdaptiveOperatorSurrogate()
        self.discovery_engine = ASTDeltaDiscoveryEngine()
        self.repository = repository or PersistentPrimitiveRepository()

    def _compute_policy_priors(self, code_str: str, active_ops: List[Tuple[str, Callable]]) -> Dict[str, float]:
        """Calculates policy prior distribution pi(a|s) using AdaptiveOperatorSurrogate."""
        features = self.calculator.extract_features(code_str)
        # Anti-primitive suppression is measured (recorded failure counts), so
        # suppressed operators receive zero prior mass rather than an invented
        # penalty logit.
        raw_priors = {}
        for op_name, _ in active_ops:
            if not self.surrogate.is_anti_primitive(op_name):
                raw_priors[op_name] = self.surrogate.predict_gain(features, op_name)
        if not raw_priors:
            # Every operator is suppressed by measured evidence; fall back to
            # Born-expectation priors over the full vocabulary rather than an
            # empty distribution.
            for op_name, _ in active_ops:
                raw_priors[op_name] = self.surrogate.predict_gain(features, op_name)

        # Softmax normalization to policy probability distribution
        max_val = max(raw_priors.values()) if raw_priors else 0.0
        exp_vals = {op: math.exp(val - max_val) for op, val in raw_priors.items()}
        sum_exp = sum(exp_vals.values()) if exp_vals else 1.0
        return {op: prob / sum_exp for op, prob in exp_vals.items()}

    def run_mcts_search(
        self, 
        target_name: str, 
        initial_code: str, 
        max_generations: int = 20,
        num_simulations_per_gen: int = 5,
        external_test_runner: Optional[Callable[[str], bool]] = None,
        external_test_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Runs MCTS Trajectory Search with Policy Priors pi(a|s) and Value Function V(s).
        """
        start_time = time.time()
        current_code = initial_code
        
        # Initial Sandbox Verification
        p_v, c_v, r_v, _ = self.evaluator.evaluate_validity(current_code, external_test_runner, external_test_code)
        # phi is a computable structural metric: report it unconditionally rather
        # than substituting a placeholder when sandbox validity fails.
        current_score = self.calculator.compute_phi(current_code)
        initial_score = current_score
        initial_node_count = self.calculator.extract_features(current_code).get("node_count", 50)

        topology = CGPSearchTopologyController(initial_n_cols=12, initial_levels_back=3, pop_size=10)
        root = MCTSNode(state_code=current_code)
        
        accepted_steps = []
        discovery_events = []
        promoted_primitives_summary = []
        cross_file_reuses_triggered = []

        total_evals_attempted = 0
        total_evals_valid = 0
        evals_skipped_by_surrogate = 0

        # Load transferred primitives into active discovery engine
        for pname, pfunc in self.repository.get_all_primitives():
            self.discovery_engine.promoted_vocabulary[pname] = pfunc

        for gen in range(1, max_generations + 1):
            gen_start_score = current_score

            # Active Operators = Base + Promoted + Sandbox
            active_ops = list(self.base_operators)
            for pname, pfunc in self.discovery_engine.promoted_vocabulary.items():
                if (pname, pfunc) not in active_ops:
                    active_ops.append((pname, pfunc))

            for sname, scand in self.discovery_engine.sandbox_pool.items():
                if not scand.is_promoted and (sname, scand.op_func) not in active_ops:
                    active_ops.append((sname, scand.op_func))

            op_dict = {op_name: op_func for op_name, op_func in active_ops}

            # 1. Selection & Expansion (MCTS Rollouts)
            for sim in range(num_simulations_per_gen):
                node = root
                
                # Expand root if not expanded
                if not node.is_expanded:
                    priors = self._compute_policy_priors(node.state_code, active_ops)
                    for op_name, op_func in active_ops:
                        if op_name in priors:
                            node.children[op_name] = MCTSNode(
                                state_code=node.state_code,
                                parent=node,
                                action_taken=op_name,
                                prior_prob=priors[op_name]
                            )
                    node.is_expanded = True

                # Select best child via PUCT
                best_action = max(node.children.keys(), key=lambda a: node.children[a].puct_score(self.c_puct))
                child = node.children[best_action]

                # 2. Evaluation via Process Sandbox & Multi-Objective Fitness
                op_func = op_dict[best_action]
                total_evals_attempted += 1
                cand_code, _ = op_func(child.state_code, self.seed + gen * 100 + total_evals_attempted)

                parse_v, compile_v, test_v, msg = self.evaluator.evaluate_validity(
                    cand_code, external_test_runner, external_test_code
                )

                if parse_v and compile_v and test_v:
                    total_evals_valid += 1
                    child.state_code = cand_code
                    cand_fitness = self.calculator.compute_multi_objective_fitness(
                        cand_code, initial_node_count=initial_node_count, tests_passed=True
                    )
                    actual_delta = round(cand_fitness - current_score, 6)
                    value = actual_delta
                else:
                    # Invalid rollouts carry no measured fitness or delta; the
                    # failure is recorded as evidence and the backpropagated
                    # value is the honest "no measured gain" (0.0).
                    cand_fitness = None
                    actual_delta = None
                    value = 0.0

                # 3. Sandbox Candidate Trial Record
                if best_action in self.discovery_engine.sandbox_pool:
                    cand = self.discovery_engine.sandbox_pool[best_action]
                    cand.record_trial(
                        actual_delta if actual_delta is not None else 0.0,
                        parse_v,
                        test_v,
                    )
                    if cand.check_promotion_eligibility():
                        self.discovery_engine.promoted_vocabulary[best_action] = cand.op_func
                        self.repository.register_primitive(
                            name=best_action,
                            op_func=cand.op_func,
                            rule_type=best_action,
                            origin_target=target_name,
                            cum_gain=cand.cumulative_delta_phi,
                            pattern_hash=cand.pattern_hash
                        )
                        promoted_primitives_summary.append({
                            "primitive_name": best_action,
                            "promotion_gen": gen,
                            "cumulative_delta_phi": round(cand.cumulative_delta_phi, 6)
                        })

                # Online Surrogate Update
                features = self.calculator.extract_features(child.state_code)
                self.surrogate.update(features, best_action, actual_delta, parse_v, test_v)

                # 4. Backpropagation
                curr_node = child
                while curr_node is not None:
                    curr_node.update(value)
                    curr_node = curr_node.parent

            # Select Best Move at Gen Level (Highest visit count or mean value)
            valid_children = [c for c in root.children.values() if c.visit_count > 0]
            if valid_children:
                best_child = max(valid_children, key=lambda c: (c.mean_value, c.visit_count))
                if best_child.mean_value > 0 and best_child.state_code != current_code:
                    prev_code = current_code
                    current_code = best_child.state_code
                    current_score = self.calculator.compute_phi(current_code)

                    is_transferred_reuse = best_child.action_taken in self.repository.repository
                    if is_transferred_reuse:
                        self.repository.record_cross_file_reuse(best_child.action_taken, target_name, best_child.mean_value)
                        cross_file_reuses_triggered.append({
                            "generation": gen,
                            "primitive_name": best_child.action_taken,
                            "target_reused_on": target_name,
                            "delta_phi": best_child.mean_value
                        })

                    accepted_steps.append({
                        "generation": gen,
                        "status": "MUTATION_ACCEPTED",
                        "winning_operator": best_child.action_taken,
                        "is_transferred_reuse": is_transferred_reuse,
                        "delta_phi": best_child.mean_value,
                        "new_phi": current_score,
                        "topology": topology.to_dict()
                    })

                    disc = self.discovery_engine.discover_from_transformation(
                        prev_code, current_code, best_child.action_taken, gen, target_name
                    )
                    if disc:
                        discovery_events.append({
                            "generation": gen,
                            "discovered_primitive": disc.name,
                            "pattern_hash": disc.pattern_hash
                        })

                    root = MCTSNode(state_code=current_code)

            gen_velocity = current_score - gen_start_score
            topology.adapt_topology(gen_velocity)

        wall_time_ms = round((time.time() - start_time) * 1000.0, 2)

        return {
            "target": target_name,
            "seed": self.seed,
            "search_mode": "MCTS_PUCT_POLICY_PRIORS",
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
