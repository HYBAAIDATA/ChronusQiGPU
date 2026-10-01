"""PYTHAGORAS v12 structural phi-resonance metric.

This is the drop-in metric API. It is intentionally evidence-first: invalid
source returns the documented floor score and feature extraction reports zero
measured structure rather than manufacturing fallback AST statistics.
"""

from __future__ import annotations

import ast
import math
from typing import Any, Dict

PHI_TARGET = 0.618033988749895


class PhiResonanceCalculator:
    """Calculate normalized structural resonance from Python AST topology."""

    def __init__(self, target_phi: float = PHI_TARGET) -> None:
        self.target_phi = float(target_phi)

    def compute_phi(self, code_str: str) -> float:
        """Return a normalized structural score in ``[0.10, 0.99]``."""
        try:
            tree = ast.parse(code_str)
        except (SyntaxError, ValueError, TypeError):
            return 0.1000

        nodes = list(ast.walk(tree))
        depth = self._get_ast_depth(tree)
        node_count = len(nodes)
        ann_assigns = sum(isinstance(node, ast.AnnAssign) for node in nodes)
        func_count = sum(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in nodes
        )

        annotation_ratio = ann_assigns / max(node_count, 1)
        depth_balance = 1.0 / (1.0 + abs(depth - 8))
        complexity_balance = min(node_count / 50.0, 1.0)
        func_balance = min(func_count / 5.0, 1.0)

        raw_score = (
            0.35
            + 0.25 * annotation_ratio
            + 0.20 * depth_balance
            + 0.10 * complexity_balance
            + 0.10 * func_balance
        )
        golden_ratio = (1.0 + math.sqrt(5.0)) / 2.0
        golden_alignment = 1.0 - abs((raw_score % golden_ratio) - (1.0 / golden_ratio))
        score = raw_score + 0.05 * golden_alignment
        return round(min(0.9900, max(0.1000, score)), 6)

    def extract_features(self, code_str: str) -> Dict[str, Any]:
        """Return measured AST features and parse validity for ``code_str``."""
        try:
            tree = ast.parse(code_str)
        except (SyntaxError, ValueError, TypeError):
            return {
                "parse_valid": False,
                "node_count": 0,
                "depth": 0,
                "annotation_density": 0.0,
                "function_count": 0,
                "statement_count": 0,
                "phi_score": 0.1000,
            }

        nodes = list(ast.walk(tree))
        node_count = len(nodes)
        depth = self._get_ast_depth(tree)
        ann_assigns = sum(isinstance(node, ast.AnnAssign) for node in nodes)
        func_count = sum(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in nodes
        )
        stmt_count = len(getattr(tree, "body", []))
        return {
            "parse_valid": True,
            "node_count": node_count,
            "depth": depth,
            "annotation_density": round(ann_assigns / max(node_count, 1), 6),
            "function_count": func_count,
            "statement_count": stmt_count,
            "phi_score": self.compute_phi(code_str),
        }

    def compute(self, code_str: str) -> float:
        """Compatibility alias used by repository scanners."""
        return self.compute_phi(code_str)

    def _get_ast_depth(self, node: ast.AST, current_depth: int = 0) -> int:
        children = list(ast.iter_child_nodes(node))
        if not children:
            return current_depth
        return max(self._get_ast_depth(child, current_depth + 1) for child in children)
