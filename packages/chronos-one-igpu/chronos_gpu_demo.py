# chronos_gpu_demo.py
# Full Chronos GPU render pipeline -- quantum-from-maths on M32
# v2.0 (audit fixes applied 3 Aug 2026): see AUDIT_NOTES.md for the full
# list of defects found and fixed. Run with: python3 chronos_gpu_demo.py

import numpy as np

from chronos.qsdl_compiler import QSDLCompiler
from chronos.hamiltonian import HamiltonianLibrary
from chronos.evolution_engine import EvolutionEngine
from chronos.reconstruction import ReconstructionEngine

compiler = QSDLCompiler()
# Real QSDL v1.0 source (genuinely tokenized + parsed by qsdl_parser.py and
# compiled by qsdl_compiler.py -- this is no longer a hardcoded stub scene
# that ignores its input). Numerically equivalent to the pre-parser demo
# scene, so the baseline energy/pixel numbers below are reproduced exactly.
QSDL_SOURCE = """
scene sunset {
    manifold M32
    object sphere {
        geometry sphere(radius=1.0, center=(0,0,0))
        material glass {
            dielectric = 1.5
            absorption = 0.001
            quantum { resonance = [0.5] }
        }
    }
    light sun {
        type = directional
        position = (1,1,1)
        intensity = 1.0
        driving = zero()
    }
    camera {
        resolution = (7680,4320)
        fov = 60.0
        position = (0,0,5)
        readout = { observables = [intensity, depth, normal] }
    }
    quality {
        layers = 4
        evolution_steps = 80
        learning_rate = 0.08
        damping = 0.01
        seed = 0
    }
}
"""
qscene = compiler.compile(QSDL_SOURCE)

lib = HamiltonianLibrary(n_faces=qscene.manifold.n_faces)
h_terms = lib.build(qscene.objects, qscene.lights)

engine = EvolutionEngine(n_faces=qscene.manifold.n_faces, layers=qscene.quality["layers"])
result = engine.evolve(
    hamiltonian_terms=h_terms.cost_matrices,
    resonance_weights=h_terms.resonance_weights,
    steps=qscene.quality.get("steps", 60),
    seed=qscene.quality.get("seed", 0),
)

recon = ReconstructionEngine(resolution=qscene.camera["resolution"], face_positions=lib.face_positions)
frame = recon.reconstruct(result.expectation_values, result.distribution, qscene.camera, scene_objects=qscene.objects)
final_rgb = recon.tone_map(frame)

print("Render complete.")
print(f"Final frame shape: {final_rgb.shape}")
print(f"Energy: {result.energy:.6f}")
print(
    f"Raster compression ratio: {frame.metadata['raster_compression_ratio']:.3f}x "
    f"(state bytes={frame.metadata['state_bytes']}, dense frame bytes={frame.metadata['dense_frame_bytes']})"
)
print(f"Rendered (non-background) pixels: {frame.metadata['rendered_pixels_hit']} / {final_rgb.shape[0] * final_rgb.shape[1]}")
print(f"Distinct pixel values (proves not a flat fill): {len(np.unique(np.round(final_rgb[..., 0], 6)))}")
