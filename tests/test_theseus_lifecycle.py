"""Real lifecycle and migration-adjacent tests; no hardware claims."""
import asyncio
import signal
import threading
import time
import pytest

from chronus.execution.lifecycle import LifecycleState, ShutdownSignals, join_until
from chronus.execution.mining_entrypoint import ChronusRealMiningEngine

pytestmark = pytest.mark.real

def test_signal_notification_restores_handlers():
    before = signal.getsignal(signal.SIGTERM)
    with ShutdownSignals() as signals:
        signals._notify(signal.SIGTERM, None)
        assert signals.requested
    assert signal.getsignal(signal.SIGTERM) is before

def test_shared_join_budget_reports_survivors():
    release = threading.Event()
    threads = [threading.Thread(target=release.wait, name=f"test-worker-{i}") for i in range(3)]
    for thread in threads:
        thread.start()
    try:
        assert set(join_until(threads, time.monotonic_ns() + 20_000_000)) == {t.name for t in threads}
    finally:
        release.set()
        assert not join_until(threads, time.monotonic_ns() + 1_000_000_000)

def test_zero_budget_session_does_not_connect():
    engine = ChronusRealMiningEngine("127.0.0.1", 1, "worker", "x")
    asyncio.run(engine.run(max_seconds=0))
    assert engine._state is LifecycleState.STOPPED
    assert engine._terminal_status == "STOP"
    assert not engine.running
    with pytest.raises(RuntimeError, match="started twice"):
        asyncio.run(engine.run(max_seconds=0))
