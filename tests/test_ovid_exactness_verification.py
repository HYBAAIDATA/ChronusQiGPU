"""OVID exactness verification — property/differential proofs per contract.

Each EXACT-classified transform in OVID_TRANSFORM_CONTRACTS is exercised
against its declared invariants: source -> transform -> inverse/materialise
-> verified semantic equivalence. Nothing here is a fresh implementation —
these tests run the production modules the contracts name.
"""
from __future__ import annotations

import os
import struct

import numpy as np
import pytest

from aethel.constants import (
    AETHEL_D7_OFFSET,
    AETHEL_D10_OFFSET,
    STATE_BYTES,
)
from aethel.fold_store import (
    CommitConflictError,
    DeviceLostError,
    FoldStoreError,
    PersistentFoldStore,
)
from aethel.phi_fold import (
    KernelBoundary,
    phi_fold,
    phi_unfold,
    reconstruction_error,
    splice_region,
    unfold_partial,
    unfold_region,
)
from aethel.phi_memory import MemoryTier, PhiMemoryHierarchy
from aethel.shm import AethelQueue


# -- ovid.phi_fold.numeric: EXACT round-trip across the dtype domain -----------


@pytest.mark.parametrize(
    "dtype", [np.int64, np.uint8, np.float64, np.complex128]
)
@pytest.mark.parametrize("depth", [0, 1, 2, 3, 4])
def test_phi_fold_numeric_exact_round_trip(dtype, depth):
    rng = np.random.default_rng(depth)
    base = rng.standard_normal(4096)
    if np.issubdtype(dtype, np.integer):
        array = (base * 100).astype(dtype)
    elif dtype == np.complex128:
        array = base + 1j * rng.standard_normal(4096)
        array = array.astype(dtype)
    else:
        array = base.astype(dtype)
    state = phi_fold(array, depth=depth)
    out = phi_unfold(state)
    # EXACT contract: element-exact, dtype-exact, content-hash verified
    assert np.array_equal(out, array)
    assert out.dtype == array.dtype
    assert state.verify_content_hash()
    assert reconstruction_error(array, state) == 0.0


def test_phi_fold_rejects_non_numeric_dtype():
    with pytest.raises(Exception):
        phi_fold(np.array([True, False, True]))


def test_phi_fold_state_corruption_detected():
    state = phi_fold(np.arange(512, dtype=np.float64), depth=3)
    tampered = state.retained.copy()
    tampered[0] += 1.0
    from aethel.phi_fold import NumericFoldState

    forged = NumericFoldState(
        retained=tampered,
        complements=state.complements,
        depth=state.depth,
        original_shape=state.original_shape,
        original_size=state.original_size,
        dtype=state.dtype,
        content_hash=state.content_hash,  # stale hash vs altered bytes
    )
    assert not forged.verify_content_hash()


# -- ovid.phi_fold.splice: EXACT regional write ---------------------------------


@pytest.mark.parametrize("depth", [1, 2, 4])
def test_splice_bit_identical_to_unfold_write_refold(depth):
    rng = np.random.default_rng(7)
    array = rng.standard_normal(2048)
    state = phi_fold(array, depth=depth)
    boundary = KernelBoundary(offset=700, length=613)
    values = rng.standard_normal(boundary.length)
    new_state, affected = splice_region(state, boundary, values)

    expected = array.copy()
    expected[boundary.slice] = values
    expected_state = phi_fold(expected, depth=depth)

    assert np.array_equal(phi_unfold(new_state), expected)
    assert new_state.content_hash == expected_state.content_hash
    # segments outside the write region are shared verbatim (identity, not
    # copies); touched levels are the ones splice_region reports
    parent_logical = (state.retained,) + tuple(reversed(state.complements))
    child_logical = (new_state.retained,) + tuple(reversed(new_state.complements))
    touched_levels = set(affected)
    for index, (parent_seg, child_seg) in enumerate(
        zip(parent_logical, child_logical)
    ):
        level = -1 if index == 0 else depth - index
        if level in touched_levels:
            assert child_seg is not parent_seg
        else:
            assert child_seg is parent_seg
    assert len(affected) <= depth + 1


def test_splice_does_not_mutate_parent_state():
    array = np.arange(1024, dtype=np.float64)
    state = phi_fold(array, depth=2)
    before = state.content_hash
    splice_region(state, KernelBoundary(10, 40), np.full(40, -1.0))
    assert state.verify_content_hash()
    assert state.content_hash == before


def test_splice_dtype_mismatch_fails_closed():
    state = phi_fold(np.arange(256, dtype=np.float64), depth=1)
    with pytest.raises(Exception):
        splice_region(state, KernelBoundary(0, 4), np.arange(4, dtype=np.int32))


# -- ovid.phi_fold.unfold_partial: EXACT addressed reconstruction ----------------


def test_unfold_partial_equals_full_unfold_span():
    rng = np.random.default_rng(3)
    array = rng.standard_normal(5000)
    state = phi_fold(array, depth=4)
    for offset, length in [(0, 1), (777, 512), (4900, 100), (1234, 3000)]:
        piece = unfold_partial(state, KernelBoundary(offset, length))
        assert np.array_equal(piece, array.ravel()[offset : offset + length])


def test_unfold_region_equals_shaped_slice():
    rng = np.random.default_rng(11)
    array = rng.standard_normal((24, 30))
    state = phi_fold(array, depth=3)
    region, stats = unfold_region(state, (slice(2, 10), slice(5, 20)))
    assert np.array_equal(region, array[2:10, 5:20])
    assert stats.decoded_bytes == stats.source_values_read * array.dtype.itemsize
    with pytest.raises(Exception):
        unfold_region(state, (slice(0, 24, 2), slice(0, 30)))  # strided -> closed


# -- ovid.phi_memory.refold: EXACT tier transitions ------------------------------


def test_refold_tier_transitions_preserve_payload():
    hierarchy = PhiMemoryHierarchy()
    rng = np.random.default_rng(5)
    array = rng.standard_normal(4096)
    hierarchy.store("w", array, MemoryTier.HBM, fold_depth=3)
    for tier in (MemoryTier.L2, MemoryTier.SRAM, MemoryTier.REGISTER):
        hierarchy.promote("w", tier)
        assert np.array_equal(hierarchy.read("w"), array)
    for tier in (MemoryTier.SRAM, MemoryTier.L2, MemoryTier.HBM):
        hierarchy.demote("w", tier)
        assert np.array_equal(hierarchy.read("w"), array)
    resident = hierarchy.load("w")
    assert resident.verify_content_hash()


def test_regional_commit_preserves_tier_and_content_tracking():
    hierarchy = PhiMemoryHierarchy()
    array = np.arange(1024, dtype=np.float64)
    hierarchy.store("r", array, MemoryTier.L2)
    boundary = KernelBoundary(100, 24)
    values = np.full(24, 9.5)
    hierarchy.commit_region("r", boundary, values)
    expected = array.copy()
    expected[boundary.slice] = values
    assert np.array_equal(hierarchy.read("r"), expected)
    assert hierarchy.load("r").verify_content_hash()


# -- ovid.fold_store.checkpoint: EXACT persistence + recovery/replay -------------


def test_checkpoint_restore_replays_versions_and_exactly_once(tmp_path):
    store = PersistentFoldStore(default_depth=2)
    array = np.arange(2048, dtype=np.float64)
    store.create("block-a", array)
    store.commit_region(
        "block-a",
        KernelBoundary(0, 32),
        np.full(32, 1.25),
        commit_id="c1",
        expected_version=0,
    )
    store.commit_region(
        "block-a",
        KernelBoundary(32, 16),
        np.full(16, -2.5),
        commit_id="c2",
    )
    path = store.checkpoint(tmp_path / "fold-checkpoint")

    restored = PersistentFoldStore.restore(path)
    assert np.array_equal(restored.read("block-a"), store.read("block-a"))
    assert restored.version("block-a") == store.version("block-a")
    assert restored.lineage("block-a") == store.lineage("block-a")
    assert restored.content_hash("block-a") == store.content_hash("block-a")
    # exactly-once survives replay: landed commit ids stay claimed
    with pytest.raises(CommitConflictError):
        restored.commit_region(
            "block-a", KernelBoundary(48, 8), np.zeros(8), commit_id="c1"
        )


def test_checkpoint_tampered_artifact_fails_closed(tmp_path):
    store = PersistentFoldStore(default_depth=1)
    store.create("b", np.arange(128, dtype=np.float64))
    path = store.checkpoint(tmp_path / "tampered")
    archive = np.load(path)
    seg_key = [k for k in archive.files if k.startswith("seg__")][0]
    tampered = dict(archive.items())
    seg = tampered[seg_key].copy()
    seg[0] += 1.0
    tampered[seg_key] = seg
    np.savez(tmp_path / "tampered2", **tampered)
    with pytest.raises(FoldStoreError):
        PersistentFoldStore.restore(tmp_path / "tampered2.npz")


def test_evict_regenerate_and_device_loss_contracts():
    store = PersistentFoldStore(default_depth=1)
    array = np.arange(512, dtype=np.float64)
    store.create("ev", array)
    header = store.evict("ev")
    assert header["content_hash"] == store.content_hash("ev")
    with pytest.raises(FoldStoreError):
        store.read("ev")
    # wrong source cannot rebind the lineage
    with pytest.raises(FoldStoreError):
        store.regenerate("ev", np.zeros(512))
    store.regenerate("ev", array)
    assert np.array_equal(store.read("ev"), array)

    store.create("dev", array, device_id="gpu-0")
    assert store.invalidate_device("gpu-0") == ("dev",)
    with pytest.raises(DeviceLostError):
        store.read("dev")
    store.rematerialize("dev", array)
    assert np.array_equal(store.read("dev"), array)


# -- shm transport: byte-exact delivery once admitted ---------------------------


def _state(d7: int, seal: int = 1) -> bytes:
    state = bytearray(STATE_BYTES)
    struct.pack_into("<I", state, AETHEL_D7_OFFSET, d7)
    struct.pack_into("<i", state, AETHEL_D10_OFFSET, seal)
    os.urandom(0)  # keep os imported for payload entropy elsewhere
    return bytes(state)


def test_seqlock_publish_delivers_committed_state_byte_exact(tmp_path):
    region = tmp_path / "queue.region"
    queue = AethelQueue(region, 8)
    state = _state(d7=13, seal=1)
    slot = queue.commit(state)
    assert slot == 13 % 8
    record = queue.read(slot)
    assert record is not None
    assert record.state == state
    queue.close()


def test_cassini_gate_rejects_unsealed_state(tmp_path):
    queue = AethelQueue(tmp_path / "q.region", 8)
    assert queue.commit(_state(d7=1, seal=0)) is None
    assert queue.commit(_state(d7=1, seal=7)) is None
    queue.close()


def test_attach_missing_region_fails_closed(tmp_path):
    from aethel.errors import SegmentMissing

    with pytest.raises(SegmentMissing):
        AethelQueue.attach(tmp_path / "absent.region", 8)
