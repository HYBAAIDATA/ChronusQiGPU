"""T6 — Concurrency and crash safety for the aethel substrate.

Claims under test:
  T6a seqlock torn reads impossible under concurrent commit/read
  T6b writer crash mid-update: readers see the previous stable record
  T6c Cassini ledger survives a process-level restart (snapshot/attach)
  T6d SegmentMissing on attach to a nonexistent region
  T6e Python/C ABI agreement — constants parsed from the C header at
      test time, not duplicated
"""

import os
import struct
import threading

import pytest

from aethel.constants import (
    AETHEL_D10_OFFSET,
    AETHEL_D7_OFFSET,
    AETHEL_HEADER_BYTES,
    AETHEL_SLOT_STRIDE,
    STATE_BYTES,
)
from aethel.errors import AethelError, SegmentMissing
from aethel.shm import AethelQueue
from aethel.storage import AddressSpace

OPS = int(os.environ.get("AETHEL_TEST_OPS", "5_000"))


def _state(d7: int, d10: int) -> bytes:
    buf = bytearray(STATE_BYTES)
    struct.pack_into("<I", buf, AETHEL_D7_OFFSET, d7)
    struct.pack_into("<i", buf, AETHEL_D10_OFFSET, d10)
    return bytes(buf)


def test_t6a_seqlock_no_torn_reads(tmp_path):
    """Concurrent writers hammer the same slots; readers must see either a
    complete committed state or None — never a torn record."""
    path = tmp_path / "aethel.region"
    committed = {_state(slot, 1 if slot % 2 == 0 else -1) for slot in range(8)}
    stop = threading.Event()
    errors = []

    def writer():
        with AethelQueue(path, slot_count=8) as q:
            for i in range(OPS):
                if stop.is_set():
                    break
                q.commit(_state(i % 8, 1 if i % 2 == 0 else -1))

    def reader():
        with AethelQueue(path, slot_count=8) as q:
            while not stop.is_set():
                for slot in range(8):
                    rec = q.read(slot)
                    if rec is not None and rec.state not in committed:
                        errors.append((slot, rec.state))

    threads = [threading.Thread(target=writer) for _ in range(2)] + [
        threading.Thread(target=reader) for _ in range(3)
    ]
    for t in threads:
        t.start()
    for t in threads[:2]:
        t.join(timeout=120)
    stop.set()
    for t in threads[2:]:
        t.join(timeout=30)
    assert not errors, f"torn or forged records observed: {errors[:3]}"


def test_t6b_writer_crash_mid_update(tmp_path):
    """A sequence left odd (writer died mid-commit) yields None on read and
    the next commit recovers cleanly."""
    path = tmp_path / "aethel.region"
    with AethelQueue(path, slot_count=4) as q:
        good = _state(2, 1)
        assert q.commit(good) == 2
        # Simulate a crash: sequence forced odd mid-write.
        base = AETHEL_HEADER_BYTES + 2 * AETHEL_SLOT_STRIDE
        seq = struct.unpack_from("<Q", q._mmap, base)[0]
        struct.pack_into("<Q", q._mmap, base, seq + 1)  # odd = write in flight
        assert q.read(2, retries=4) is None
        # Recovery: commit resumes from the odd sequence and lands even.
        assert q.commit(good) == 2
        rec = q.read(2)
        assert rec is not None and rec.state == good


def test_t6c_ledger_survives_restart(tmp_path):
    """Snapshot, reattach in a fresh AddressSpace, and the ledger verifies
    byte-identically — plus the resumed writer keeps monotonic indices."""
    store = tmp_path / "store"
    space = AddressSpace()
    payloads = [f"restart-{i}".encode() for i in range(32)]
    for p in payloads:
        space.write(p)
    space.snapshot(store)

    resumed = AddressSpace.attach(store)
    assert resumed.ledger.verify_ledger() is True
    assert [e.index for e in resumed.ledger.entries] == [
        e.index for e in space.ledger.entries
    ]
    for i, entry in enumerate(resumed.ledger.entries):
        assert resumed.read(resumed.address_of_index(entry.index)) == payloads[i]

    # Resumed writing stays strictly monotonic for the same writer.
    address = resumed.write(b"post-restart")
    assert address.index > 32
    assert resumed.ledger.verify_ledger() is True


def test_t6d_missing_segment_is_typed(tmp_path):
    """Attaching to a nonexistent region raises SegmentMissing, not a
    silent create."""
    with pytest.raises(SegmentMissing):
        AethelQueue.attach(tmp_path / "absent.region", slot_count=4)
    with pytest.raises(SegmentMissing):
        AddressSpace.attach(tmp_path / "absent-store")


def test_t6d_corrupt_journal_fails_closed(tmp_path):
    """A malformed journal raises a typed aethel error — never truncates."""
    store = tmp_path / "store"
    space = AddressSpace()
    space.write(b"ok")
    space.snapshot(store)
    journal = store / "ledger.jsonl"
    journal.write_text(journal.read_text() + '{"seq": "garbage"\n')
    with pytest.raises(AethelError):
        AddressSpace.attach(store)


def test_t6e_c_abi_agreement_parses_header():
    """Every shared constant is parsed from the C header at test time —
    no hardcoded duplication in this test."""
    from aethel.selftest import check_c_abi_agreement

    verdict = check_c_abi_agreement()
    assert verdict["verdict"] == "PASS", verdict["detail"]
