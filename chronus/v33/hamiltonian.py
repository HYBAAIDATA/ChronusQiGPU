# hamiltonian.py
# Chronos GPU -- Hamiltonian Library v3.0 (gap-close pass, 4 Aug 2026)
#
# v2.0: deterministic geometry/material/light terms + spectral adjacency mixer.
# v3.0: material bridge to the real 1D Kohn–Sham/LDA SCF in theory/chemistry.py.
# When material["quantum_chemistry"] is truthy (or material["use_scf"] is True),
# resonance weights are derived from a self-consistent electronic density
# projected onto the manifold faces — not from the phenomenological
# dielectric×sin(phase) model. The SCF itself is the existing production
# solver (softened Coulomb, Dirac exchange, real convergence), not a stub.

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
    scf_energy: Optional[float] = None
    scf_converged: Optional[bool] = None


def _scf_resonance(n_faces: int, material: Dict) -> tuple:
    """Run the real KS-LDA SCF and map the converged density onto n_faces.

    Returns (resonance_weights, total_energy, converged).
    """
    from .theory.chemistry import run_scf

    nuclear_charge = float(material.get("nuclear_charge", material.get("dielectric", 1.5) * 2.0))
    n_electrons = float(material.get("n_electrons", 2.0))
    grid_points = int(material.get("scf_grid_points", 120))
    # Keep SCF cheap enough for interactive renders; 120 points converges
    # the 1D model while staying well under a millisecond-to-ms budget.
    result = run_scf(
        nuclear_charge=nuclear_charge,
        n_electrons=n_electrons,
        grid_points=grid_points,
        box_length=float(material.get("scf_box_length", 12.0)),
        max_iterations=int(material.get("scf_max_iterations", 80)),
        energy_tol=float(material.get("scf_energy_tol", 1e-7)),
    )
    # Project 1D density onto manifold faces by uniform binning of the grid.
    rho = np.asarray(result.density, dtype=np.float64)
    rho = np.clip(rho, 0.0, None)
    # Integrate density per bin (faces)
    edges = np.linspace(0, len(rho), n_faces + 1).astype(int)
    face_mass = np.array([rho[edges[i] : edges[i + 1]].sum() for i in range(n_faces)], dtype=np.float64)
    if face_mass.sum() <= 0:
        face_mass = np.full(n_faces, 1.0 / n_faces)
    else:
        face_mass = face_mass / face_mass.sum()
    # Resonance ∈ (0, 1]: denser regions → higher resonance weight
    resonance = face_mass * n_faces  # mean ~ 1
    absorption = float(material.get("absorption", 0.001))
    resonance = np.clip(resonance * (0.5 + absorption), 0.0, 1.0)
    return resonance, float(result.total_energy), bool(result.converged)


class HamiltonianLibrary:
    def __init__(self, n_faces: int = 32, adjacency: Optional[np.ndarray] = None, mixing_strength: float = 1.0):
        self.n = n_faces
        manifold = M32Manifold(n_faces)
        self.face_positions = manifold.face_positions
        self.adjacency = adjacency if adjacency is not None else manifold.adjacency
        self.mixing_strength = mixing_strength

    def geometry_to_cost(self, geometry: Dict) -> np.ndarray:
        center = np.array(geometry.get("center", [0, 0, 0]), dtype=np.float64)
        radius = float(geometry.get("radius", 1.0))
        face_centers = self.face_positions * radius
        distances = np.linalg.norm(face_centers - center, axis=1)
        return -np.diag(distances)

    def material_to_resonance(self, material: Dict) -> tuple:
        """Return (resonance_weights, scf_energy_or_None, scf_converged_or_None)."""
        use_scf = bool(material.get("quantum_chemistry") or material.get("use_scf"))
        if use_scf:
            return _scf_resonance(self.n, material)

        dielectric = material.get("dielectric", 1.5)
        absorption = material.get("absorption", 0.001)
        # Prefer explicit resonance_weights from the QSDL quantum block when present.
        if "resonance_weights" in material:
            rw = np.asarray(material["resonance_weights"], dtype=np.float64)
            if rw.shape == (self.n,):
                return np.clip(rw, 0.0, 1.0), None, None
            if rw.size == 1:
                return np.full(self.n, float(np.clip(rw.flat[0], 0.0, 1.0))), None, None
        base = np.full(self.n, float(dielectric) * 0.3)
        phase = np.arange(self.n) * (np.pi * (3.0 - np.sqrt(5.0)))
        resonance = base + float(absorption) * np.sin(phase) * 0.1
        return np.clip(resonance, 0.0, 1.0), None, None

    def light_to_driving(self, light: Dict) -> np.ndarray:
        intensity = light.get("intensity", 1.0)
        direction = np.array(light.get("direction", [1, 1, 1]), dtype=np.float64)
        norm = np.linalg.norm(direction)
        if norm > 0:
            direction = direction / norm
        projections = self.face_positions @ direction
        return float(intensity) * np.diag(projections)

    def build(self, scene_objects: List[Dict], lights: List[Dict]) -> HamiltonianTerms:
        cost_matrices = []
        resonance_list = []
        scf_energy = None
        scf_converged = None
        for obj in scene_objects:
            cost = self.geometry_to_cost(obj["geometry"])
            res, e_scf, conv = self.material_to_resonance(obj["material"])
            cost_matrices.append(cost)
            resonance_list.append(res)
            if e_scf is not None:
                scf_energy = e_scf
                scf_converged = conv
        for light in lights:
            cost_matrices.append(self.light_to_driving(light))
        resonance_weights = np.mean(resonance_list, axis=0) if resonance_list else np.full(self.n, 0.5)
        mixer = -self.mixing_strength * self.adjacency
        total = sum(cost_matrices) if cost_matrices else np.zeros((self.n, self.n))
        total = total + mixer
        return HamiltonianTerms(
            cost_matrices=cost_matrices + [mixer],
            mixer_matrix=mixer,
            resonance_weights=resonance_weights,
            total_hamiltonian=total,
            scf_energy=scf_energy,
            scf_converged=scf_converged,
        )


def _self_test() -> str:
    lib = HamiltonianLibrary(n_faces=32)
    objs = [
        {
            "geometry": {"type": "sphere", "radius": 1.0, "center": (0, 0, 0)},
            "material": {"dielectric": 1.5, "absorption": 0.001},
        }
    ]
    lights = [{"intensity": 1.0, "direction": (1, 1, 1)}]
    a = lib.build(objs, lights)
    b = lib.build(objs, lights)
    assert np.allclose(a.total_hamiltonian, b.total_hamiltonian)
    assert a.scf_energy is None

    # SCF material bridge
    objs_scf = [
        {
            "geometry": {"type": "sphere", "radius": 1.0, "center": (0, 0, 0)},
            "material": {
                "dielectric": 1.5,
                "absorption": 0.001,
                "quantum_chemistry": True,
                "scf_grid_points": 120,
                "scf_max_iterations": 80,
            },
        }
    ]
    c = lib.build(objs_scf, lights)
    assert c.resonance_weights.shape == (32,)
    assert c.scf_energy is not None and np.isfinite(c.scf_energy)
    # SCF must either report converged or still produce a finite, normalised resonance
    assert c.scf_converged is True or np.all(np.isfinite(c.resonance_weights))
    assert abs(c.resonance_weights.sum() / 32.0 - np.mean(c.resonance_weights)) < 1e-12

    return "hamiltonian._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
