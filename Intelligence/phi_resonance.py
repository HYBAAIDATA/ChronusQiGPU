"""
EUCLID INTELLIGENCE SUBSTRATE — PHI-RESONANCE CALCULATOR
Computes the φ-resonance score of a Python AST for structural coherence and self-optimisation.

Integrated into EUCLID (Intelligence) and accessible to Salamander (Self-Healing / Self-Optimisation).

Components:
1. Abstraction consistency: Uniformity of abstraction boundaries across function/class definitions.
2. Compositional depth balance: Proximity of nesting depth ratio to the golden ratio φ.
3. Information density proportionality: AST node cardinality normalized by maximum depth.
"""

from __future__ import annotations

import ast
import math
from typing import Any, Dict, List, Tuple
import numpy as np

# Golden ratio constant: (sqrt(5) - 1) / 2
PHI: float = (math.sqrt(5.0) - 1.0) / 2.0  # 0.6180339887498949

# Pisot-Vijayaraghavan spectral gaps:
PHI_POWERS: List[float] = [float(PHI**k) for k in range(9)]
PHASE_TRANSITION_PRIMARY: float = float(PHI**5)  # 0.0901699437...
PHASE_TRANSITION_SECONDARY: float = float(PHI**6)  # 0.0557280900...


class PhiResonanceCalculator:
    """
    Computes the φ-resonance score of a Python AST for Euclid's structural code assessment.
    """

    def __init__(self, phi_target: float = PHI):
        self.phi_target = float(phi_target)

    def compute(self, source: str) -> float:
        """
        Compute composite φ-score from Python source code.
        Returns a float in [0.0, 1.0].
        """
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return 0.0

        depth_map = self._build_depth_map(tree)

        abstraction = self._abstraction_consistency(tree, depth_map)
        depth_balance = self._compositional_depth_balance(tree, depth_map)
        density = self._information_density(tree, depth_map)

        phi_score = (abstraction + depth_balance + density) / 3.0
        return float(np.clip(phi_score, 0.0, 1.0))

    def compute_components(self, source: str) -> Dict[str, float]:
        """
        Compute breakdown of individual φ-score components.
        """
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return {
                "abstraction": 0.0,
                "depth_balance": 0.0,
                "density": 0.0,
                "composite": 0.0,
            }

        depth_map = self._build_depth_map(tree)
        abstraction = self._abstraction_consistency(tree, depth_map)
        depth_balance = self._compositional_depth_balance(tree, depth_map)
        density = self._information_density(tree, depth_map)
        composite = (abstraction + depth_balance + density) / 3.0

        return {
            "abstraction": float(abstraction),
            "depth_balance": float(depth_balance),
            "density": float(density),
            "composite": float(composite),
        }

    def _build_depth_map(self, tree: ast.AST) -> Dict[int, int]:
        """Fast O(N) node-to-depth map via preorder traversal."""
        depth_map: Dict[int, int] = {id(tree): 0}
        stack: List[Tuple[ast.AST, int]] = [(tree, 0)]
        while stack:
            parent, depth = stack.pop()
            child_depth = depth + 1
            for child in ast.iter_child_nodes(parent):
                depth_map[id(child)] = child_depth
                stack.append((child, child_depth))
        return depth_map

    def _abstraction_consistency(self, tree: ast.AST, depth_map: Dict[int, int]) -> float:
        """Measure consistency of abstraction levels across declarations."""
        depths: List[int] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                d = depth_map.get(id(node), 0)
                depths.append(d)

        if not depths:
            return 0.5
        if len(depths) == 1:
            return 1.0

        variance = float(np.var(depths))
        return float(1.0 / (1.0 + variance))

    def _compositional_depth_balance(self, tree: ast.AST, depth_map: Dict[int, int]) -> float:
        """Measure proximity of nesting depth ratio to φ."""
        depths: List[int] = []
        for node in ast.walk(tree):
            if isinstance(
                node,
                (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith),
            ):
                d = depth_map.get(id(node), 0)
                depths.append(d)

        if not depths:
            return 0.5

        max_d = max(depths)
        min_d = min(depths)

        if max_d == 0:
            return 0.5

        ratio = float(min_d) / float(max_d)
        return float(max(0.0, 1.0 - abs(ratio - self.phi_target)))

    def _information_density(self, tree: ast.AST, depth_map: Dict[int, int]) -> float:
        """Measure information density proportionality."""
        node_count = sum(1 for _ in ast.walk(tree))
        max_d = max(depth_map.values()) if depth_map else 0

        if max_d == 0:
            return 0.5

        density = float(node_count) / (float(max_d) * 10.0)
        return float(min(density, 1.0))

    def is_resonant(self, source: str) -> bool:
        """Check if source code achieves φ-resonance threshold."""
        return self.compute(source) >= self.phi_target

    def diagnose_manifold(self, source: str) -> Dict[str, Any]:
        """
        φ-sensitivity diagnostic for Salamander self-healing.
        Determines whether a module resides on a flat fitness manifold.
        """
        base_components = self.compute_components(source)
        base_phi = base_components["composite"]

        perturbation_deltas: List[float] = []

        # Perturbation 1: variable probe
        p1 = source + "\n_phi_probe_var_1 = 1\n"
        deltas_p1 = self.compute(p1) - base_phi
        perturbation_deltas.append(deltas_p1)

        # Perturbation 2: subroutine probe
        p2 = source + "\ndef _probe_subroutine():\n    return 42\n"
        perturbation_deltas.append(self.compute(p2) - base_phi)

        max_abs_delta = max(abs(d) for d in perturbation_deltas) if perturbation_deltas else 0.0
        is_degenerate = max_abs_delta < 1e-5

        return {
            "base_phi": base_phi,
            "components": base_components,
            "perturbation_deltas": perturbation_deltas,
            "max_abs_gradient": max_abs_delta,
            "is_degenerate_manifold": is_degenerate,
            "spectral_primary_barrier": PHASE_TRANSITION_PRIMARY,
            "spectral_secondary_threshold": PHASE_TRANSITION_SECONDARY,
        }
