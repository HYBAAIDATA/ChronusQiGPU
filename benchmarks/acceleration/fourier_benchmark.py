"""Compare equivalent normalized explicit transforms; output JSON to stdout."""
import json
import os
import platform
import statistics
import sys
import time
import numpy as np
from chronus.acceleration.fourier import qft


def direct(x):
    n = len(x)
    index = np.arange(n)
    matrix = np.exp(2j * np.pi * np.outer(index, index) / n)
    return matrix @ x / np.sqrt(n)


def fft(x):
    return np.fft.ifft(x, norm="ortho")


def run():
    records = []
    rng = np.random.default_rng(418)
    for n in (64, 256):
        x = rng.normal(size=n) + 1j * rng.normal(size=n)
        functions = {"layer_qft": qft, "direct_dft": direct, "optimized_fft": fft}
        expected = direct(x)
        for name, fn in functions.items():
            fn(x)  # one untimed warmup per function
            times, last = [], None
            for _ in range(7):
                start = time.perf_counter_ns()
                last = fn(x)
                times.append(time.perf_counter_ns() - start)
                np.testing.assert_allclose(last, expected, atol=1e-11, rtol=1e-11)
            records.append({"workload": "normalized positive-sign explicit DFT", "n": n,
                            "implementation": name, "elapsed_ns": times,
                            "median_ns": statistics.median(times),
                            "max_abs_error_vs_direct": float(np.max(np.abs(last-expected))),
                            "raw_output_complex_pairs": [[float(z.real), float(z.imag)] for z in last]})
    return {"description": "One-module layer; no end-to-end service benchmark",
            "seed": 418, "repetitions": 7, "warmups": 1, "timer": "perf_counter_ns",
            "timing_scope": "function call including validation/output; input generation and verification excluded; direct matrix construction included",
            "comparison": "identical explicit vector input and output; direct DFT and optimized FFT",
            "python": sys.version, "numpy": np.__version__, "platform": platform.platform(),
            "thread_settings": {k: os.environ.get(k) for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')},
            "records": records}


if __name__ == '__main__':
    print(json.dumps(run(), indent=2, allow_nan=False))
