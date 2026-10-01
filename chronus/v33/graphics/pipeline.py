# pipeline.py -- Quantum graphics pipeline (wavefunction → pixel colour).
# Vertex transform is classical linear algebra; the quantum shader evaluates
# |ψ(face)|² via nearest-face lookup on the manifold — no GPU API required.

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..reconstruction import ReconstructionEngine, Frame8K


def quantum_shader(amplitude: complex) -> Tuple[float, float, float]:
    """Map a complex field sample to an RGB triple (Born intensity)."""
    i = float(abs(amplitude) ** 2)
    return (i, i, i)


@dataclass
class QuantumGraphicsPipeline:
    """Evaluate a manifold wavefunction through a pinhole camera.

    Internally reuses ReconstructionEngine for ray geometry; shades by
    projecting the complex state onto face amplitudes.
    """

    resolution: Tuple[int, int] = (160, 90)
    face_positions: Optional[np.ndarray] = None

    def render_state(
        self,
        state: np.ndarray,
        camera: Optional[Dict] = None,
        scene_objects: Optional[List[Dict]] = None,
    ) -> Frame8K:
        distribution = np.abs(np.asarray(state, dtype=complex)) ** 2
        distribution = distribution / (distribution.sum() + 1e-30)
        camera = camera or {"position": (0, 0, 5), "fov": 60.0, "resolution": self.resolution}
        objs = scene_objects or [
            {"geometry": {"type": "sphere", "radius": 1.0, "center": (0, 0, 0)}}
        ]
        recon = ReconstructionEngine(resolution=self.resolution, face_positions=self.face_positions)
        return recon.reconstruct(
            {"intensity": 1.0, "depth": float(np.mean(distribution)), "normal": float(np.std(distribution))},
            distribution,
            camera,
            scene_objects=objs,
        )

    def vertex_shader(self, vertex: np.ndarray, modelview: np.ndarray, projection: np.ndarray) -> np.ndarray:
        """Standard MVP transform: projection @ modelview @ vertex_h."""
        v = np.asarray(vertex, dtype=np.float64)
        if v.shape == (3,):
            v = np.array([v[0], v[1], v[2], 1.0])
        return projection @ modelview @ v


def _self_test() -> str:
    from ..manifold import M32Manifold

    m = M32Manifold(n=32)
    state = m.get_state()
    pipe = QuantumGraphicsPipeline(resolution=(64, 36), face_positions=m.face_positions)
    frame = pipe.render_state(state)
    assert frame.rgb.shape == (36, 64, 3)
    assert int(np.count_nonzero(frame.depth)) > 0

    mvp_v = pipe.vertex_shader(
        np.array([1.0, 0.0, 0.0]),
        np.eye(4),
        np.eye(4),
    )
    assert mvp_v.shape == (4,)
    assert abs(quantum_shader(1 + 0j)[0] - 1.0) < 1e-12
    return "graphics.pipeline._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
