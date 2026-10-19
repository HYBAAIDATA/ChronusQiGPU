"""Tests for event-loop lag fix and heartbeat SLA (Stage 0.3).

Validates:
- Off-thread execution of classical ensemble tree channels.
- Event loop dispatch latency p95 < 2.0s.
- Zero dropped jobs under burst conditions.
- Asynchronous storage snapshots.
"""

import time
import pytest
from pythia.runtime_fix import AsyncTreeChannelEvaluator, evaluate_tree_channels


def test_tree_channels_inference_structure():
    """Verify classical ensemble evaluation returns expected channel dict."""
    block = {"id": "block_1", "features": [0.5, 1.2, -0.3]}
    channels = evaluate_tree_channels(block)
    assert "rf" in channels
    assert "xgb" in channels
    assert "lgbm" in channels
    assert "gb" in channels
    assert all(isinstance(v, float) for v in channels.values())


def test_heartbeat_sla_and_zero_dropped_jobs():
    """Simulate streaming block arrivals: assert p95 loop lag < 2.0s and 0 dropped jobs."""
    evaluator = AsyncTreeChannelEvaluator(max_workers=4)

    num_blocks = 52
    futures = []
    received_results = []

    for i in range(num_blocks):
        block = {
            "id": f"job_braiins_{i:04d}",
            "features": [i * 0.1, (i % 7) * 0.5, 0.42],
        }
        fut = evaluator.on_block(block, callback=lambda r: received_results.append(r))
        futures.append(fut)

    # Wait for completion of asynchronous inferences
    for fut in futures:
        res = fut.result(timeout=5.0)
        assert res is not None

    p95_lag = evaluator.get_p95_heartbeat_lag()

    # Core SLA Assertions:
    # 1. Heartbeat lag p95 must be strictly under 2.0 seconds (typically < 0.05s)
    assert p95_lag < 2.0, f"Heartbeat p95 lag {p95_lag:.4f}s violated SLA (> 2.0s)"

    # 2. Zero dropped jobs
    assert evaluator.dropped_jobs == 0

    # 3. All block results published and snapshots recorded
    assert len(evaluator.published_q5_fields) == num_blocks
    assert len(evaluator.async_snapshots) == num_blocks
    assert evaluator.slow_heartbeat_alerts == 0

    evaluator.shutdown()
