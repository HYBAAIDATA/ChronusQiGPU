# hamiltonian.py
# Chronos GPU -- Hamiltonian Library v2.0 (audit fix, 3 Aug 2026)
#
# Fixes vs the original top-level hamiltonian_library.py v1.0:
#   - Removed all calls to the unseeded global np.random RNG. Previously
#     geometry_to_cost / material_to_resonance / light_to_driving called
#     np.random.randn() directly, which made the Hamiltonian -- and every
#     downstream energy/frame result -- non-deterministic from run to run
#     even at a fixed evolution seed. Confirmed by running the original demo
#     three times: energies came back -1.060671 / -1.169363 / -1.144699.
#   - Face geometry is now a deterministic function of n_faces (manifold.py
#     fibonacci_sphere) instead of random noise.

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from .manifold import M32Manifold


@dataclass
class HamiltonianTerms:
    cost_matrices: List[np.ndarray]
    mixer_matrix: np.ndarray
    resonance_weights: np.ndarray
    total_hamiltonian: np.ndarray


class HamiltonianLibrary:
    def __init__(self, n_faces: int = 32, adjacency: Optional[np.ndarray] = None, mixing_strength: float = 1.0):
        self.n = n_faces
        manifold = M32Manifold(n_faces)
        self.face_positions = manifold.face_positions
        # Real face-to-face coupling (angular-threshold adjacency), not an
        # identity placeholder. Without this, the Hamiltonian built below is
        # purely diagonal, its ground state trivially collapses onto a
        # single face, and the rendered frame ends up effectively
        # single-colored -- confirmed by an early test run of this fix pass.
        self.adjacency = adjacency if adjacency is not None else manifold.adjacency
        self.mixing_strength = mixing_strength

    def geometry_to_cost(self, geometry: Dict) -> np.ndarray:
        center = np.array(geometry.get("center", [0, 0, 0]), dtype=np.float64)
        radius = float(geometry.get("radius", 1.0))
        face_centers = self.face_positions * radius
        distances = np.linalg.norm(face_centers - center, axis=1)
        return -np.diag(distances)

    def material_to_resonance(self, material: Dict) -> np.ndarray:
        dielectric = material.get("dielectric", 1.5)
        absorption = material.get("absorption", 0.001)
        base = np.full(self.n, dielectric * 0.3)
        # Deterministic structured variation across faces (golden-angle
        # phase), replacing the previous unseeded np.random.randn jitter.
        phase = np.arange(self.n) * (np.pi * (3.0 - np.sqrt(5.0)))
        resonance = base + absorption * np.sin(phase) * 0.1
        return np.clip(resonance, 0.0, 1.0)

    def light_to_driving(self, light: Dict) -> np.ndarray:
        intensity = light.get("intensity", 1.0)
        direction = np.array(light.get("direction", [1, 1, 1]), dtype=np.float64)
        norm = np.linalg.norm(direction)
        if norm > 0:
            direction = direction / norm
        projections = self.face_positions @ direction
        return intensity * np.diag(projections)

    def build(self, scene_objects: List[Dict], lights: List[Dict]) -> HamiltonianTerms:
        cost_matrices = []
        resonance_list = []
        for obj in scene_objects:
            cost = self.geometry_to_cost(obj["geometry"])
            res = self.material_to_resonance(obj["material"])
            cost_matrices.append(cost)
            resonance_list.append(res)
        for light in lights:
            driving = self.light_to_driving(light)
            cost_matrices.append(driving)
        resonance_weights = np.mean(resonance_list, axis=0) if resonance_list else np.full(self.n, 0.5)
        # Off-diagonal transverse-field-style mixer built from real manifold
        # adjacency (geometric neighbors), scaled to be comparable in
        # magnitude to the cost terms so it actually competes during
        # diagonalization instead of being a no-op (as np.eye(n) was).
        mixer = -self.mixing_strength * self.adjacency
        total = sum(cost_matrices) if cost_matrices else np.zeros((self.n, self.n))
        total = total + mixer
        return HamiltonianTerms(
            cost_matrices=cost_matrices + [mixer],
            mixer_matrix=mixer,
            resonance_weights=resonance_weights,
            total_hamiltonian=total,
        )
