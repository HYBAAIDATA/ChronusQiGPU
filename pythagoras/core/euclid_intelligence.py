"""EUCLID repository-intelligence evaluation for PYTHAGORAS v12."""

import ast
import math
from typing import Any, Dict, Tuple

PHI = (1.0 + math.sqrt(5)) / 2.0
PLASTIC_PISOT = 1.324717957244746


class LucasSequenceCalculator:
    """Compute exact and continuous Lucas values."""

    @staticmethod
    def exact_lucas(n: int) -> int:
        if n < 0:
            raise ValueError(f"Lucas index n must be non-negative, got {n}")
        if n == 0:
            return 2
        if n == 1:
            return 1
        a, b = 2, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return b

    @staticmethod
    def continuous_lucas(x: float) -> float:
        x = max(0.0, float(x))
        return math.pow(PHI, x) + math.cos(math.pi * x) * math.pow(PHI, -x)


class EuclidIntelligenceEngine:
    """EUCLID-owned Intelligence scale: L_n * 20^(phi * t_p)."""

    def __init__(self, pisot_base: float = 20.0) -> None:
        if not math.isfinite(pisot_base) or pisot_base <= 0.0:
            raise ValueError("pisot_base must be finite and positive")
        self.pisot_base = float(pisot_base)
        self.lucas_calc = LucasSequenceCalculator()

    def calculate_lucas_index(self, code_str: str) -> Tuple[int, float]:
        try:
            tree = ast.parse(code_str)
        except (SyntaxError, ValueError, TypeError):
            return 0, 0.0
        depth = self._get_ast_depth(tree)
        nodes = list(ast.walk(tree))
        node_count = len(nodes)
        ann_assigns = sum(isinstance(node, ast.AnnAssign) for node in nodes)
        funcs = sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in nodes)
        annotation_density = ann_assigns / max(node_count, 1)
        raw_x = (
            depth * 0.5
            + math.log2(max(node_count, 1)) * 0.8
            + funcs * 1.2
            + annotation_density * 3.0
        )
        return max(0, int(round(raw_x))), max(0.0, raw_x)

    def compute_intelligence_scale(
        self, code_str: str, topological_time: float = 0.0
    ) -> Dict[str, Any]:
        t_p = max(0.0, float(topological_time))
        if not math.isfinite(t_p):
            raise ValueError("topological_time must be finite")
        discrete_n, continuous_x = self.calculate_lucas_index(code_str)
        lucas_discrete = self.lucas_calc.exact_lucas(discrete_n)
        lucas_continuous = self.lucas_calc.continuous_lucas(continuous_x)
        scale_exponent = min(PHI * t_p, 50.0)
        pisot_scale = math.pow(self.pisot_base, scale_exponent)
        return {
            "owner": "EUCLID_REPO_INTELLIGENCE",
            "intelligence_score": round(lucas_continuous * pisot_scale, 6),
            "exact_lucas_score": round(lucas_discrete * pisot_scale, 6),
            "lucas_index_discrete": discrete_n,
            "lucas_index_continuous": round(continuous_x, 4),
            "lucas_value_L_n": lucas_discrete,
            "topological_time_t_p": round(t_p, 4),
            "pisot_scaling_factor": round(pisot_scale, 6),
            "scaling_formula": "Intelligence = L_n * 20^(phi * t_p)",
        }

    def _get_ast_depth(self, node: ast.AST, current_depth: int = 0) -> int:
        children = list(ast.iter_child_nodes(node))
        if not children:
            return current_depth
        return max(self._get_ast_depth(child, current_depth + 1) for child in children)
