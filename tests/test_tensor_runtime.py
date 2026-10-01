"""Timing, cancellation, timeout, and memory-preflight runtime behaviour."""

from __future__ import annotations

import time

import pytest

from tensor.contracts import MemoryBudget, Precision, TensorShape
from tensor.errors import TensorCancelledError, TensorMemoryError, TensorTimeoutError
from tensor.runtime import (
    CancellationToken,
    Deadline,
    preflight_memory,
    telemetry_record,
    timed_execute,
)


def test_preflight_memory_fails_closed_before_execution():
    shapes = (TensorShape((1000, 1000)),)
    with pytest.raises(TensorMemoryError):
        preflight_memory(shapes, Precision.FLOAT64, MemoryBudget(1024))


def test_preflight_memory_returns_estimate_within_budget():
    shapes = (TensorShape((2, 2)),)
    estimate = preflight_memory(shapes, Precision.FLOAT64, MemoryBudget(1024))
    assert estimate == 2 * 2 * 8


def test_deadline_raises_timeout_after_expiry():
    deadline = Deadline(timeout_ns=1)
    time.sleep(0.01)
    with pytest.raises(TensorTimeoutError):
        deadline.check()


def test_deadline_with_no_timeout_never_raises():
    Deadline(timeout_ns=None).check()


def test_cancellation_token_blocks_after_cancel():
    token = CancellationToken()
    token.check()  # fine before cancellation
    token.cancel()
    with pytest.raises(TensorCancelledError):
        token.check()


def test_timed_execute_measures_elapsed_time_and_records_operations():
    _, measurement = timed_execute(lambda: 42, operations=10, backend="numpy-cpu")
    assert measurement.operations == 10
    assert measurement.elapsed_ns > 0
    assert measurement.backend == "numpy-cpu"
    assert measurement.fallback_used is False


def test_timed_execute_honours_cancellation_before_running():
    token = CancellationToken()
    token.cancel()
    with pytest.raises(TensorCancelledError):
        timed_execute(lambda: 1, operations=1, backend="numpy-cpu", cancel_token=token)


def test_timed_execute_raises_timeout_if_already_expired():
    with pytest.raises(TensorTimeoutError):
        timed_execute(
            lambda: time.sleep(0.01),
            operations=1,
            backend="numpy-cpu",
            timeout_ns=1,
        )


def test_timed_execute_records_fallback_evidence():
    _, measurement = timed_execute(
        lambda: 1,
        operations=1,
        backend="numpy-cpu",
        fallback_used=True,
        fallback_reason="preferred backend unavailable",
    )
    assert measurement.fallback_used is True
    assert measurement.fallback_reason == "preferred backend unavailable"


def test_telemetry_record_merges_extra_fields_without_losing_truth_class():
    _, measurement = timed_execute(lambda: 1, operations=1, backend="numpy-cpu")
    record = telemetry_record(measurement, request_id="abc123")
    assert record["request_id"] == "abc123"
    assert record["truth_class"] == "measured"
    assert record["hashrate_hps"] is None
