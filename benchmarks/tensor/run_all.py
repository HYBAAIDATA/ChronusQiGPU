"""Run the whole Kellogg tensor benchmark suite: python -m benchmarks.tensor.run_all [--quick]."""

from benchmarks.tensor._run import main

if __name__ == "__main__":
    raise SystemExit(main())
