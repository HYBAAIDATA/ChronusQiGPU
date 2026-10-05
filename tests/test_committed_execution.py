"""Committed-path execution: coordinate-committed output, resident write-back.

Covers the closed-loop folded write path end-to-end — committed
contraction (matmul/kron row-blocks), the CoordinateCommit exactly-once
contract, PhiGPU resident write-back gated on the integrity verdict, and
the runtime record's committed-path measurements.
"""

import numpy as np
import pytest

from aethel.phi_fold import KernelBoundary, phi_fold, phi_unfold
from aethel.phi_memory import MemoryHierarchyError, PhiMemoryHierarchy
from chronus.phi_gpu import (
    CoordinateCommit,
    KernelLaunchConfig,
    KernelTask,
    PhiGPU,
    PhiGPUError,
)
from tensor import TensorRuntime
from tensor.folded import folded_execute


def _gpu(*, cores=4):
    gpu = PhiGPU(cores=cores)
    return gpu


# ---- committed contraction (tensor/folded.py) ------------------------------


def test_committed_matmul_correctness_rectangular_and_odd():
    rng = np.random.default_rng(7)
    for m, k, n in [(7, 5, 9), (16, 16, 16), (3, 4, 2), (9, 1, 5)]:
        a = rng.normal(size=(m, k))
        b = rng.normal(size=(k, n))
        out, receipt = folded_execute("matmul", (phi_fold(a, 3), phi_fold(b, 3)))
        assert receipt.path == "committed"
        got = phi_unfold(out)
        assert got.shape == (m, n)
        # Not bit-identical (declared): row-block reassociation ~1e-16.
        assert np.allclose(got, a @ b, rtol=1e-12, atol=1e-12)
        assert np.max(np.abs(got - a @ b)) <= 1e-12


def test_committed_matmul_decodes_full_cone_but_bounded_peak():
    rng = np.random.default_rng(3)
    a = rng.normal(size=(16, 8))
    b = rng.normal(size=(8, 12))
    out, receipt = folded_execute("matmul", (phi_fold(a, 3), phi_fold(b, 3)))
    full = (a.size + b.size) * a.itemsize
    # Honest dependency: A row-blocks + all of B == the full cone.
    assert receipt.decoded_bytes == full
    # The measured win is peak materialisation, not decode volume.
    assert 0 < receipt.peak_materialized_bytes < full
    assert receipt.commit_regions >= 2
    assert receipt.commit_bytes == 16 * 12 * a.itemsize


def test_committed_kron_bit_identical():
    rng = np.random.default_rng(11)
    a = rng.normal(size=(5, 3))
    b = rng.normal(size=(2, 4))
    out, receipt = folded_execute("kron", (phi_fold(a, 2), phi_fold(b, 2)))
    assert receipt.path == "committed"
    assert np.array_equal(phi_unfold(out), np.kron(a, b))
    assert receipt.commit_regions >= 2


def test_committed_matmul_dtypes():
    rng = np.random.default_rng(5)
    a32 = rng.normal(size=(8, 8)).astype(np.float32)
    b32 = rng.normal(size=(8, 8)).astype(np.float32)
    out, _ = folded_execute("matmul", (phi_fold(a32, 3), phi_fold(b32, 3)))
    assert np.allclose(phi_unfold(out), a32 @ b32, rtol=1e-5, atol=1e-6)
    ac = (rng.normal(size=(6, 6)) + 1j * rng.normal(size=(6, 6))).astype(
        np.complex128
    )
    bc = (rng.normal(size=(6, 6)) + 1j * rng.normal(size=(6, 6))).astype(
        np.complex128
    )
    out, _ = folded_execute("matmul", (phi_fold(ac, 3), phi_fold(bc, 3)))
    assert np.allclose(phi_unfold(out), ac @ bc, rtol=1e-12, atol=1e-12)


def test_committed_out_of_domain_falls_back_materializing():
    rng = np.random.default_rng(2)
    # Nonconformable 2-D inputs propagate numpy's error — the same contract
    # the materializing path has always had.
    with pytest.raises(ValueError):
        folded_execute(
            "matmul",
            (phi_fold(rng.normal(size=(4, 4)), 2), phi_fold(rng.normal(size=(5, 5)), 2)),
        )
    # Rank != 2 is outside the committed domain: materializing path.
    a3 = rng.normal(size=(2, 3, 4))
    b3 = rng.normal(size=(2, 4, 3))
    out, receipt = folded_execute("matmul", (phi_fold(a3, 1), phi_fold(b3, 1)))
    assert receipt.path == "materialized"
    assert np.allclose(phi_unfold(out), a3 @ b3)


def test_runtime_execute_matmul_surfaces_commit_measurements():
    rt = TensorRuntime()
    a = np.arange(12.0).reshape(3, 4) + 0.5
    b = np.arange(20.0).reshape(4, 5) - 0.25
    rt.store_tensor("a", a, depth=2)
    rt.store_tensor("b", b, depth=2)
    record = rt.execute("matmul", ("a", "b"), op_count=3 * 4 * 5)
    assert record["path"] == "committed"
    assert record["commit_regions"] >= 1
    assert record["commit_bytes"] == 15 * 8
    assert 0 < record["peak_materialized_bytes"] < record["decoded_bytes"] + 1
    got = phi_unfold(rt.store.read_state(record["output"]))
    assert np.allclose(got, a @ b, rtol=1e-12, atol=1e-12)


# ---- CoordinateCommit (chronus/phi_gpu.py) ----------------------------------


def test_coordinate_commit_exactly_once():
    commit = CoordinateCommit(8, np.float64)
    commit.commit(0, np.array([1.0, 2.0]))
    commit.commit(4, np.array([5.0, 6.0]))
    commit.commit(2, np.array([3.0, 4.0]))
    commit.commit(6, np.array([7.0, 8.0]))
    assert np.array_equal(commit.finish(), np.arange(1.0, 9.0))
    with pytest.raises(PhiGPUError):
        commit.commit(3, np.array([9.0]))  # already committed


def test_coordinate_commit_gap_fails_closed():
    commit = CoordinateCommit(8, np.float64)
    commit.commit(0, np.array([1.0, 2.0]))
    with pytest.raises(PhiGPUError, match="uncommitted"):
        commit.finish()


def test_coordinate_commit_out_of_span():
    commit = CoordinateCommit(4, np.float64)
    with pytest.raises(PhiGPUError):
        commit.commit(3, np.array([1.0, 2.0]))


# ---- resident write-back (aethel/phi_memory.py + phi_gpu) --------------------


def test_memory_commit_region_splices_and_keeps_integrity():
    memory = PhiMemoryHierarchy()
    memory.store("w", np.arange(16.0), fold_depth=3)
    affected = memory.commit_region("w", KernelBoundary(4, 4), np.full(4, 9.0))
    assert affected
    assert np.array_equal(
        memory.read("w")[:16], np.concatenate([np.arange(4.0), np.full(4, 9.0), np.arange(8.0, 16.0)])
    )
    assert memory._residents["w"].verify_integrity()
    with pytest.raises(MemoryHierarchyError):
        memory.commit_region("w", KernelBoundary(14, 8), np.ones(8))
    with pytest.raises(MemoryHierarchyError):
        memory.commit_region("ghost", KernelBoundary(0, 1), np.ones(1))


def test_launch_kernel_commit_to_writes_verified_result():
    gpu = _gpu()
    gpu.memory.store("src", np.arange(8.0), fold_depth=1)
    gpu.memory.store("dst", np.zeros(8), fold_depth=1)
    result = gpu.launch_kernel(
        KernelLaunchConfig(
            name="src",
            work_items=8,
            kernel=lambda s: s * 2.0,
            commit_to=("dst", KernelBoundary(0, 8)),
        )
    )
    assert np.array_equal(result, np.arange(8.0) * 2.0)
    assert np.array_equal(gpu.memory.read("dst")[:8], np.arange(8.0) * 2.0)
    assert gpu.launch_log[-1].committed == ("dst", 0, 8)


def test_launch_kernel_commit_withheld_on_failed_verdict():
    gpu = _gpu()
    gpu.memory.store("src", np.arange(8.0), fold_depth=1)
    gpu.memory.store("dst", np.zeros(8), fold_depth=1)
    # Per-slice output differs from whole-work reference → verdict fails.
    with pytest.raises(PhiGPUError, match="withheld"):
        gpu.launch_kernel(
            KernelLaunchConfig(
                name="src",
                work_items=8,
                kernel=lambda s: s + s.size,
                commit_to=("dst", KernelBoundary(0, 8)),
            )
        )
    assert np.array_equal(gpu.memory.read("dst")[:8], np.zeros(8))


def test_non_coordinate_kernel_fails_closed():
    gpu = _gpu()
    gpu.memory.store("src", np.arange(8.0), fold_depth=1)
    with pytest.raises(PhiGPUError, match="coordinate"):
        gpu.launch_kernel(
            KernelLaunchConfig(
                name="src", work_items=8, kernel=lambda s: np.asarray([s.sum()])
            )
        )


def test_scheduled_task_commit_to_flows_through():
    gpu = _gpu()
    gpu.memory.store("src", np.arange(8.0), fold_depth=1)
    gpu.memory.store("dst", np.zeros(8), fold_depth=1)
    task = KernelTask(
        name="double-src",
        position=1.0,
        resident="src",
        payload={
            "kernel": lambda s: s * 2.0,
            "boundary": KernelBoundary(0, 8),
            "work_items": 8,
            "commit_to": ("dst", KernelBoundary(0, 8)),
        },
    )
    gpu.submit_task(task, 1.0)
    gpu.run_ready()
    assert np.array_equal(gpu.memory.read("dst")[:8], np.arange(8.0) * 2.0)
    assert gpu.launch_log[-1].committed == ("dst", 0, 8)


def test_commit_boundary_must_match_work_items():
    with pytest.raises(PhiGPUError, match="commit boundary"):
        KernelLaunchConfig(
            name="src",
            work_items=4,
            kernel=lambda s: s,
            commit_to=("dst", KernelBoundary(0, 8)),
        )


def test_reduce_results_empty():
    gpu = _gpu()
    assert gpu._reduce_results((), total=0).size == 0
