"""
EUCLID Structural Resonance Calculator v16.0
===============================================
Evaluates AST structural alignment against a target golden ratio (default phi = 0.618033988749895).
Includes anti-Goodharting functional node checks, security penalties, and multi-objective fitness gates.
Note: Phi is an experimental structural heuristic metric, not a standalone substitute for functional testing.
"""

import ast
import math
from typing import Dict, Any, Tuple, Set
from euclid.validation.process_sandbox import ASTSafetyValidator

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
    """
    def __init__(self, target_phi: float = PHI_TARGET):
        self.target_phi = target_phi

    def compute_raw_structural_score(self, code_str: str) -> Tuple[float, Dict[str, Any]]:
        """Calculates raw structural metrics across the AST."""
        try:
            tree = ast.parse(code_str)
        except Exception:
            return 0.1000, {"node_count": 0, "depth": 0, "annotation_density": 0.0, "func_count": 0, "stmt_count": 0, "unreferenced_dead_nodes": 0}

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

        annotation_ratio = ann_assigns / max(node_count, 1)
        depth_balance = 1.0 / (1.0 + abs(depth - 8))
        complexity_balance = min(node_count / 50.0, 1.0)
        func_balance = min(func_count / 5.0, 1.0)

        raw_score = 0.35 + (0.25 * annotation_ratio) + (0.20 * depth_balance) + (0.10 * complexity_balance) + (0.10 * func_balance)
        
        # Dead node penalty
        raw_score = max(0.1000, raw_score - (dead_node_count * 0.02))

        metrics = {
            "node_count": node_count,
            "depth": depth,
            "annotation_density": round(annotation_ratio, 6),
            "function_count": func_count,
            "statement_count": stmt_count,
            "unreferenced_dead_nodes": dead_node_count,
            "raw_structural_score": round(raw_score, 6)
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
            return 0.1000

        # Target Proximity Alignment
        dist_to_target = abs(raw_score - self.target_phi)
        alignment_score = max(0.1000, 1.0 - dist_to_target)

        # Anti-bloat penalty: penalize code if node count grows artificially beyond 100
        bloat_penalty = max(0.0, (metrics["node_count"] - 100) * 0.002)
        
        final_score = max(0.1000, min(0.9900, alignment_score - bloat_penalty))
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
        if size_ratio > 1.5:
            bloat_penalty = (size_ratio - 1.5) * 0.10

        return round(max(0.1000, phi_score - bloat_penalty), 6)

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
