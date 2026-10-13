# engine.py
# Chronos GPU -- ChronosEngine orchestrator v2.0 (audit fix, 3 Aug 2026)
#
# Fix vs v1.0:
#   render() hardcoded `energy = 0.123456` ("# Placeholder for full
#   pipeline") and returned a bare dict, which does not even match this
#   package's own README quickstart (`result.energy`, an attribute access
#   that would fail on a dict). This exact 0.123456 constant also showed up,
#   unchanged, in a Notion page's "smoke test results" -- strong evidence
#   that reported test was never actually produced by running this pipeline.
#
#   v2.0 runs the real, wired pipeline (compile -> Hamiltonian -> evolve ->
#   reconstruct) and returns a real object with an `.energy` attribute
#   matching the README's documented usage.

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np

from .qsdl_compiler import QSDLCompiler, ManifoldConfig
from .hamiltonian import HamiltonianLibrary
from .evolution_engine import EvolutionEngine
from .reconstruction import ReconstructionEngine
from .lucas_runtime import LucasRuntime


@dataclass
class RenderOutput:
    energy: float
    scene: str
    frame_shape: tuple
    raster_compression_ratio: float
    rendered_pixels_hit: int
    total_pixels: int
    distribution: np.ndarray
    lucas_records: int
    lucas_backend: str


class ChronosEngine:
    def __init__(self, n_faces: int = 32, layers: int = 4):
        self.n = n_faces
        self.layers = layers
        self.lucas_runtime = LucasRuntime()

    def render(self, scene: str = "default") -> RenderOutput:
        compiler = QSDLCompiler(ManifoldConfig(n_faces=self.n))
        qscene = compiler.compile(scene)

        # Lucas records provide the exact, certificate-bearing face/rung index
        # contract. Numeric rendering remains a deliberately separate projection.
        lucas_records = self.lucas_runtime.evaluate(range(qscene.manifold.n_faces))

        lib = HamiltonianLibrary(n_faces=qscene.manifold.n_faces)
        h_terms = lib.build(qscene.objects, qscene.lights)

        engine = EvolutionEngine(n_faces=qscene.manifold.n_faces, layers=self.layers)
        result = engine.evolve(
            hamiltonian_terms=h_terms.cost_matrices,
            resonance_weights=h_terms.resonance_weights,
            steps=qscene.quality.get("steps", 60),
            seed=qscene.quality.get("seed", 0),
        )

        recon = ReconstructionEngine(resolution=qscene.camera["resolution"], face_positions=lib.face_positions)
        frame = recon.reconstruct(
            result.expectation_values, result.distribution, qscene.camera, scene_objects=qscene.objects
        )
        final_rgb = recon.tone_map(frame)
        h, w, _ = final_rgb.shape

        return RenderOutput(
            energy=result.energy,
            scene=scene,
            frame_shape=final_rgb.shape,
            raster_compression_ratio=frame.metadata["raster_compression_ratio"],
            rendered_pixels_hit=frame.metadata["rendered_pixels_hit"],
            total_pixels=h * w,
            distribution=result.distribution,
            lucas_records=len(lucas_records),
            lucas_backend=self.lucas_runtime.capabilities.name,
        )

    def evolve(self, hamiltonian: np.ndarray) -> np.ndarray:
        # v1.0 returned np.random.randn(...) unrelated to `hamiltonian`.
        # v2.0 actually diagonalizes it and returns the ground state.
        hamiltonian = (hamiltonian + hamiltonian.T) / 2.0
        eigvals, eigvecs = np.linalg.eigh(hamiltonian)
        state = eigvecs[:, 0].astype(complex)
        peak = int(np.argmax(np.abs(state)))
        if state[peak].real < 0:
            state = -state
        return state
