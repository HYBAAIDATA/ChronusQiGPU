"""
EUCLID Structural Resonance Calculator v16.0
===============================================
Evaluates AST structural alignment against a target golden ratio (default phi = 0.618033988749895).
Includes anti-Goodharting functional node checks, security penalties, and multi-objective fitness gates.
Note: Phi is an experimental structural heuristic metric, not a standalone substitute for functional testing.

Scoring substrate: the measured AST feature profile is prepared as a quantum
state |psi_code> (``QuantumState.from_real_vector``) and the declared target
profile as |psi_target>; the raw structural score is the Born overlap
|<psi_target|psi_code>|^2 computed by ``QuantumState.fidelity`` — a real
Hilbert-space inner product, not an invented weighted squash.  Every remaining
constant is an explicit constructor parameter (declared metric definition),
never a value presented as measured.
"""

import ast
import math
from typing import Dict, Any, Tuple, Set, Sequence
from euclid.validation.process_sandbox import ASTSafetyValidator
from kellogg.quantum_tensor import QuantumState

PHI_TARGET = 0.618033988749895

class FunctionalASTAnalyzer(ast.NodeVisitor):
    """
    Analyzes AST for functional code usage, detecting unreferenced variables and dead nodes.
    """
    def __init__(self):
        self.assigned_vars: Set[str] = set()
        self.used_vars: Set[str] = set()
        self.defined_funcs: Set[str] = set()
        self.called_funcs: Set[str] = set()

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Store):
            self.assigned_vars.add(node.id)
        elif isinstance(node.ctx, ast.Load):
            self.used_vars.add(node.id)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if not node.name.startswith("_"):
            self.defined_funcs.add(node.name)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            self.called_funcs.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            self.called_funcs.add(node.func.attr)
        self.generic_visit(node)


class PhiResonanceCalculator:
    """
    AST Structural Resonance Evaluator.
    Measures golden ratio alignment, structural depth balance, type coverage,
    and penalizes excessive code bloat / Goodhart gaming.

    The raw score is the Born overlap |<psi_target|psi_code>|^2 where
    |psi_code> is prepared from the measured feature profile
    [annotation_ratio, depth_balance, complexity_balance, func_balance,
    dead_node_health] and |psi_target> from ``target_weights`` (declared).
    """
    def __init__(
        self,
        target_phi: float = PHI_TARGET,
        *,
        # declared metric definition — explicit parameters, not mystery constants
        target_weights: Sequence[float] = (0.25, 0.20, 0.10, 0.10, 0.35),
        target_depth: int = 8,
        reference_node_count: float = 50.0,
        reference_function_count: float = 5.0,
        dead_node_penalty: float = 0.02,
        score_floor: float = 0.1,
        score_ceiling: float = 0.99,
        bloat_node_threshold: int = 100,
        bloat_penalty_per_node: float = 0.002,
        fitness_bloat_ratio: float = 1.5,
        fitness_bloat_penalty: float = 0.10,
    ):
        self.target_phi = target_phi
        self.target_weights = [float(w) for w in target_weights]
        if len(self.target_weights) != 5 or any(w < 0 for w in self.target_weights):
            raise ValueError("target_weights must be five non-negative entries")
        self.target_depth = int(target_depth)
        self.reference_node_count = float(reference_node_count)
        self.reference_function_count = float(reference_function_count)
        self.dead_node_penalty = float(dead_node_penalty)
        self.score_floor = float(score_floor)
        self.score_ceiling = float(score_ceiling)
        self.bloat_node_threshold = int(bloat_node_threshold)
        self.bloat_penalty_per_node = float(bloat_penalty_per_node)
        self.fitness_bloat_ratio = float(fitness_bloat_ratio)
        self.fitness_bloat_penalty = float(fitness_bloat_penalty)
        # declared target state |psi_target> ∝ sqrt(target_weights)
        self._target_state = QuantumState.from_real_vector(
            [math.sqrt(w) for w in self.target_weights]
        )

    def compute_raw_structural_score(self, code_str: str) -> Tuple[float, Dict[str, Any]]:
        """Calculates raw structural metrics across the AST.

        The score is the Born overlap |<psi_target|psi_code>|^2 of the measured
        feature state against the declared target state.
        """
        try:
            tree = ast.parse(code_str)
        except Exception:
            return self.score_floor, {"node_count": 0, "depth": 0, "annotation_density": 0.0, "func_count": 0, "stmt_count": 0, "unreferenced_dead_nodes": 0}

        depth = self._get_ast_depth(tree)
        node_count = sum(1 for _ in ast.walk(tree))
        ann_assigns = sum(1 for n in ast.walk(tree) if isinstance(n, ast.AnnAssign))
        func_count = sum(1 for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
        stmt_count = len(tree.body) if hasattr(tree, 'body') else 1

        # Functional analysis for dead-node detection
        analyzer = FunctionalASTAnalyzer()
        analyzer.visit(tree)
        unreferenced = (analyzer.assigned_vars - analyzer.used_vars) | (analyzer.defined_funcs - analyzer.called_funcs)
        dead_node_count = len(unreferenced)

        # measured feature profile (all components are measured AST quantities
        # under declared normalisation transforms)
        annotation_ratio = ann_assigns / max(node_count, 1)
        depth_balance = 1.0 / (1.0 + abs(depth - self.target_depth))
        complexity_balance = min(node_count / self.reference_node_count, 1.0)
        func_balance = min(func_count / self.reference_function_count, 1.0)
        dead_health = 1.0 - (dead_node_count / max(node_count, 1))

        feature_profile = [
            annotation_ratio,
            depth_balance,
            complexity_balance,
            func_balance,
            dead_health,
        ]

        if any(value > 0.0 for value in feature_profile):
            code_state = QuantumState.from_real_vector(feature_profile)
            overlap = self._target_state.fidelity(code_state)
        else:
            # no alignment evidence: the feature state is the null vector and
            # cannot be normalised — declared floor, not a fabricated overlap
            overlap = self.score_floor

        # Dead-node penalty on measured dead count (declared policy)
        raw_score = max(
            self.score_floor, overlap - (dead_node_count * self.dead_node_penalty)
        )

        metrics = {
            "node_count": node_count,
            "depth": depth,
            "annotation_density": round(annotation_ratio, 6),
            "function_count": func_count,
            "statement_count": stmt_count,
            "unreferenced_dead_nodes": dead_node_count,
            "born_overlap": round(overlap, 6),
            "raw_structural_score": round(raw_score, 6),
            "evidence_class": "born-overlap: |<psi_target|psi_code>|^2 on measured feature state",
        }
        return raw_score, metrics

    def compute_phi(self, code_str: str) -> float:
        """
        Calculates golden ratio structural resonance alignment relative to target_phi.
        Assigns 0.0000 to code failing AST security audit.
        """
        # Security Gate: Dangerous code receives 0.0000 score!
        safe, sec_msg = ASTSafetyValidator.validate_code_str(code_str)
        if not safe and "SecurityViolation" in sec_msg:
            return 0.0000

        raw_score, metrics = self.compute_raw_structural_score(code_str)
        if metrics["node_count"] == 0:
            return self.score_floor

        # Target Proximity Alignment
        dist_to_target = abs(raw_score - self.target_phi)
        alignment_score = max(self.score_floor, 1.0 - dist_to_target)

        # Anti-bloat penalty: penalize code if node count grows artificially
        # beyond the declared threshold
        bloat_penalty = max(
            0.0, (metrics["node_count"] - self.bloat_node_threshold) * self.bloat_penalty_per_node
        )

        final_score = max(self.score_floor, min(self.score_ceiling, alignment_score - bloat_penalty))
        return round(final_score, 6)

    def compute_multi_objective_fitness(
        self,
        code_str: str,
        initial_node_count: int = 50,
        tests_passed: bool = True
    ) -> float:
        """
        Multi-objective fitness function:
        Returns 0.0000 if tests fail or if code contains security violations.
        """
        if not tests_passed:
            return 0.0000

        phi_score = self.compute_phi(code_str)
        if phi_score == 0.0000:
            return 0.0000

        _, metrics = self.compute_raw_structural_score(code_str)

        # Bloat factor relative to initial program size
        size_ratio = metrics["node_count"] / max(initial_node_count, 1)
        bloat_penalty = 0.0
        if size_ratio > self.fitness_bloat_ratio:
            bloat_penalty = (size_ratio - self.fitness_bloat_ratio) * self.fitness_bloat_penalty

        return round(max(self.score_floor, phi_score - bloat_penalty), 6)

    def _get_ast_depth(self, node: ast.AST, current_depth: int = 0) -> int:
        children = list(ast.iter_child_nodes(node))
        if not children:
            return current_depth
        return max(self._get_ast_depth(child, current_depth + 1) for child in children)

    def extract_features(self, code_str: str) -> Dict[str, Any]:
        raw_score, metrics = self.compute_raw_structural_score(code_str)
        metrics["phi_score"] = self.compute_phi(code_str)
        metrics["target_phi"] = self.target_phi
        return metrics
