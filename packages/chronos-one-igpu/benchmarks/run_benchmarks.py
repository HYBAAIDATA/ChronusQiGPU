# run_benchmarks.py -- Chronos GPU production benchmark suite (4 Aug 2026)
#
# Every number in BENCHMARKS.md is produced by actually running this script
# on the sandbox machine, not estimated or hand-written. Re-run with:
#   PYTHONPATH=src python3 benchmarks/run_benchmarks.py

from __future__ import annotations

import json
import platform
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np

from chronos.engine import ChronosEngine
from chronos.manifold import M32Manifold
from chronos.qsdl_compiler import QSDLCompiler, ManifoldConfig
from chronos.qsdl_parser import parse_qsdl
from chronos.theory.report import self_test_all, run_unbuilt_maths
from chronos.theory.superconductivity import bcs_gap_self_consistent, K_B
from chronos.academic.report import run_academic_enhancements
from chronos.phi_scaling import run_phi_power_scaling_benchmark, phi_power_exact

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


def timed(fn, *args, **kwargs):
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    return result, time.perf_counter() - t0


def bench_manifold_construction() -> dict:
    out = {}
    for n in (32, 64, 128, 256):
        _, dt = timed(lambda n=n: M32Manifold(n=n))
        out[str(n)] = round(dt, 6)
    return out


def bench_qsdl_parse_compile() -> dict:
    _, parse_dt = timed(parse_qsdl, DEMO_QSDL_SOURCE)
    compiler = QSDLCompiler()
    _, compile_dt = timed(compiler.compile, DEMO_QSDL_SOURCE)
    return {
        "parse_seconds": round(parse_dt, 6),
        "compile_seconds_including_parse": round(compile_dt, 6),
        "source_bytes": len(DEMO_QSDL_SOURCE),
    }


def bench_full_render_at_scale() -> dict:
    out = {}
    for n_faces in (32, 64, 128, 256):
        engine = ChronosEngine(n_faces=n_faces, layers=4)
        result, dt = timed(engine.render, DEMO_QSDL_SOURCE)
        out[str(n_faces)] = {
            "wall_seconds": round(dt, 4),
            "energy": round(float(result.energy), 6),
            "rendered_pixels_hit": int(result.rendered_pixels_hit),
            "total_pixels": int(result.total_pixels),
            "frame_shape": list(result.frame_shape),
            "raster_compression_ratio": round(float(result.raster_compression_ratio), 3),
            "distinct_distribution_values": int(len(np.unique(np.round(result.distribution, 9)))),
        }
    return out


def bench_bcs_solver() -> dict:
    tc_k = 9.2  # niobium-like reference Tc, matching the theory module's own self-test
    delta0_j = 1.76 * K_B * tc_k
    out = {"tc_kelvin": tc_k, "delta0_joules": delta0_j}
    temps = [0.0, tc_k * 0.3, tc_k * 0.6, tc_k * 0.9, tc_k * 0.99]
    rows = []
    for t in temps:
        gap, dt = timed(bcs_gap_self_consistent, t, delta0_j, tc_k)
        rows.append({
            "temperature_k": round(t, 4),
            "gap_joules": gap,
            "solve_seconds": round(dt, 6),
        })
    out["points"] = rows
    return out


def bench_theory_self_tests() -> dict:
    results, dt = timed(self_test_all)
    return {"total_seconds": round(dt, 4), "results": results}


def bench_academic_suite() -> dict:
    report, dt = timed(run_academic_enhancements)
    return {
        "total_seconds": round(dt, 4),
        "nist_benchmark_average_score": report["nist"]["benchmark_average_score"],
        "tensor_train_compression_ratio": report["tensor_train_1000_qubit"]["compression_ratio"],
    }


def bench_phi_scaling() -> dict:
    report, dt = timed(run_phi_power_scaling_benchmark, max_measured_power=15)
    return {
        "total_seconds": round(dt, 4),
        "empirical_scaling_exponent": report.empirical_scaling_exponent,
        "tiers": [
            {
                "power": t.power,
                "n_faces_exact_lucas_check": phi_power_exact(t.power),
                "n_faces": t.n_faces,
                "measured": t.measured,
                "wall_time_seconds": t.wall_time_seconds,
                "eigh_seconds": t.eigh_seconds,
                "energy": t.energy,
            }
            for t in report.tiers
        ],
    }


def main() -> None:
    suite_t0 = time.perf_counter()
    results = {
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "manifold_construction_seconds": bench_manifold_construction(),
        "qsdl_parse_compile": bench_qsdl_parse_compile(),
        "full_render_at_scale": bench_full_render_at_scale(),
        "bcs_gap_solver": bench_bcs_solver(),
        "theory_self_tests": bench_theory_self_tests(),
        "academic_suite": bench_academic_suite(),
        "phi_power_scaling": bench_phi_scaling(),
    }
    results["total_benchmark_wall_seconds"] = round(time.perf_counter() - suite_t0, 3)

    out_path = Path(__file__).resolve().parent / "results.json"
    out_path.write_text(json.dumps(results, indent=2, default=str))
    print(json.dumps(results, indent=2, default=str))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
