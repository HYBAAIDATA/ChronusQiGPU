"""Persistent folded-state store: versioning, atomic commits, custody lifecycle."""

import numpy as np
import pytest

from aethel.fold_store import (
    CommitConflictError,
    DeviceLostError,
    FoldStoreError,
    PersistentFoldStore,
)
from aethel.phi_fold import (
    KernelBoundary,
    PhiFoldError,
    fold_result,
    phi_fold,
    phi_unfold,
    splice_region,
)


def test_splice_region_is_bit_identical_to_full_refold():
    data = np.arange(64, dtype=np.float64)
    state = phi_fold(data, depth=3)
    write = np.arange(8, dtype=np.float64) + 100.0
    spliced, affected = splice_region(state, KernelBoundary(20, 8), write)
    expected_full = data.copy()
    expected_full[20:28] = write
    reference = phi_fold(expected_full, depth=3)
    assert np.array_equal(phi_unfold(spliced), phi_unfold(reference))
    assert spliced.content_hash == reference.content_hash
    assert spliced.depth == reference.depth


def test_splice_region_touches_only_intersecting_lineage():
    data = np.arange(64, dtype=np.float64)
    state = phi_fold(data, depth=3)
    # Write into the retained (first) segment only.
    _, affected = splice_region(state, KernelBoundary(0, 4), np.zeros(4))
    assert affected == (-1,)
    # Write across the whole tensor touches every fold level.
    _, affected_all = splice_region(state, KernelBoundary(0, 64), np.zeros(64))
    assert set(affected_all) == {-1, 0, 1, 2}


def test_splice_region_rejects_dtype_and_bounds():
    state = phi_fold(np.arange(32, dtype=np.float32), depth=2)
    with pytest.raises(PhiFoldError, match="dtype"):
        splice_region(state, KernelBoundary(0, 4), np.zeros(4, dtype=np.float64))
    with pytest.raises(PhiFoldError, match="bounds"):
        splice_region(state, KernelBoundary(30, 8), np.zeros(8, dtype=np.float32))
    with pytest.raises(PhiFoldError, match="boundary requires"):
        splice_region(state, KernelBoundary(0, 8), np.zeros(4, dtype=np.float32))


def test_fold_result_delegates_to_regional_splice():
    data = np.arange(64, dtype=np.float64)
    state = phi_fold(data, depth=2)
    write = np.zeros(8)
    via_fold_result = fold_result(write, KernelBoundary(10, 8), state)
    via_splice, _ = splice_region(state, KernelBoundary(10, 8), write)
    assert np.array_equal(phi_unfold(via_fold_result), phi_unfold(via_splice))
    assert via_fold_result.content_hash == via_splice.content_hash
    # Depth change is a genuine global op — still a full re-fold.
    deeper = fold_result(write, KernelBoundary(10, 8), state, depth=4)
    assert deeper.depth == 4


def test_store_create_read_roundtrip_and_dtype():
    store = PersistentFoldStore(default_depth=2)
    data = np.arange(64, dtype=np.float32).reshape(8, 8)
    store.create("w", data)
    np.testing.assert_array_equal(store.read("w"), data)
    assert store.read("w").dtype == np.float32
    assert store.version("w") == 0


def test_commit_region_atomic_and_versioned():
    store = PersistentFoldStore()
    data = np.arange(64, dtype=np.float64)
    store.create("x", data, depth=2)
    record = store.commit_region(
        "x", KernelBoundary(10, 8), np.zeros(8), commit_id="c1", expected_version=0
    )
    assert record.from_version == 0 and record.to_version == 1
    assert record.region == (10, 8)
    assert set(record.affected_levels) <= {-1, 0, 1}
    assert store.version("x") == 1
    expected = data.copy()
    expected[10:18] = 0
    np.testing.assert_array_equal(store.read("x"), expected)
    # Lineage records the commit chain.
    assert store.lineage("x") == ("genesis", "v0:c1")
    # Content identity tracks the write.
    assert store.content_hash("x") != phi_fold(data, depth=2).content_hash


def test_commit_is_exactly_once():
    store = PersistentFoldStore()
    store.create("x", np.arange(32, dtype=np.float64), depth=1)
    store.commit_region("x", KernelBoundary(0, 4), np.ones(4), commit_id="dup")
    with pytest.raises(CommitConflictError, match="already committed"):
        store.commit_region("x", KernelBoundary(0, 4), np.ones(4), commit_id="dup")
    with pytest.raises(CommitConflictError, match="expected version"):
        store.commit_region(
            "x",
            KernelBoundary(4, 4),
            np.ones(4),
            commit_id="c2",
            expected_version=0,  # stale: current is 1
        )
    assert store.version("x") == 1


def test_concurrent_commits_serialize():
    import threading

    store = PersistentFoldStore()
    store.create("x", np.zeros(64, dtype=np.float64), depth=2)
    errors = []

    def worker(n):
        try:
            for i in range(10):
                store.commit_region(
                    "x",
                    KernelBoundary(i, 1),
                    np.array([float(n * 10 + i)]),
                    commit_id=f"t{n}:{i}",
                )
        except Exception as exc:  # pragma: no cover - failure surface
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert store.version("x") == 40
    expected = np.zeros(64)
    for n in range(4):
        for i in range(10):
            expected[i] = float(n * 10 + i)
    np.testing.assert_array_equal(store.read("x"), expected)


def test_eviction_and_regeneration(tmp_path):
    store = PersistentFoldStore()
    data = np.arange(64, dtype=np.float64)
    store.create("x", data, depth=2)
    store.commit_region("x", KernelBoundary(0, 4), np.ones(4), commit_id="w1")
    header = store.evict("x")
    assert header["content_hash"] == store.content_hash("x")
    with pytest.raises(FoldStoreError, match="evicted"):
        store.read("x")
    with pytest.raises(FoldStoreError, match="does not match"):
        store.regenerate("x", np.zeros(64))
    updated = data.copy()
    updated[:4] = 1.0
    store.regenerate("x", updated)
    np.testing.assert_array_equal(store.read("x"), updated)


def test_device_loss_invalidation_and_rematerialize():
    store = PersistentFoldStore()
    store.create("gpu-block", np.arange(16, dtype=np.float64), device_id="opencl:0")
    store.create("host-block", np.arange(16, dtype=np.float64))
    lost = store.invalidate_device("opencl:0")
    assert lost == ("gpu-block",)
    with pytest.raises(DeviceLostError):
        store.read("gpu-block")
    np.testing.assert_array_equal(store.read("host-block"), np.arange(16))
    with pytest.raises(FoldStoreError, match="does not match"):
        store.rematerialize("gpu-block", np.zeros(16))
    store.rematerialize("gpu-block", np.arange(16, dtype=np.float64))
    np.testing.assert_array_equal(store.read("gpu-block"), np.arange(16))


def test_checkpoint_restore_roundtrip_and_tamper(tmp_path):
    store = PersistentFoldStore()
    data = np.arange(64, dtype=np.float32)
    store.create("a", data, depth=2)
    store.commit_region("a", KernelBoundary(5, 4), np.full(4, 7.0, np.float32), commit_id="m1")
    store.create("b", np.arange(8, dtype=np.complex128), depth=1)
    path = store.checkpoint(tmp_path / "graph")

    restored = PersistentFoldStore.restore(path)
    assert restored.names() == ("a", "b")
    assert restored.version("a") == 1
    assert restored.lineage("a") == ("genesis", "v0:m1")
    expected = data.copy()
    expected[5:9] = 7.0
    np.testing.assert_array_equal(restored.read("a"), expected)
    assert restored.content_hash("a") == store.content_hash("a")
    # Exactly-once survives a restart.
    with pytest.raises(CommitConflictError):
        restored.commit_region("a", KernelBoundary(0, 1), np.zeros(1, np.float32), commit_id="m1")
    with pytest.raises(CommitConflictError):
        restored.commit_region(
            "a", KernelBoundary(0, 1), np.zeros(1, np.float32), commit_id="genesis"
        )


def test_checkpoint_tamper_fails_closed(tmp_path):
    store = PersistentFoldStore()
    store.create("a", np.arange(64), depth=2)
    store.checkpoint(tmp_path / "g")
    # Corrupt one segment array inside the archive.
    import zipfile

    real = tmp_path / "g.npz"
    bad = tmp_path / "g_bad.npz"
    with zipfile.ZipFile(real) as zin, zipfile.ZipFile(bad, "w") as zout:
        for item in zin.infolist():
            payload = zin.read(item.filename)
            if item.filename == "seg__a__0__0.npy":
                payload = payload[:-16] + b"\xde\xad\xbe\xef" * 4
            zout.writestr(item, payload)
    with pytest.raises(FoldStoreError, match="content-hash"):
        PersistentFoldStore.restore(bad)


def test_status_surface():
    store = PersistentFoldStore()
    store.create("a", np.arange(8), depth=1)
    status = store.status()
    assert status["format"] == "aethel-fold-store/v1"
    assert status["blocks"]["a"]["residency"] == "resident"
    assert status["blocks"]["a"]["content_hash"]
