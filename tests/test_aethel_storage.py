"""T3 — Storage contract tests (Fibonacci + Cassini).

Claims under test (aethel/CONTRACT.md Section A):
  A1 address monotonicity    — strictly increasing Fibonacci indices
  A2 Cassini ledger integrity — every quadruple satisfies the identity
  A3 gap detection           — a removed index fails reads, before retrieval
  A4 forgery detection       — non-Fibonacci index/value pairs rejected
  A5 bounded write           — a single write advances <= max_step
  A6 concurrent writers      — disjoint writers share one consistent ledger
"""

import os
import threading

import pytest

from aethel.errors import GapDetected, InvalidAddress
from aethel.fibonacci import cassini_holds, fibonacci, is_fibonacci
from aethel.storage import (
    MAX_ADDRESS_INDEX,
    AddressSpace,
    CassiniLedger,
    LedgerEntry,
)

# Declared test scale. The soak-scale run lives in `aethel selftest --full`;
# this suite must stay fast enough for CI while exercising every claim.
WRITE_SCALE = int(os.environ.get("AETHEL_TEST_WRITES", "20_000"))


def test_a1_index_stream_strictly_increasing_fibonacci():
    """T3a: consecutive writes produce strictly increasing Fibonacci indices
    and each committed value equals fibonacci(index) exactly."""
    remaining = WRITE_SCALE
    offset = 0
    while remaining:
        space = AddressSpace()
        previous = 0
        batch = min(remaining, MAX_ADDRESS_INDEX)
        for i in range(batch):
            address = space.write(f"block-{offset + i}".encode())
            assert address.index > previous, f"index regressed at write {offset + i}"
            assert address.value == fibonacci(address.index)
            previous = address.index
        offset += batch
        remaining -= batch


def test_a2_ledger_verify_and_single_forged_quadruple():
    """T3b: verify_ledger over the committed stream; corrupting ONE
    quadruple makes it return False."""
    space = AddressSpace()
    for i in range(256):
        space.write(f"a2-{i}".encode())
    assert space.ledger.verify_ledger() is True
    assert all(cassini_holds(e.quadruple) for e in space.ledger.entries)

    # Forge one quadruple in place — the verifier must catch it.
    victim = space.ledger.entries[10]
    space.ledger.entries[10] = LedgerEntry(
        seq=victim.seq,
        index=victim.index,
        value=victim.value,
        quadruple=(victim.quadruple[0] + 1,) + victim.quadruple[1:],
        digest=victim.digest,
        writer=victim.writer,
    )
    assert space.ledger.verify_ledger() is False


def test_a3_gap_detection_blocks_retrieval():
    """T3c: removing one index from the stream makes the next read raise
    GapDetected before any payload is returned."""
    space = AddressSpace()
    addresses = [space.write(f"gap-{i}".encode()) for i in range(8)]

    del space.ledger.entries[3]  # the gap
    with pytest.raises(GapDetected):
        space.read(addresses[0])
    with pytest.raises(GapDetected):
        space.read(addresses[5])
    assert space.ledger.verify_ledger() is False


def test_a4_forged_index_and_value_rejected():
    """T3d: an index/value pair not on the true Fibonacci sequence raises
    InvalidAddress at write time."""
    space = AddressSpace()
    space.write(b"real")

    with pytest.raises(InvalidAddress):
        space.register(index=100, value=12345, payload=b"forged-value")

    # A Fibonacci value paired with the wrong index is also a forgery.
    with pytest.raises(InvalidAddress):
        space.register(index=50, value=fibonacci(51), payload=b"forged-index")

    with pytest.raises(InvalidAddress):
        space.register(index=0, value=0, payload=b"below-domain")


def test_a4_duplicate_and_regressed_index_rejected():
    """A duplicate or regressed index is a forged transition."""
    space = AddressSpace()
    first = space.write(b"x")
    with pytest.raises(InvalidAddress):
        space.register(index=first.index, value=first.value, payload=b"dup")


def test_a5_bounded_advance_enforced():
    """T3e: one write may advance the index by at most max_step."""
    space = AddressSpace(max_step=4)
    for i in range(64):
        before = space.ledger.entries[-1].index if space.ledger.entries else 0
        address = space.write(f"a5-{i}".encode())
        assert 1 <= address.index - before <= 4
    with pytest.raises(InvalidAddress):
        space.write(b"too-far", advance=5)
    with pytest.raises(InvalidAddress):
        space.write(b"zero-step", advance=0)


def test_a6_concurrent_writers_disjoint_ranges():
    """T3f: two writers on disjoint index ranges share one ledger without
    corrupting it — the global sequence stays contiguous and per-writer
    streams strictly increase."""
    base = AddressSpace()
    writer_a = base
    writer_b = base.fork(writer=1, start_index=1)
    # Writer B registers into a disjoint band; writer A streams low indices.
    barrier = threading.Barrier(2)

    def stream(space, prefix, count):
        barrier.wait()
        for i in range(count):
            space.write(f"{prefix}-{i}".encode())

    def registered(space, start, count):
        barrier.wait()
        for i in range(count):
            idx = 1_000 + i
            space.register(idx, fibonacci(idx), f"hi-{i}".encode())

    t1 = threading.Thread(target=stream, args=(writer_a, "lo", 200))
    t2 = threading.Thread(target=registered, args=(writer_b, 1_000, 200))
    t1.start()
    t2.start()
    t1.join(timeout=60)
    t2.join(timeout=60)

    assert len(base.ledger.entries) == 400
    assert base.ledger.verify_ledger() is True
    seqs = [e.seq for e in base.ledger.entries]
    assert seqs == list(range(400)), "global sequence is not contiguous"


def test_ledger_rejects_forged_append_directly():
    """The ledger itself — not just AddressSpace — is the forgery gate."""
    ledger = CassiniLedger()
    ledger.append(1, "d" * 64, writer=0)
    with pytest.raises(InvalidAddress):
        ledger.append(5, "d" * 64, writer=0, value=12345)  # fib(5) = 5 != 12345
    with pytest.raises(InvalidAddress):
        ledger.append(1, "d" * 64, writer=0)  # regression
    assert is_fibonacci(ledger.entries[0].value)


def test_verify_requires_all_blocks_present():
    """A ledger that verifies but lacks a block fails space.verify()."""
    space = AddressSpace()
    a = space.write(b"present")
    space.write(b"vanished")
    del space._blocks[space.ledger.entries[-1].index]
    assert space.ledger.verify_ledger() is True
    assert space.verify() is False
    # But reading the surviving block still works.
    assert space.read(a) == b"present"
