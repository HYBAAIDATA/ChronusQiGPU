"""Super-GPU benchmark entry point.

The super-GPU substrate is Chronus (post-consolidation "the GPU" is
Chronus), so the benchmark lives at ``scripts/benchmark_chronus.py`` —
per-device measured paths, aggregate vs best single (partition
efficiency), ASIC/GPU/CPU reported separately, and
``{"measured": false, "reason": ...}`` on hosts without measured
hardware. This script is the spec-named alias: it forwards argv verbatim
and exits with the same status. There is one benchmark, not two.
"""

from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(
        str(Path(__file__).resolve().parent / "benchmark_chronus.py"),
        run_name="__main__",
    )
