"""A short, seeded soak of the full voyage; the long soak runs via soak_voyage.py."""

from __future__ import annotations

import asyncio

from soak_voyage import run_soak


def test_short_soak_keeps_every_invariant():
    stats = asyncio.run(run_soak(8.0, seed=11, backend="cpu"))
    assert stats["unexpected_errors"] == []
    assert stats["executions"] > 20
    assert stats["submits"] > 0
    assert stats["duplicate_submits"] == 0
    assert stats["stale_submits"] == 0
    assert stats["max_queue_depth"] <= 3
    assert stats["max_active_leases"] <= 5
    assert stats["causal_events_retained"] <= 4096
    assert stats["session_state"] == "SEARCHING"
    assert stats["recovery_mode"] in ("NORMAL", "DE_RATE")
