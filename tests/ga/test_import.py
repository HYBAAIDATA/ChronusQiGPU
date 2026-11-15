import subprocess
import sys
import time


def test_foundation_modules_import_without_creating_an_app():
    started = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "-c", "import ga.mathcore, ga.api"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    elapsed = time.perf_counter() - started
    assert result.returncode == 0, result.stderr
    assert elapsed < 0.5, f"cold import took {elapsed:.3f}s"


def test_import_budget_is_stable_under_load():
    """Median of 11 cold imports must fit the 500 ms budget; a single
    scheduler or Defender outlier is tolerated (second-worst must fit 750 ms)."""
    samples = []
    for _ in range(11):
        start = time.perf_counter()
        subprocess.run(
            [sys.executable, "-c", "import ga.mathcore, ga.api"],
            capture_output=True,
            timeout=30,
            check=True,
        )
        samples.append(time.perf_counter() - start)
    samples.sort()
    assert samples[len(samples) // 2] < 0.5, f"median {samples[5]:.3f}s: {samples}"
    assert samples[-2] < 0.75, f"persistent regression: {samples}"
