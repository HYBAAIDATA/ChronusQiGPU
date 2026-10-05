# real_workloads.py
# Chronos GPU -- real-workload benchmark set (5 Oct 2026)
#
# "Real workload" means a full QSDL scene through the real pipeline
# (manifold -> Hamiltonian -> evolution -> ray-traced reconstruction),
# measured under the reproducibility protocol. The demo scene (one glass
# sphere, one directional light) remains as the continuity baseline; the
# new scenes exercise what the documents actually describe: multiple
# objects, multiple materials, multiple lights, and (from the v3.2
# composite elevation) real box and plane geometry with nearest-hit
# composition.
#
# Run:
#   PYTHONPATH=. python chronus/v33/benchmarks/real_workloads.py
#   python -m chronus.v33.benchmarks.real_workloads

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from chronus.v33.engine import ChronosEngine
from chronus.v33.benchmarks.protocol import (
    envelope,
    measure,
    nan_guard,
    write_artifact,
)

import json
from pathlib import Path


@dataclass(frozen=True)
class WorkloadSpec:
    name: str
    description: str
    qsdl_source: str
    resolution: Tuple[int, int]
    n_faces: int = 32
    layers: int = 4
    supersampling: int = 1
    repetitions: int = 1
    tags: Tuple[str, ...] = field(default_factory=tuple)


def _camera(resolution: Tuple[int, int], spp: int = 1) -> str:
    ss = "" if spp <= 1 else f" supersampling = {spp} "
    return (
        f"camera {{ resolution=({resolution[0]},{resolution[1]}) fov=60.0 "
        f"position=(0,0,5) readout = {{ observables = [intensity, depth, normal]{ss}}} }} "
    )


def _quality(steps: int = 80) -> str:
    return (
        f"quality {{ layers=4 evolution_steps={steps} learning_rate=0.08 "
        "damping=0.01 seed=0 } "
    )


DEMO_QSDL_SOURCE = (
    "scene sunset { "
    "manifold M32 "
    "object sphere { geometry sphere(radius=1.0, center=(0,0,0)) "
    "material glass { dielectric=1.5 absorption=0.001 quantum { resonance=[0.5] } } } "
    "light sun { type=directional position=(1,1,1) intensity=1.0 driving=zero() } "
    + _camera((7680, 4320))
    + _quality()
    + "}"
)


TWO_SPHERE_SOURCE = (
    "scene binary { "
    "manifold M32 "
    "object glass_sphere { geometry sphere(radius=1.0, center=(-1.4,0,0)) "
    "material glass { dielectric=1.5 absorption=0.001 quantum { resonance=[0.5] } } } "
    "object dense_sphere { geometry sphere(radius=0.8, center=(1.6,0,-0.5)) "
    "material ceramic { dielectric=2.2 absorption=0.02 quantum { resonance=[0.75] } } } "
    "light sun { type=directional position=(1,1,1) intensity=1.0 driving=zero() } "
    "light fill { type=point position=(-2,2,3) intensity=0.5 driving=zero() } "
    + _camera((7680, 4320))
    + _quality()
    + "}"
)


STUDIO_COMPOSITE_SOURCE = (
    "scene studio { "
    "manifold M32 "
    "object glass_sphere { geometry sphere(radius=1.0, center=(-1.2,0,0)) "
    "material glass { dielectric=1.5 absorption=0.001 quantum { resonance=[0.5] } } } "
    "object metal_box { geometry box(center=(1.2,0,0), extents=(0.8,0.8,0.8)) "
    "material metal { dielectric=2.4 absorption=0.01 quantum { resonance=[0.7] } } } "
    "object ground { geometry plane(normal=(0,1,0), offset=-1.5) "
    "material matte { dielectric=1.1 absorption=0.02 quantum { resonance=[0.3] } } } "
    "light sun { type=directional position=(1,1,1) intensity=1.0 driving=zero() } "
    "light fill { type=point position=(-2,2,3) intensity=0.5 driving=zero() } "
    + _camera((7680, 4320))
    + _quality()
    + "}"
)


GALLERY_SUPER_RES_SOURCE = STUDIO_COMPOSITE_SOURCE.replace(
    "observables = [intensity, depth, normal]",
    "observables = [intensity, depth, normal] supersampling = 4",
).replace("scene studio", "scene gallery", 1)


REAL_WORKLOADS: Tuple[WorkloadSpec, ...] = (
    WorkloadSpec(
        name="demo_sunset_sphere_8k",
        description=(
            "Continuity baseline: one glass sphere, one directional light, 8K. "
            "The validated v3.1 single-sphere path (bit-identical contract, "
            "hits 1,832,112 at 8K)."
        ),
        qsdl_source=DEMO_QSDL_SOURCE,
        resolution=(7680, 4320),
        tags=("baseline", "sphere", "8k"),
    ),
    WorkloadSpec(
        name="binary_two_sphere_8k",
        description=(
            "Real multi-object scene: two spheres with different materials "
            "and two lights, composed by nearest hit."
        ),
        qsdl_source=TWO_SPHERE_SOURCE,
        resolution=(7680, 4320),
        tags=("multi-object", "sphere", "8k"),
    ),
    WorkloadSpec(
        name="studio_composite_box_plane_8k",
        description=(
            "Real geometry spread: glass sphere + axis-aligned metal box + "
            "ground plane, two lights, nearest-hit composition (v3.2)."
        ),
        qsdl_source=STUDIO_COMPOSITE_SOURCE,
        resolution=(7680, 4320),
        tags=("multi-object", "box", "plane", "composite", "8k"),
    ),
    WorkloadSpec(
        name="gallery_composite_4spp_8k",
        description=(
            "The composite studio scene with real 4x supersampling -- the "
            "documented design factor, traced not asserted."
        ),
        qsdl_source=GALLERY_SUPER_RES_SOURCE,
        resolution=(7680, 4320),
        supersampling=4,
        tags=("multi-object", "composite", "supersampling", "8k"),
    ),
)


def run_workload(spec: WorkloadSpec, engine: Optional[ChronosEngine] = None) -> Dict:
    """Run one workload under the protocol and return its measurement row."""
    eng = engine or ChronosEngine(n_faces=spec.n_faces, layers=spec.layers)
    stats = measure(lambda: eng.render(spec.qsdl_source), repetitions=spec.repetitions)
    # One deterministic render supplies the frame facts (energy, hits).
    result = eng.render(spec.qsdl_source)
    energy_guard = nan_guard(float(result.energy), "render produced no finite energy")
    frame_facts = {
        "energy": energy_guard["value"],
        "energy_measured": energy_guard["measured"],
        "rendered_pixels_hit": int(result.rendered_pixels_hit),
        "total_pixels": int(result.total_pixels),
        "frame_shape": list(result.frame_shape),
        "samples_per_pixel": int(result.samples_per_pixel or 1),
        "render_backend": result.render_backend,
        "distinct_distribution_values": None,
    }
    try:
        import numpy as np

        frame_facts["distinct_distribution_values"] = int(
            len(np.unique(np.round(result.distribution, 9)))
        )
    except Exception:  # noqa: BLE001
        pass
    return {
        "workload": spec.name,
        "description": spec.description,
        "tags": list(spec.tags),
        "resolution": list(spec.resolution),
        "n_faces": spec.n_faces,
        "layers": spec.layers,
        "supersampling": spec.supersampling,
        "wall_time": stats,
        "frame_facts": frame_facts,
    }


def run_all(resolution_override: Optional[Tuple[int, int]] = None,
            repetitions_override: Optional[int] = None) -> Dict:
    """Run every real workload and build the protocol envelope."""
    rows = []
    for spec in REAL_WORKLOADS:
        if resolution_override is not None and spec.resolution == (7680, 4320):
            src = spec.qsdl_source.replace(
                "resolution=(7680,4320)",
                f"resolution=({resolution_override[0]},{resolution_override[1]})",
            )
            reps = repetitions_override if repetitions_override is not None else spec.repetitions
            spec = WorkloadSpec(
                name=spec.name,
                description=spec.description,
                qsdl_source=src,
                resolution=resolution_override,
                n_faces=spec.n_faces,
                layers=spec.layers,
                supersampling=spec.supersampling,
                repetitions=reps,
                tags=spec.tags + ("resolution_overridden",),
            )
        rows.append(run_workload(spec))
    return envelope(sections={"real_workloads": rows})


def main() -> None:
    payload = run_all()
    out_path = Path(__file__).resolve().parent / "real_workload_results.json"
    write_artifact(payload, out_path)
    print(json.dumps(payload, indent=2, default=str))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()