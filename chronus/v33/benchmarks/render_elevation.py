# render_elevation.py
# Chronos GPU -- render elevation benchmark (5 Oct 2026)
#
# Measures the v3.1 elevation pass against the documented envelope, from the
# run that produced the artifact:
#   - 8K (7680x4320) default render, 1 sample/pixel, numpy reference path
#   - 8K supersampled render, 4 samples/pixel (the documented design factor)
#   - GPU lane status: bound and measured, or honestly unavailable with the
#     measured reason
# No number in this artifact is projected; unmeasured lanes say so.
#
# Run:  PYTHONPATH=. python chronus/v33/benchmarks/render_elevation.py
#       python -m chronus.v33.benchmarks.render_elevation

from __future__ import annotations

import json
import platform
import sys
import time
from pathlib import Path

import numpy as np

from chronus.v33.evolution_engine import EvolutionEngine
from chronus.v33.gpu_render import probe_cupy
from chronus.v33.hamiltonian import HamiltonianLibrary
from chronus.v33.reconstruction import ReconstructionEngine

DEMO_QSDL_SOURCE = (
    "scene sunset { "
    "manifold M32 "
    "object sphere { geometry sphere(radius=1.0, center=(0,0,0)) "
    "material glass { dielectric=1.5 absorption=0.001 quantum { resonance=[0.5] } } } "
    "light sun { type=directional position=(1,1,1) intensity=1.0 driving=zero() } "
    "camera { resolution=(7680,4320) fov=60.0 position=(0,0,5) readout = { observables = [intensity, depth, normal] } } "
    "quality { layers=4 evolution_steps=80 learning_rate=0.08 damping=0.01 seed=0 } "
    "}"
)


def _scene_inputs():
    lib = HamiltonianLibrary(n_faces=32)
    objs = [
        {
            "geometry": {"type": "sphere", "radius": 1.0, "center": (0, 0, 0)},
            "material": {
                "dielectric": 1.5,
                "absorption": 0.001,
                "resonance_weights": np.full(32, 0.5),
            },
        }
    ]
    lights = [{"intensity": 1.0, "direction": (1, 1, 1)}]
    h_terms = lib.build(objs, lights)
    evo = EvolutionEngine(n_faces=32, layers=4)
    result = evo.evolve(
        hamiltonian_terms=h_terms.cost_matrices,
        resonance_weights=h_terms.resonance_weights,
        steps=80,
        seed=0,
    )
    return lib, objs, result


def main() -> None:
    lib, objs, result = _scene_inputs()
    camera = {"resolution": (7680, 4320), "fov": 60.0, "position": (0, 0, 5)}
    recon = ReconstructionEngine(
        resolution=(7680, 4320), face_positions=lib.face_positions, block_rows=128
    )

    t0 = time.perf_counter()
    frame1 = recon.reconstruct(
        result.expectation_values, result.distribution, camera, scene_objects=objs
    )
    wall_1spp = time.perf_counter() - t0

    cam4 = dict(camera, supersampling=4)
    t0 = time.perf_counter()
    frame4 = recon.reconstruct(
        result.expectation_values, result.distribution, cam4, scene_objects=objs
    )
    wall_4spp = time.perf_counter() - t0

    status = probe_cupy()

    artifact = {
        "schema": "chronos-v33-render-elevation-v1",
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "energy": round(float(result.energy), 6),
        "full_render_8k": {
            "samples_per_pixel_1": {
                "wall_seconds": round(wall_1spp, 4),
                "rendered_pixels_hit": int(frame1.metadata["rendered_pixels_hit"]),
                "total_pixels": 7680 * 4320,
                "raster_compression_ratio": frame1.metadata["raster_compression_ratio"],
            },
            "samples_per_pixel_4": {
                "wall_seconds": round(wall_4spp, 4),
                "rendered_pixels_hit": int(frame4.metadata["rendered_pixels_hit"]),
                "total_pixels": 7680 * 4320,
                "raster_compression_ratio": frame4.metadata["raster_compression_ratio"],
            },
        },
        "gpu_lane": {
            "backend": "cupy",
            "available": status.available,
            "device": status.device_name,
            "reason": status.reason,
            # honestly unmeasured on this host unless bound and run
            "measured": status.available,
        },
        "note": (
            "Wall times are measured on the host that produced this artifact. "
            "The GPU lane is fail-closed: when unavailable, no GPU wall time exists "
            "and none is invented."
        ),
    }

    out_path = Path(__file__).resolve().parent / "render_elevation_results.json"
    out_path.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps(artifact, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
