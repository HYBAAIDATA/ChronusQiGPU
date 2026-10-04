# qsdl_compiler.py
# Chronos GPU -- QSDL Compiler v2.0 (audit fix, 3 Aug 2026)
#
# Fix vs v1.0: src/chronos's own stub referenced np.eye(32) without ever
# importing numpy (a bug -- it could not have run), and didn't build a real
# scene at all. The top-level qsdl_compiler.py had a hard SyntaxError
# ("qsd l_source" instead of "qsdl_source") that prevented the whole demo
# pipeline from importing. Both are fixed here in one real implementation.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from .manifold import M32Manifold


@dataclass
class ManifoldConfig:
    name: str = "M32"
    n_faces: int = 32
    adjacency_threshold: float = 0.70


@dataclass
class QScene:
    manifold: ManifoldConfig
    objects: List[Dict] = field(default_factory=list)
    lights: List[Dict] = field(default_factory=list)
    camera: Dict = field(default_factory=dict)
    hamiltonian_terms: List[np.ndarray] = field(default_factory=list)
    readout_observables: List[str] = field(default_factory=list)
    quality: Dict = field(default_factory=dict)


class QSDLCompiler:
    def __init__(self, manifold: Optional[ManifoldConfig] = None):
        self.manifold = manifold or ManifoldConfig()

    def compile(self, qsdl_source: str) -> QScene:
        # NOTE: this does not actually parse the QSDL grammar from
        # notion-39 (QSDL Specification v1.0); it returns the same fixed demo
        # scene as the original code regardless of qsdl_source content. A
        # real BNF-grammar parser is future scope, not something this audit
        # pass added.
        scene = QScene(manifold=self.manifold)
        scene.objects.append({
            "name": "sphere_0",
            "geometry": {"type": "sphere", "radius": 1.0, "center": (0, 0, 0)},
            "material": {
                "dielectric": 1.5,
                "absorption": 0.001,
                "resonance_weights": np.full(self.manifold.n_faces, 0.5),
            },
            "transform": np.eye(4),
        })
        scene.lights.append({
            "name": "sun",
            "type": "directional",
            "direction": (1, 1, 1),
            "intensity": 1.0,
            "driving_term": np.zeros((self.manifold.n_faces, self.manifold.n_faces)),
        })
        scene.camera = {
            "resolution": (7680, 4320),
            "fov": 60.0,
            "position": (0, 0, 5),
            "readout": ["intensity", "depth", "normal"],
        }
        scene.quality = {
            "layers": 4,
            "steps": 80,
            "learning_rate": 0.08,
            "damping": 1e-2,
            "seed": 0,
        }
        scene.hamiltonian_terms = self._build_initial_hamiltonian(scene)
        return scene

    def _build_initial_hamiltonian(self, scene: QScene) -> List[np.ndarray]:
        terms = []
        for obj in scene.objects:
            res = obj["material"]["resonance_weights"]
            cost = -np.diag(res)
            terms.append(cost)
        for light in scene.lights:
            terms.append(light["driving_term"])
        return terms
