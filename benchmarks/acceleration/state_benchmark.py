"""Benchmark validated explicit state preparation and unitary application."""
import json
import os
import platform
import statistics
import sys
import time
import numpy as np
from chronus.acceleration.state import normalize, apply_unitary


def layer(x, u):
    return apply_unitary(normalize(x), u)


def baseline(x, u):
    # Independent direct formulation, same validation for this finite benchmark.
    if not np.isfinite(x).all() or not np.isfinite(u).all():
        raise ValueError('nonfinite')
    v = x / np.linalg.norm(x)
    if not np.allclose(u.conj().T @ u, np.eye(len(v)), rtol=0, atol=1e-10):
        raise ValueError('not unitary')
    return u @ v


def run():
    rng = np.random.default_rng(419)
    records = []
    for n in (8, 64):
        x = rng.normal(size=n) + 1j*rng.normal(size=n)
        u = np.diag(np.exp(1j*rng.uniform(-np.pi, np.pi, size=n)))
        expected = baseline(x, u)
        for name, fn in [('layer', layer), ('direct_numpy_baseline', baseline)]:
            fn(x, u)
            times = []
            for _ in range(7):
                start = time.perf_counter_ns()
                result = fn(x, u)
                times.append(time.perf_counter_ns()-start)
                np.testing.assert_allclose(result, expected, rtol=1e-10, atol=1e-10)
            records.append({'n': n, 'operation': name, 'elapsed_ns': times,
                            'median_ns': statistics.median(times),
                            'max_abs_error': float(np.max(np.abs(result-expected))),
                            'raw_output_complex_pairs': [[float(z.real), float(z.imag)] for z in result]})
    return {'workload': 'normalize explicit state then validate and apply diagonal unitary',
            'timing_scope': 'complete calls including validation and output; input generation and post-call correctness assertion excluded',
            'limitations': 'baseline assumes generated nonzero vector and compatible shapes; no general equivalence for invalid inputs',
            'seed': 419, 'warmups': 1, 'repetitions': 7, 'timer': 'perf_counter_ns',
            'python': sys.version, 'numpy': np.__version__, 'platform': platform.platform(),
            'thread_settings': {k: os.environ.get(k) for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')},
            'records': records}


if __name__ == '__main__':
    print(json.dumps(run(), indent=2, allow_nan=False))
