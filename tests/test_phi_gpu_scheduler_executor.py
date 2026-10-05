"""Geodesic scheduler → executor coupling: ready queue drives launches."""

import numpy as np
import pytest

from aethel.phi_fold import KernelBoundary
from aethel.phi_memory import MemoryTier, PhiMemoryHierarchy
from chronus.phi_gpu import KernelTask, PhiGPU, PhiGPUError


def _gpu(size=128):
    gpu = PhiGPU(memory=PhiMemoryHierarchy())
    data = np.arange(size, dtype=np.float64)
    gpu.store("x", data, tier=MemoryTier.L2)
    return gpu, data


def test_scheduled_task_boundary_controls_launch():
    gpu, data = _gpu()
    kernel = lambda s: s * 2.0  # noqa: E731
    gpu.submit_task(KernelBoundary(40, 8), kernel=kernel, resident="x")
    results = gpu.run_ready()
    assert len(results) == 1
    np.testing.assert_array_equal(results[0], data[40:48] * 2.0)
    # The executed boundary is the selected task's, not a local default.
    assert gpu.launch_log[-1].boundary == (40, 8)


def test_ready_queue_executes_in_scheduled_order():
    gpu, data = _gpu()
    kernel = lambda s: s + 1.0  # noqa: E731
    # Far boundary submitted first; near boundary must execute first.
    gpu.submit_task(KernelBoundary(100, 8), reference=1.0, kernel=kernel, resident="x")
    gpu.submit_task(KernelBoundary(4, 8), reference=1.0, kernel=kernel, resident="x")
    results = gpu.run_ready()
    assert [r.tolist() for r in results] == [
        (data[4:12] + 1.0).tolist(),
        (data[100:108] + 1.0).tolist(),
    ]
    # scheduled_log order == execution order, and both selected tasks ran.
    assert gpu.scheduler.scheduled_log == ["fma:1", "fma:0"]
    assert [t.name for t in gpu.scheduler.completed_tasks] == ["fma:1", "fma:0"]
    assert [r.boundary for r in gpu.launch_log] == [(4, 8), (100, 8)]


def test_dependency_readiness_gates_dispatch():
    gpu, data = _gpu()
    kernel = lambda s: s  # noqa: E731
    # Dependent is nearer — readiness must still gate it.
    gpu.submit_task(
        KernelBoundary(4, 4), reference=1.0, kernel=kernel, resident="x",
        operation="dep", depends_on=("fma:1",),
    )
    gpu.submit_task(
        KernelBoundary(100, 4), reference=1.0, kernel=kernel, resident="x"
    )
    # The dependent sits nearer to the reference but is blocked: only the
    # far ready task may dispatch.
    results = gpu.run_ready()
    assert len(results) == 2  # the dep unblocks after fma:1 completes
    np.testing.assert_array_equal(results[0], data[100:104])
    np.testing.assert_array_equal(results[1], data[4:8])
    assert gpu.scheduler.scheduled_log == ["fma:1", "dep:0"]
    assert gpu.scheduler.get_metrics()["blocked_tasks"] == 0


def test_unsatisfied_dependency_stays_queued():
    gpu, data = _gpu()
    kernel = lambda s: s  # noqa: E731
    gpu.submit_task(
        KernelBoundary(4, 4), kernel=kernel, resident="x",
        depends_on=("never:exists",),
    )
    assert gpu.run_ready() == []
    assert gpu.scheduler.schedule_next() is None
    assert gpu.scheduler.get_metrics()["blocked_tasks"] == 1


def test_task_payload_missing_pieces_fail_closed():
    gpu, _ = _gpu()
    gpu.scheduler.submit(
        KernelTask("bare", 4.0, payload={"boundary": KernelBoundary(0, 4)})
    )
    with pytest.raises(PhiGPUError, match="no kernel"):
        gpu.run_next()
    gpu.scheduler.submit(
        KernelTask(
            "nores", 4.0,
            payload={"boundary": KernelBoundary(0, 4), "kernel": lambda s: s},
        )
    )
    with pytest.raises(PhiGPUError, match="no resident"):
        gpu.run_next()


def test_standalone_launch_kernel_unchanged():
    gpu, data = _gpu()
    from chronus.phi_gpu import KernelLaunchConfig

    out = gpu.launch_kernel(
        KernelLaunchConfig(name="x", work_items=8, kernel=lambda s: s * 3.0)
    )
    np.testing.assert_array_equal(out, data[:8] * 3.0)
