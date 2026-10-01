"""Modern QAOA with Egger warm-start, multi-angle, and RQAOA.

Egger et al. 2020: theta_i = 2 * arcsin(sqrt(p_i)) rotates the initial
superposition to bias towards the classical relaxation solution p_i in [0, 1].
"""

from __future__ import annotations
import numpy as np
from typing import Any, Callable, Dict, List, Optional, Tuple


def egger_warm_start_angles(p: np.ndarray) -> np.ndarray:
    """Warm-start rotation angle per qubit: theta_i = 2*arcsin(sqrt(p_i))."""
    p_clip = np.clip(p.astype(float), 0.0, 1.0)
    return 2.0 * np.arcsin(np.sqrt(p_clip))


def multi_angle_qaoa_params(num_edges: int, num_nodes: int, depth: int) -> Dict[str, np.ndarray]:
    """Multi-angle QAOA (ma-QAOA): per-edge gamma, per-node beta at each depth."""
    return {
        "gamma": np.zeros((depth, num_edges)),
        "beta": np.zeros((depth, num_nodes)),
    }


class ModernQAOA:
    def __init__(self, num_qubits: int, max_depth: int = 10) -> None:
        self.num_qubits = num_qubits
        self.max_depth = max_depth

    def adaptive_depth(self, problem_size: int, problem_structure: Dict[str, Any]) -> int:
        connectivity = problem_structure.get("connectivity", "dense")
        constraint_ratio = float(problem_structure.get("constraint_ratio", 0.5))
        base = max(1, int(np.log2(max(2, problem_size))))
        if connectivity == "sparse":
            base = int(base * 1.5)
        elif connectivity == "dense":
            base = int(base * 0.8)
        base = max(1, int(base * (1.0 + constraint_ratio)))
        return min(base, self.max_depth)

    def constraint_gate_recipe(self, constraints: List[Dict[str, Any]]) -> List[str]:
        recipe: List[str] = []
        for c in constraints:
            kind = c.get("type", "linear")
            if kind == "linear":
                recipe.extend(["RY", "CNOT"])
            elif kind == "quadratic":
                recipe.extend(["RY", "RZ", "CNOT", "CNOT"])
            elif kind == "higher_order":
                recipe.extend(["RY", "RZ", "CNOT"] * 3)
        return recipe

    def optimize(
        self,
        cost_fn: Callable[[np.ndarray, np.ndarray], float],
        classical_solution: Optional[np.ndarray] = None,
        problem_structure: Optional[Dict[str, Any]] = None,
        max_iter: int = 100,
    ) -> Dict[str, Any]:
        depth = self.adaptive_depth(self.num_qubits, problem_structure or {})
        if classical_solution is not None:
            init_beta = egger_warm_start_angles(np.asarray(classical_solution))
            beta0 = np.tile(init_beta.mean(), depth)
            gamma0 = np.full(depth, np.pi / 4)
        else:
            rng = np.random.default_rng(0)
            beta0 = rng.uniform(0.0, np.pi, depth)
            gamma0 = rng.uniform(0.0, 2 * np.pi, depth)

        # Nelder-Mead style hill climb (no scipy dependency).
        params = np.concatenate([beta0, gamma0])
        best = float(cost_fn(params[:depth], params[depth:]))
        step = 0.2
        for _ in range(max_iter):
            improved = False
            for i in range(len(params)):
                for s in (+step, -step):
                    trial = params.copy()
                    trial[i] += s
                    val = float(cost_fn(trial[:depth], trial[depth:]))
                    if val < best - 1e-9:
                        best = val
                        params = trial
                        improved = True
                        break
                if improved:
                    break
            if not improved:
                step *= 0.5
                if step < 1e-4:
                    break
        return {
            "optimal_beta": params[:depth],
            "optimal_gamma": params[depth:],
            "optimal_cost": best,
            "optimal_depth": depth,
        }

    def recursive_qaoa_eliminate(self, corr: np.ndarray) -> Tuple[int, int, int]:
        """RQAOA: eliminate the variable pair with largest |<Z_i Z_j>| correlation.

        Returns (i, j, sign) where sign = +/- 1 indicates the elimination direction.
        """
        C = np.asarray(corr, dtype=float)
        n = C.shape[0]
        assert C.shape == (n, n)
        best = (0, 1, 1)
        best_abs = -1.0
        for i in range(n):
            for j in range(i + 1, n):
                a = abs(C[i, j])
                if a > best_abs:
                    best_abs = a
                    best = (i, j, 1 if C[i, j] >= 0 else -1)
        return best
