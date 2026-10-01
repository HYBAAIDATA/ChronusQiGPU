"""
EUCLID Intelligence Engine: Lucas & Pisot Scale Intelligence Evaluation
========================================================================
EUCLID owns overall Intelligence analysis across the platform.

Uses Lucas Sequence (L_n) and Pisot-Vijayaraghavan numbers with the
Lucas 20^(phi * t_p) scale formula:
    Intelligence_EUCLID = L_n * 20^(phi * t_p)

where:
    - L_n is the n-th Lucas number (L_0 = 2, L_1 = 1, L_2 = 3, L_3 = 4, L_4 = 7, ...)
    - phi is the Golden Ratio = (1 + sqrt(5)) / 2
    - t_p is topological time / phase transition index (supplied by the host)

Mathematical properties relied on by the invariant checks:
    - Positivity: L(x) = φ^x + cos(πx)·φ^(−x) ≥ φ^x − φ^(−x) > 0 for x > 0, and L(0) = 2,
      so Intelligence > 0 for every input. (The continuous extension dips to ≈ 0.913
      near x ≈ 0.84, so "≥ 2" is not a property of the formula; discrete L_n ≥ 1.)
    - Monotonicity in x: L(x) is strictly increasing for x ≳ 0.84, which covers every
      non-trivial module (x > 3 for any function-bearing code).
    - Pisot rounding identity: φ is a Pisot number, so L_n = round(φ^n) for n ≥ 2.
    - Comparisons between two codes must use the same t_p; the factor 20^(φ·t_p)
      cancels in the ratio, leaving L(x_mut) / L(x_orig).

The Lucas index is computed over the effective AST (core.structure), so dead,
duplicated or unreferenced code does not raise it.
"""

import ast
import math
from typing import Dict, Any, Tuple, Optional

from pythagoras.core.structure import analyze_structure, StructureReport

PHI = (1.0 + math.sqrt(5)) / 2.0  # Golden Ratio / Primary Pisot Number (~1.618033988749895)
PLASTIC_PISOT = 1.324717957244746  # Smallest Pisot-Vijayaraghavan number


class LucasSequenceCalculator:
    """Computes exact and continuous Lucas numbers L_n = phi^n + (-phi)^(-n)."""

    @staticmethod
    def exact_lucas(n: int) -> int:
        """Returns exact n-th Lucas number for integer n >= 0."""
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
        """Continuous extension of Lucas numbers via Binet-style formula."""
        x_clamped = max(0.0, float(x))
        term1 = math.pow(PHI, x_clamped)
        # Avoid zero division or negative powers overflow
        term2 = math.cos(math.pi * x_clamped) * math.pow(PHI, -x_clamped)
        return term1 + term2


class EuclidIntelligenceEngine:
    """
    EUCLID Intelligence Engine: Primary Intelligence Evaluator.
    EUCLID owns overall intelligence measurement, structural reasoning, and scaling.
    """

    def __init__(self, pisot_base: float = 20.0):
        self.pisot_base = pisot_base
        self.lucas_calc = LucasSequenceCalculator()

    def calculate_lucas_index(self, code_str: str, report: Optional[StructureReport] = None) -> Tuple[int, float]:
        """
        Derives discrete Lucas index n and continuous Lucas parameter x from the effective
        AST's depth, size, live function count and coherent annotation density.
        """
        report = report or analyze_structure(code_str)
        if not report.parse_ok:
            return 0, 0.0
        raw_x = (report.depth * 0.5) + (math.log2(max(report.effective_nodes, 1)) * 0.8) \
            + (report.function_count * 1.2) + (report.annotation_density * 3.0)
        return max(0, int(round(raw_x))), max(0.0, raw_x)

    @staticmethod
    def lucas_lock(continuous_x: float) -> float:
        """Pisot proximity: 1.0 when x sits exactly on a Lucas level, 0.0 midway between levels."""
        return round(1.0 - 2.0 * abs(continuous_x - round(continuous_x)), 6)

    def compute_intelligence_scale(self, code_str: str, topological_time: float = 0.0) -> Dict[str, Any]:
        """
        Computes EUCLID Intelligence Scale using the Lucas 20^(phi * t_p) formula:
            Intelligence = L_n * 20^(phi * t_p)
        """
        t_p = max(0.0, float(topological_time))
        report = analyze_structure(code_str)
        discrete_n, continuous_x = self.calculate_lucas_index(code_str, report)

        lucas_discrete = self.lucas_calc.exact_lucas(discrete_n)
        lucas_continuous = self.lucas_calc.continuous_lucas(continuous_x)

        # Scale factor 20^(phi * t_p)
        scale_exponent = PHI * t_p
        # Prevent overflow for large t_p
        scale_exponent = min(scale_exponent, 50.0)
        pisot_scale = math.pow(self.pisot_base, scale_exponent)

        raw_intelligence = lucas_continuous * pisot_scale
        exact_intelligence = lucas_discrete * pisot_scale

        return {
            "owner": "EUCLID_REPO_INTELLIGENCE",
            "intelligence_score": round(raw_intelligence, 6),
            "exact_lucas_score": round(exact_intelligence, 6),
            "lucas_index_discrete": discrete_n,
            "lucas_index_continuous": round(continuous_x, 4),
            "lucas_value_L_n": lucas_discrete,
            "topological_time_t_p": round(t_p, 4),
            "pisot_scaling_factor": round(pisot_scale, 6),
            "lucas_lock": self.lucas_lock(continuous_x),
            "parse_ok": report.parse_ok,
            "scaling_formula": "Intelligence = L_n * 20^(phi * t_p)"
        }

    def _get_ast_depth(self, node: ast.AST, current_depth: int = 0) -> int:
        children = list(ast.iter_child_nodes(node))
        if not children:
            return current_depth
        return max(self._get_ast_depth(child, current_depth + 1) for child in children)
