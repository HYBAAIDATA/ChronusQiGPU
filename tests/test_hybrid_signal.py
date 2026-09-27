"""T7 — falsification suite for the hybrid traversal claim.

T7a (negative control): on an easy target no traversal order can have an
advantage; the measured difference MUST sit inside bootstrap noise. If it
does not, the harness is measuring artifacts and the test fails loudly.

T7b (positive control): on a harder target the harness must actually
measure something — trials complete, shares are found, attestations are
emitted.

T7c (honesty): the falsification report must state the outcome plainly in
its first paragraph, whichever direction the numbers go.

These tests run the live substrate (GPU if present, the honest CPU path
otherwise — either way the traversal-order measurement is valid).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from scripts.benchmark_hybrid import benchmark, write_reports


@pytest.fixture(scope="module")
def neg_result():
    # Easy target: expected nonces-to-share ~16. Every traversal equivalent.
    return benchmark(n=8, target_bits=252, nonce_space=1 << 16, resamples=500)


@pytest.fixture(scope="module")
def pos_result():
    # Harder target: expected ~2^18 nonces; traversal signal would show here.
    return benchmark(n=8, target_bits=238, nonce_space=1 << 20, resamples=500)


def test_negative_control_within_noise(neg_result):
    ci = neg_result["lucas_minus_gpu_only"]["ci95"]
    assert ci["contains_zero"], (
        "harness is measuring artifacts: negative-control CI "
        f"[{ci['low']}, {ci['high']}] excludes zero"
    )
    ci_even = neg_result["lucas_minus_even"]["ci95"]
    assert ci_even["contains_zero"], (
        "harness is measuring artifacts: negative-control even-split CI "
        f"[{ci_even['low']}, {ci_even['high']}] excludes zero"
    )


def test_positive_control_measures_something(pos_result):
    per_cfg = pos_result["per_config"]
    gpu = per_cfg["gpu_only"]
    assert gpu["n_completed"] > 0
    assert gpu["total_hashes"] > 0
    assert gpu["attestations_emitted"] > 0
    lucas = per_cfg["hybrid_lucas"]
    assert lucas["n_completed"] > 0
    assert lucas["total_hashes"] > 0
    # Every trial either found a share or honestly exhausted its span.
    assert lucas["found_rate"] is not None


def test_falsification_report_states_outcome(tmp_path, neg_result, pos_result):
    verdict = write_reports(neg_result, pos_result, out_dir=tmp_path)
    report = (tmp_path / "hybrid_falsification.md").read_text()
    bench = (tmp_path / "hybrid_benchmark.md").read_text()
    first_paragraph = report.split("\n\n")[1]
    honest_markers = (
        "No statistically significant difference was measured"
        in first_paragraph
        or "statistically significant difference was measured"
        in first_paragraph
    )
    assert honest_markers, (
        "falsification report does not state its outcome in the first "
        f"paragraph: {first_paragraph!r}"
    )
    assert "harness_trustworthy" in report
    assert "| config |" in bench
    assert "attested" in report or "attestation" in report
    assert isinstance(verdict["harness_trustworthy"], bool)
