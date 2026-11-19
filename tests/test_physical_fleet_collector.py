# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Arithmetic unit checks of the collector; no GPU workload is executed."""
import pytest

from benchmarks.physical_fleet import nearest_rank, summary

pytestmark = pytest.mark.real


def test_nearest_rank_uses_exact_integer_arithmetic():
    samples = list(range(1000, 0, -1))
    assert nearest_rank(samples, 50, 100) == 500
    assert nearest_rank(samples, 99, 100) == 990
    assert nearest_rank(samples, 999, 1000) == 999
    assert summary(samples)["p999"] == 999


def test_missing_samples_never_report_measurement():
    assert summary([]) == {"status": "UNAVAILABLE", "samples": 0}
    assert summary([10])["p999"] is None
    assert summary([10])["p999_status"] == "INSUFFICIENT_SAMPLES"
    with pytest.raises(ValueError):
        nearest_rank([], 50, 100)
