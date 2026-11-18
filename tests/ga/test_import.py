"""Import budget tests for the GA namespace.

The measurement methodology is shared with scripts/ci/check_ga_import.py so
the test and the gate cannot disagree about what the budget means.

A timing assertion has to survive a busy machine. The first import pays for
the page cache, so warmup samples are discarded; the gate is a p95 over many
samples rather than a median, because a median ignores the tail; and samples
slower than a stall threshold are discarded rather than allowed to dominate
the percentile.
"""

import importlib.util
import pathlib
import subprocess
import sys
import time
import pytest

pytestmark = pytest.mark.real

ROOT = pathlib.Path(__file__).resolve().parents[2]
GATE = ROOT / "scripts" / "ci" / "check_ga_import.py"

_spec = importlib.util.spec_from_file_location("check_ga_import", GATE)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


def _cold_import_samples(count):
    """Return the durations of `count` cold imports, in seconds."""
    samples = []
    for _ in range(count):
        start = time.perf_counter()
        subprocess.run(
            [sys.executable, "-c", "import ga.mathcore, ga.api"],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        samples.append(time.perf_counter() - start)
    return samples


def test_foundation_modules_import_without_creating_an_app():
    """The namespace must import cleanly and create no app as a side effect."""
    result = subprocess.run(
        [sys.executable, "-c", "import ga.mathcore, ga.api"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_import_budget_is_stable_under_load():
    """The p95 of cold imports must fit the budget on a busy machine."""
    gate.measure_imports()  # warmup, discarded by the gate
    samples = _cold_import_samples(gate.SAMPLES)
    kept = [sample for sample in samples if sample <= gate.STALL_SECONDS]
    assert kept, f"every sample exceeded the stall threshold: {samples}"
    p95 = gate.percentile(kept, 0.95)
    assert p95 < gate.P95_BUDGET_SECONDS, (
        f"p95 {p95:.3f}s exceeds the {gate.P95_BUDGET_SECONDS:.3f}s budget: "
        f"{[round(sample, 3) for sample in sorted(samples)]}"
    )

