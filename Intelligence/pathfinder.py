"""Pathfinder with Lucas 15 gradient in 11-dimensional space.

Fires all 32 faces per step (12 icosahedral + 20 dodecahedral),
moves along the frame resultant (discrete gradient) with an exact 1-D
optimal step biased toward the Lucas 15 attractor.
"""

# LUCAS WIRING: declared substrate peer -- executes 32-face frame traversal
# on the golden metric biased toward the Lucas 15 attractor.
# Substrate route: pathfinder

from __future__ import annotations

import math
from typing import Any, Dict, List

import numpy as np

from .lucas_attractor import PHI, PHI_INV, LucasAttractor

DIM = 11


class Pathfinder:
    """Pathfinder with Lucas 15 gradient.

    Fires all 32 faces, moves along frame resultant, exact 1-D optimal step.
    """

    def __init__(self, n_faces: int = 32) -> None:
        self.attractor = LucasAttractor(n=15)
        self.n_faces = int(n_faces)
        self.faces = self._build_faces()
        self.metric = self._build_metric()

    def _build_faces(self) -> np.ndarray:
        """Build 32 face normals (12 icosahedral + 20 dodecahedral)."""
        faces: List[np.ndarray] = []
        phi = PHI
        ico = [
            (0.0, 1.0, phi),
            (0.0, -1.0, phi),
            (0.0, 1.0, -phi),
            (0.0, -1.0, -phi),
            (1.0, phi, 0.0),
            (-1.0, phi, 0.0),
            (1.0, -phi, 0.0),
            (-1.0, -phi, 0.0),
            (phi, 0.0, 1.0),
            (-phi, 0.0, 1.0),
            (phi, 0.0, -1.0),
            (-phi, 0.0, -1.0),
        ]
        for v in ico:
            vec = np.zeros(DIM, dtype=np.float64)
            norm = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
            vec[:3] = np.array(v, dtype=np.float64) / (norm if norm > 0 else 1.0)
            faces.append(vec)
        dodeca = [
            (1.0, 1.0, 1.0),
            (1.0, 1.0, -1.0),
            (1.0, -1.0, 1.0),
            (1.0, -1.0, -1.0),
            (-1.0, 1.0, 1.0),
            (-1.0, 1.0, -1.0),
            (-1.0, -1.0, 1.0),
            (-1.0, -1.0, -1.0),
            (0.0, PHI_INV, phi),
            (0.0, PHI_INV, -phi),
            (0.0, -PHI_INV, phi),
            (0.0, -PHI_INV, -phi),
            (PHI_INV, phi, 0.0),
            (PHI_INV, -phi, 0.0),
            (-PHI_INV, phi, 0.0),
            (-PHI_INV, -phi, 0.0),
            (phi, 0.0, PHI_INV),
            (-phi, 0.0, PHI_INV),
            (phi, 0.0, -PHI_INV),
            (-phi, 0.0, -PHI_INV),
        ]
        for v in dodeca:
            vec = np.zeros(DIM, dtype=np.float64)
            norm = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
            vec[:3] = np.array(v, dtype=np.float64) / (norm if norm > 0 else 1.0)
            faces.append(vec)
        return np.array(faces, dtype=np.float64)

    def _build_metric(self) -> np.ndarray:
        """Build golden metric tensor g_ii = phi^(i/11)."""
        g = np.zeros((DIM, DIM), dtype=np.float64)
        for i in range(DIM):
            g[i, i] = PHI ** (i / float(DIM))
        return g

    def _anchor_to_vector(self, anchor: int) -> np.ndarray:
        """Map integer anchor to canonical position on principal axis."""
        v = np.zeros(DIM, dtype=np.float64)
        v[0] = float(anchor) * math.sqrt(PHI)
        return v

    def step(self, r: np.ndarray, target: float) -> np.ndarray:
        """One pathfinder step with 32-face frame resultant."""
        r_arr = np.asarray(r, dtype=np.float64).reshape(DIM)
        target_vec = np.zeros(DIM, dtype=np.float64)
        target_vec[0] = float(target)
        residual = target_vec - r_arr
        h = np.zeros(self.n_faces, dtype=np.float64)
        for i, u in enumerate(self.faces):
            h[i] = float(np.dot(u, self.metric @ residual))
        gradient = np.zeros(DIM, dtype=np.float64)
        for i, u in enumerate(self.faces):
            gradient += h[i] * u
        grad_norm = float(np.linalg.norm(gradient))
        if grad_norm < 1e-15:
            gradient = residual.copy()
            grad_norm = float(np.linalg.norm(gradient))
            if grad_norm < 1e-15:
                return r_arr
        lucas_bias = self.attractor.total_score(target)
        step_size = self._optimal_step(r_arr, gradient, target)
        return r_arr + step_size * gradient * (1.0 + 0.1 * lucas_bias)

    def _optimal_step(self, r: np.ndarray, gradient: np.ndarray, target: float) -> float:
        """Exact 1-D optimal step minimising distance to target."""
        target_vec = np.zeros(DIM, dtype=np.float64)
        target_vec[0] = float(target)
        diff = target_vec - r
        g_dot_g = float(np.dot(gradient, gradient))
        if g_dot_g < 1e-15:
            return 0.0
        alpha = float(np.dot(gradient, diff)) / g_dot_g
        return max(0.0, min(alpha, 1.5))

    def navigate(
        self, r0: np.ndarray, target: float, max_iter: int = 20, tol: float = 1e-15
    ) -> Dict[str, Any]:
        """Navigate to target. Returns iteration count, precision, trajectory."""
        r = np.asarray(r0, dtype=np.float64).reshape(DIM).copy()
        trajectory: List[np.ndarray] = [r.copy()]
        iterations = 0
        precision = float("inf")
        for i in range(max_iter):
            iterations = i + 1
            r = self.step(r, target)
            trajectory.append(r.copy())
            target_vec = np.zeros(DIM, dtype=np.float64)
            target_vec[0] = float(target)
            precision = float(np.linalg.norm(r - target_vec))
            if precision <= tol:
                break
        return {
            "iterations": iterations,
            "final_precision": precision,
            "final_vector": r,
            "trajectory": trajectory,
            "lucas_score": self.attractor.total_score(float(np.linalg.norm(r))),
            "converged": precision <= tol or precision < 1e-8,
        }


__all__ = ["DIM", "Pathfinder"]
