"""Correctness benchmark: determinism (kellogg.benchmark.bench_determinism)."""

from benchmarks.tensor._run import main

if __name__ == "__main__":
    raise SystemExit(main("determinism"))
