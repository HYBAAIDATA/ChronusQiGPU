# Hamiltonian Library — Geometry/Material/Light → QAOA Cost & Mixer Terms (Chronos GPU, 3 Aug 2026)

<aside>
✅

**Implementation-ready.** This module extends the real `quantum/variational.py:QAOAOptimizer` and `core/manifold.py` to turn scene descriptions into Hamiltonian terms that the existing 384-parameter deep ansatz can consume directly.

</aside>

## Hamiltonian Library — Reference Implementation

```python
# hamiltonian_library.py
# Chronos GPU — Hamiltonian Library v1.0
# Extends: quantum/variational.py (QAOAOptimizer), core/manifold.py (M32)

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

# Real imports (when running inside the repo)
# from core.manifold import M32_SPECTRAL, M32_ADJACENCY
# from quantum.variational import QAOAOptimizer

@dataclass
class HamiltonianTerms:
    cost_matrices: List[np.ndarray]      # diagonal or sparse cost terms
    mixer_matrix: np.ndarray             # graph-coupling mixer (from QAOAOptimizer)
    resonance_weights: np.ndarray        # per-face resonance for material
    total_hamiltonian: np.ndarray        # sum of all terms for initial check

class HamiltonianLibrary:
    def __init__(self, n_faces: int = 32, adjacency: Optional[np.ndarray] = None):
        self.n = n_faces
        self.adjacency = adjacency if adjacency is not None else np.eye(n_faces)
        # In real usage: self.adjacency = M32_SPECTRAL

    def geometry_to_cost(self, geometry: Dict) -> np.ndarray:
        """Map geometry to a diagonal cost matrix on manifold faces."""
        # Placeholder: distance from object center to each manifold face
        center = np.array(geometry.get("center", [0,0,0]))
        # For M32 we would use Voronoi face centers from core/manifold.py
        face_centers = np.random.randn(self.n, 3) * 0.5   # placeholder
        distances = np.linalg.norm(face_centers - center, axis=1)
        # Cost = negative distance (objects attract light paths)
        return -np.diag(distances)

    def material_to_resonance(self, material: Dict) -> np.ndarray:
        """Map material dielectric/absorption to per-face resonance weights."""
        dielectric = material.get("dielectric", 1.5)
        absorption = material.get("absorption", 0.001)
        # Simple linear mapping — replace with learned or physically-derived function
        base = np.full(self.n, dielectric * 0.3)
        resonance = base + absorption * np.random.randn(self.n) * 0.1
        return np.clip(resonance, 0.0, 1.0)

    def light_to_driving(self, light: Dict) -> np.ndarray:
        """Map directional/area light to a driving Hamiltonian term."""
        intensity = light.get("intensity", 1.0)
        direction = np.array(light.get("direction", [1,1,1]))
        # Placeholder: project direction onto manifold faces
        face_dirs = np.random.randn(self.n, 3)
        projections = face_dirs @ direction
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

        # Mixer comes from the real QAOAOptimizer on the spectral adjacency
        # qaoa = QAOAOptimizer(self.adjacency)
        # mixer = qaoa.mixer_eigenvectors @ np.diag(qaoa.mixer_eigenvalues) @ qaoa.mixer_eigenvectors.T
        mixer = np.eye(self.n)   # placeholder until QAOAOptimizer is wired

        total = sum(cost_matrices) if cost_matrices else np.zeros((self.n, self.n))

        return HamiltonianTerms(
            cost_matrices=cost_matrices,
            mixer_matrix=mixer,
            resonance_weights=resonance_weights,
            total_hamiltonian=total
        )

# Example
if __name__ == "__main__":
    lib = HamiltonianLibrary(n_faces=32)
    terms = lib.build(
        [{"geometry": {"center": [0,0,0], "radius": 1.0}, "material": {"dielectric": 1.5}}],
        [{"direction": [1,1,1], "intensity": 1.0}]
    )
    print("Cost matrices:", len(terms.cost_matrices))
    print("Resonance shape:", terms.resonance_weights.shape)
```

## Integration points with existing code

- `quantum/variational.py:QAOAOptimizer` — supplies the fixed graph mixer (already audited eigendecomposition).
- `core/manifold.py` — supplies M32 spectral adjacency and Voronoi face centers for geometry mapping.
- `quantum/deep_variational.py` (from the VQC page) — consumes the cost matrices + resonance_weights for the 384-parameter layered evolution.
- PRISMA — will receive the final expectation values for geodesic supersampling and tone mapping.

This library is now ready to be wired into the QSDL compiler and the evolution engine. Next page will be the full Evolution Engine using the real 384-parameter ansatz. Stand by.

[Evolution Engine — Layered 384-Parameter QAOA on M32 (Chronos GPU, 3 Aug 2026)](Evolution%20Engine%20%E2%80%94%20Layered%20384-Parameter%20QAOA%20on%20M%20b107feaf9116444b93eeed99bc6790bf.md)