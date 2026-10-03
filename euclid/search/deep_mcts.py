"""EUCLID Elevated Multi-Step MCTS (v16 elevation).

Preserves the merged v16 :class:`MCTSSearchEngine` untouched.  This module
provides the deeper search the v16 engine reviewed as missing:

* true multi-depth tree traversal (selection descends, not root-only);
* state/transposition reuse keyed by canonical AST hash;
* persistent policy priors (surrogate) blended with measured world-model
  priors when supplied;
* multi-step credit assignment (backpropagation along the full trajectory);
* uncertainty-aware exploration (PUCT with explicit c_puct, visit counts);
* progressive widening as the operator vocabulary grows;
* terminal/test-aware values (a candidate failing tests is terminal);
* resource-aware search (hard evaluation and wall-clock budgets);
* trajectory export/ingest for replay from prior successful searches;
* explicit separation of policy prior, value estimate, measured reward and
  the phi diagnostic — phi is telemetry, never the promotion objective.

No AlphaZero equivalence is claimed: this is PUCT-style tree search over a
small AST operator vocabulary with a learned linear surrogate as prior.
"""
from __future__ import annotations

import ast
import hashlib
import math
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from euclid.core.phi_metric import PhiResonanceCalculator
from euclid.core.primitives import ASTPrimitives
from euclid.surrogate.adaptive_surrogate import AdaptiveOperatorSurrogate
from euclid.transfer.persistent_repository import PersistentPrimitiveRepository
from euclid.validation.process_sandbox import IsolatedProcessEvaluator

TERMINAL_TEST_FAILURE_VALUE = -1.0


def state_key(code: str) -> str:
    """Canonical state identity for transposition reuse."""
    try:
        canonical = ast.dump(ast.parse(code))
    except SyntaxError:
        canonical = code
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


@dataclass
class DeepMCTSNode:
    key: str
    state_code: str
    depth: int
    parent: Optional["DeepMCTSNode"] = None
    action_taken: Optional[str] = None
    prior: float = 1.0
    children: Dict[str, "DeepMCTSNode"] = field(default_factory=dict)
    visit_count: int = 0
    total_value: float = 0.0
    terminal: bool = False
    exhausted: bool = False  # every operator from this state already linked

    @property
    def mean_value(self) -> float:
        return self.total_value / self.visit_count if self.visit_count else 0.0

    def update(self, value: float) -> None:
        """Backpropagates one measured value through this node."""
        self.visit_count += 1
        self.total_value += value

    def puct(self, c_puct: float) -> float:
        parent_visits = self.parent.visit_count if self.parent else 1
        exploration = c_puct * self.prior * (math.sqrt(max(parent_visits, 1)) / (1.0 + self.visit_count))
        return self.mean_value + exploration


@dataclass(frozen=True)
class SearchBudget:
    max_evaluations: int = 24
    max_depth: int = 4
    max_wall_seconds: float = 30.0
    widening_k: int = 2
    widening_alpha: float = 0.5

    def __post_init__(self) -> None:
        if self.max_evaluations < 1 or self.max_depth < 1:
            raise ValueError("budget requires positive evaluations and depth")
        if self.max_wall_seconds <= 0 or self.widening_k < 1 or not 0 < self.widening_alpha <= 1:
            raise ValueError("invalid budget parameters")


class DeepMCTSEngine:
    """Budgeted multi-depth MCTS over AST operator sequences."""

    def __init__(
        self,
        repository: Optional[PersistentPrimitiveRepository] = None,
        target_phi: float = 0.618033988749895,
        seed: int = 42,
        c_puct: float = 1.4,
        evaluator: Optional[IsolatedProcessEvaluator] = None,
        world_model: Any = None,
        world_model_prior_weight: float = 0.5,
    ) -> None:
        self.seed = seed
        self._rng = random.Random(seed)
        self.c_puct = c_puct
        self.calculator = PhiResonanceCalculator(target_phi)
        self.base_operators = ASTPrimitives.get_all_operators()
        self.evaluator = evaluator or IsolatedProcessEvaluator(timeout_sec=2.0)
        self.surrogate = AdaptiveOperatorSurrogate(learning_rate=0.05)
        self.repository = repository or PersistentPrimitiveRepository()
        # Optional learned transition model; blended into priors only.
        self.world_model = world_model
        if not 0.0 <= world_model_prior_weight <= 1.0:
            raise ValueError("world_model_prior_weight must be in [0,1]")
        self.world_model_prior_weight = world_model_prior_weight
        self._trajectory_priors: Dict[str, float] = {}

    # -- priors ---------------------------------------------------------------
    def ingest_trajectories(self, trajectories: Sequence[Sequence[str]]) -> int:
        """Replay prior successful operator sequences as soft priors."""
        ingested = 0
        for trajectory in trajectories:
            for position, action in enumerate(trajectory):
                key = f"{position}:{action}"
                self._trajectory_priors[key] = self._trajectory_priors.get(key, 0.0) + 1.0
                ingested += 1
        return ingested

    def _priors(self, code: str, ops: Sequence[str], depth: int, signature: Any = None) -> Dict[str, float]:
        features = self.calculator.extract_features(code)
        raw: Dict[str, float] = {}
        for op_name in ops:
            prior = self.surrogate.predict_gain(features, op_name)
            prior += 0.05 * self._trajectory_priors.get(f"{depth}:{op_name}", 0.0)
            if self.world_model is not None and signature is not None:
                try:
                    predicted = self.world_model.expected_gain(signature, op_name)
                except AttributeError:
                    predicted = None
                if predicted is not None:
                    w = self.world_model_prior_weight
                    prior = (1 - w) * prior + w * float(predicted)
            raw[op_name] = prior
        peak = max(raw.values()) if raw else 0.0
        exp = {op: math.exp(value - peak) for op, value in raw.items()}
        total = sum(exp.values()) or 1.0
        return {op: value / total for op, value in exp.items()}

    # -- evaluation -------------------------------------------------------------
    def _evaluate(
        self,
        code: str,
        baseline_fitness: float,
        initial_node_count: int,
        external_test_runner: Optional[Callable[[str], bool]],
        external_test_code: Optional[str],
    ) -> Tuple[bool, float, str]:
        """Sandbox-gated measured evaluation.  Returns (valid, measured_reward, diagnostic)."""
        parse_v, compile_v, test_v, msg = self.evaluator.evaluate_validity(
            code, external_test_runner, external_test_code
        )
        if not (parse_v and compile_v and test_v):
            return False, TERMINAL_TEST_FAILURE_VALUE, msg
        fitness = self.calculator.compute_multi_objective_fitness(
            code, initial_node_count=initial_node_count, tests_passed=True
        )
        return True, round(fitness - baseline_fitness, 6), msg

    # -- search -------------------------------------------------------------------
    def search(
        self,
        target_name: str,
        initial_code: str,
        *,
        budget: SearchBudget | None = None,
        signature: Any = None,
        external_test_runner: Optional[Callable[[str], bool]] = None,
        external_test_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        budget = budget or SearchBudget()
        start = time.monotonic()
        root_key = state_key(initial_code)
        baseline_ok, _, baseline_msg = self._evaluate(
            initial_code, 0.0, 1, external_test_runner, external_test_code
        )
        # baseline fitness uses the true node count, so recompute honestly
        initial_features = self.calculator.extract_features(initial_code)
        initial_node_count = int(initial_features.get("node_count", 50))
        if baseline_ok:
            baseline_fitness = self.calculator.compute_multi_objective_fitness(
                initial_code, initial_node_count=initial_node_count, tests_passed=True
            )
        else:
            baseline_fitness = 0.0

        table: Dict[str, DeepMCTSNode] = {}
        root = DeepMCTSNode(root_key, initial_code, depth=0)
        table[root_key] = root
        transposition_hits = 0
        evaluations = 0
        depth_histogram: Dict[int, int] = {}
        phi_diagnostics: List[Dict[str, float]] = []

        ops_all = [name for name, _ in self.base_operators] + [
            name for name, _ in self.repository.get_all_primitives()
        ]
        op_funcs = dict(self.base_operators)
        for name, func in self.repository.get_all_primitives():
            op_funcs[name] = func

        def widen_limit(node: DeepMCTSNode) -> int:
            return min(
                len(ops_all),
                max(1, math.ceil(budget.widening_k * (max(node.visit_count, 1) ** budget.widening_alpha))),
            )

        def expand(node: DeepMCTSNode) -> None:
            priors = self._priors(node.state_code, ops_all, node.depth, signature)
            allowed = widen_limit(node)
            ranked = sorted(ops_all, key=lambda op: priors[op], reverse=True)
            added = 0
            for op_name in ranked:
                if op_name in node.children:
                    continue
                if added >= allowed:
                    break
                node.children[op_name] = DeepMCTSNode(
                    key="", state_code=node.state_code, depth=node.depth + 1,
                    parent=node, action_taken=op_name, prior=priors[op_name],
                )
                added += 1
            if len(node.children) >= len(ops_all):
                node.exhausted = True

        def select(node: DeepMCTSNode) -> DeepMCTSNode:
            """Descend through evaluated nodes; stop at an unevaluated child,
            a terminal node, the depth bound, or a fully exhausted node."""
            while True:
                if node.terminal or node.depth >= budget.max_depth or node.visit_count == 0:
                    return node
                if not node.children and not node.exhausted:
                    expand(node)  # node state is known (evaluated), children are valid
                if not node.children:
                    node.exhausted = True
                    return node
                if not node.exhausted and len(node.children) < widen_limit(node):
                    expand(node)  # progressive widening on revisit
                node = max(node.children.values(), key=lambda c: c.puct(self.c_puct))

        root.visit_count = 1  # root state was evaluated as the baseline
        best_code, best_fitness = initial_code, baseline_fitness
        best_trajectory: List[str] = []
        stalled_iterations = 0

        while evaluations < budget.max_evaluations:
            if time.monotonic() - start > budget.max_wall_seconds:
                break
            if stalled_iterations > budget.max_evaluations:
                break  # tree exhausted: no unevaluated frontier remains
            leaf = select(root)
            trajectory: List[DeepMCTSNode] = []
            node = leaf
            while node is not None:
                trajectory.append(node)
                node = node.parent
            trajectory.reverse()

            revisit_only = (
                leaf.visit_count > 0
                and (leaf.terminal or leaf.depth >= budget.max_depth or leaf.exhausted)
            )
            if revisit_only:
                stalled_iterations += 1
                for node in [leaf] + trajectory[:-1]:
                    node.update(leaf.mean_value)
                continue
            op_name = leaf.action_taken
            if op_name is None:
                stalled_iterations += 1
                continue
            parent_state = leaf.parent.state_code if leaf.parent else initial_code
            op_func = op_funcs[op_name]
            cand_code, _ = op_func(parent_state, self.seed + evaluations)
            evaluations += 1
            stalled_iterations = 0
            depth_histogram[leaf.depth] = depth_histogram.get(leaf.depth, 0) + 1

            cand_key = state_key(cand_code)
            if cand_key in table:
                # Transposition: this operator sequence reached a known state.
                transposition_hits += 1
                existing = table[cand_key]
                leaf.key = cand_key
                leaf.state_code = existing.state_code
                value = existing.mean_value if existing.visit_count else 0.0
                for node in trajectory:
                    node.update(value)
                continue

            valid, measured_reward, diagnostic = self._evaluate(
                cand_code, baseline_fitness, initial_node_count,
                external_test_runner, external_test_code,
            )
            leaf.key = cand_key
            leaf.state_code = cand_code
            table[cand_key] = leaf
            phi_diag = self.calculator.compute_phi(cand_code) if valid else 0.0
            phi_diagnostics.append({"phi_diagnostic": phi_diag, "measured_reward": measured_reward})

            features = self.calculator.extract_features(parent_state)
            self.surrogate.update(features, op_name, measured_reward, valid, valid)
            if self.world_model is not None and signature is not None:
                observe = getattr(self.world_model, "observe_gain", None)
                if observe is not None:
                    observe(signature, op_name, measured_reward)

            if not valid:
                leaf.terminal = True  # test/parse failure is terminal evidence
            value = measured_reward
            for node in trajectory:
                node.update(value)

            if valid:
                cand_fitness = self.calculator.compute_multi_objective_fitness(
                    cand_code, initial_node_count=initial_node_count, tests_passed=True
                )
                if cand_fitness > best_fitness:
                    best_fitness = cand_fitness
                    best_code = cand_code
                    best_trajectory = [
                        n.action_taken for n in trajectory if n.action_taken
                    ]

        wall_time_ms = round((time.monotonic() - start) * 1000.0, 2)
        return {
            "target": target_name,
            "seed": self.seed,
            "search_mode": "DEEP_MCTS_PUCT_TRANSPOSITION_BUDGETED",
            "initial_fitness": round(baseline_fitness, 6),
            "best_fitness": round(best_fitness, 6),
            "measured_improvement": round(best_fitness - baseline_fitness, 6),
            "evaluations_used": evaluations,
            "evaluation_budget": budget.max_evaluations,
            "max_depth_reached": max(depth_histogram) if depth_histogram else 0,
            "depth_histogram": {str(k): v for k, v in sorted(depth_histogram.items())},
            "transposition_table_size": len(table),
            "transposition_hits": transposition_hits,
            "best_trajectory": best_trajectory,
            "surrogate_rmse": self.surrogate.compute_rmse(),
            "phi_diagnostics": phi_diagnostics,
            "separation_notice": (
                "policy priors (surrogate+trajectory), value estimates (visit means), "
                "measured reward (sandbox-gated multi-objective fitness delta) and the "
                "phi diagnostic are distinct quantities; phi is telemetry only"
            ),
            "wall_time_ms": wall_time_ms,
            "best_code": best_code,
        }


__all__ = ["DeepMCTSEngine", "DeepMCTSNode", "SearchBudget", "state_key",
           "TERMINAL_TEST_FAILURE_VALUE"]
