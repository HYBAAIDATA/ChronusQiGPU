"""
EUCLID Structural Complexity Engine v16.0
==========================================
Measures AST structural complexity heuristics using the Lucas Sequence (L_n) and tracks
topological phase transitions (t_p) as separate, un-conflated dimensions.
Note: Structural complexity and Lucas indices are mathematical code metrics, not empirical AGI metrics.
"""

import ast
import math
from typing import Dict, Any, Tuple

class LucasSequenceCalculator:
    """Calculates Lucas Sequence numbers L_n and continuous Pisot extensions."""
    
    @staticmethod
    def exact_lucas(n: int) -> int:
        """L_0 = 2, L_1 = 1, L_2 = 3, L_3 = 4, L_4 = 7, L_5 = 11, ..."""
        if n < 0:
            n = abs(n)
        if n == 0: return 2
        if n == 1: return 1
        a, b = 2, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return b

    @staticmethod
    def continuous_lucas(x: float) -> float:
        """Pisot continuous extension for Lucas sequence."""
        phi = (1.0 + math.sqrt(5)) / 2.0
        psi = (1.0 - math.sqrt(5)) / 2.0
        return math.pow(phi, x) + math.cos(x * math.pi) * math.pow(abs(psi), x)

class EuclidIntelligenceEngine:
    """
    EUCLID Structural Complexity Metric Engine.
    Evaluates AST complexity heuristics using Lucas indices (L_n) and topological time (t_p).
    """
    def __init__(self, owner: str = "EUCLID_REPO_INTELLIGENCE"):
        self.owner = owner

    def calculate_lucas_index(self, code_str: str) -> Tuple[int, float]:
        """
        Maps AST complexity and annotation coverage to Lucas index n.
        Guarantees discrete_n in {0, 2, 3, ...} so that L_n >= 2.0 unconditionally.
        """
        try:
            tree = ast.parse(code_str)
            node_count = sum(1 for _ in ast.walk(tree))
            ann_assigns = sum(1 for n in ast.walk(tree) if isinstance(n, ast.AnnAssign))
            func_count = sum(1 for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
        except Exception:
            node_count, ann_assigns, func_count = 1, 0, 0

        ann_density = ann_assigns / max(node_count, 1)
        base_n = int(math.log2(max(node_count, 1))) + func_count + int(ann_density * 5)
        
        # Non-degeneracy index mapping: ensure L_n >= 2.0 (n=0 -> L_0=2; n>=2 -> L_n>=3)
        if base_n <= 1:
            discrete_n = 0
        else:
            discrete_n = min(base_n, 30)

        continuous_x = float(discrete_n) + ann_density
        return discrete_n, round(continuous_x, 4)

    def compute_intelligence_metrics(self, code_str: str, topological_time: float = 0.0) -> Dict[str, Any]:
        """
        Evaluates EUCLID structural complexity metrics with strictly separated dimensions:
        - structural_complexity_L_n (L_n derived purely from current evolved AST)
        - topological_progression_time (t_p accepted phase transitions)
        - composite_time_projected_scale (L_n * 20^(phi * t_p))
        """
        discrete_n, continuous_x = self.calculate_lucas_index(code_str)
        lucas_val = LucasSequenceCalculator.exact_lucas(discrete_n)
        phi = (1.0 + math.sqrt(5)) / 2.0
        
        # Structural Complexity Score (Pure AST measure, L_n >= 2.0)
        structural_complexity = float(lucas_val)

        # Topological Time Scale (Time Progression Factor)
        t_p = max(0.0, float(topological_time))
        scale_exponent = min(phi * t_p, 20.0)  # Safety clamp against overflow
        pisot_multiplier = math.pow(20.0, scale_exponent)
        
        composite_scale = structural_complexity * pisot_multiplier

        return {
            "owner": self.owner,
            "structural_complexity_L_n": structural_complexity,
            "lucas_index_discrete": discrete_n,
            "topological_time_t_p": t_p,
            "pisot_time_multiplier": round(pisot_multiplier, 6),
            "composite_time_projected_scale": round(composite_scale, 6),
            "scaling_formula": "Structural = L_n; Composite = L_n * 20^(phi * t_p)"
        }
