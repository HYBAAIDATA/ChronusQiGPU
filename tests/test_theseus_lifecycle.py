"""Real lifecycle and migration-adjacent tests; no hardware claims."""
import asyncio
import signal
import threading
import time
import pytest

from chronus.execution.lifecycle import LifecycleState, OwnedWorkerGroup, ShutdownSignals, join_until
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


def test_owned_worker_deadline_does_not_block_event_loop_shutdown():
    group = OwnedWorkerGroup()
    started = threading.Event()
    release = threading.Event()

    def blocked():
        started.set()
        release.wait()

    async def session():
        task = asyncio.create_task(group.call("blocked-native", blocked))
        for _ in range(100):
            if started.is_set():
                break
            await asyncio.sleep(0.001)
        assert started.is_set()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        deadline = time.monotonic_ns() + 20_000_000
        assert group.join_until(deadline) == ["blocked-native"]

    try:
        asyncio.run(session())
    finally:
        release.set()
        assert not group.join_until(time.monotonic_ns() + 1_000_000_000)


@pytest.mark.parametrize("bad", [-1, float("nan"), float("inf"), "1", True])
def test_invalid_duration_is_rejected_before_start(bad):
    engine = ChronusRealMiningEngine("127.0.0.1", 1, "worker", "x")
    with pytest.raises(ValueError, match="max_seconds"):
        asyncio.run(engine.run(max_seconds=bad))
    assert engine._state is LifecycleState.INIT
