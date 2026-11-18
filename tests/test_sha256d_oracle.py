"""SHA-256d header packing, target boundaries, and accounting regressions."""
import hashlib
import struct
from enum import IntEnum

import pytest

from chronus.execution.sha256d_oracle import Sha256dTargetOracle, sha256d, target_from_bits

pytestmark = pytest.mark.real
PREFIX = bytes(range(76))


def reference_digest(ntime, nonce):
    header = PREFIX[:68] + struct.pack('<I', ntime) + PREFIX[72:76] + struct.pack('<I', nonce)
    return hashlib.sha256(hashlib.sha256(header).digest()).digest()


@pytest.mark.parametrize('ntime,nonce', [(0, 0), (0, 0xFFFFFFFF), (0xFFFFFFFF, 0), (0xFFFFFFFF, 0xFFFFFFFF)])
def test_digest_packs_both_lanes_little_endian(ntime, nonce):
    oracle = Sha256dTargetOracle(PREFIX, 0)
    assert oracle.digest((ntime << 32) | nonce) == reference_digest(ntime, nonce)
    assert (oracle.evaluations, oracle.midstates, oracle.compressions) == (1, 1, 3)


def test_target_is_inclusive_and_verify_has_separate_accounting():
    value = (23 << 32) | 42
    digest = reference_digest(23, 42)
    target = int.from_bytes(digest, 'little')
    for threshold, accepted in [(target - 1, False), (target, True), (target + 1, True)]:
        oracle = Sha256dTargetOracle(PREFIX, threshold)
        assert oracle.verify(value) == (accepted, digest[::-1].hex())
        assert (oracle.evaluations, oracle.midstates, oracle.compressions) == (0, 0, 0)
        assert oracle(value) is accepted
        assert oracle.verify(value) == (accepted, digest[::-1].hex())
        assert (oracle.evaluations, oracle.midstates, oracle.compressions) == (1, 1, 3)


def test_repeated_and_interleaved_times_do_not_mutate_cached_hashes():
    oracle = Sha256dTargetOracle(PREFIX, 0)
    for ntime, nonce in [(1, 2), (2, 3), (1, 4), (1, 2)]:
        assert oracle.digest((ntime << 32) | nonce) == reference_digest(ntime, nonce)
    assert (oracle.evaluations, oracle.midstates, oracle.compressions) == (4, 2, 10)


def test_prefix_is_copied_and_truncated_to_header_fields():
    prefix = bytearray(PREFIX + b'ignored nonce and suffix')
    oracle = Sha256dTargetOracle(prefix, 0)
    prefix[:] = b'\xff' * len(prefix)
    assert oracle.prefix == PREFIX
    assert oracle.ntime == int.from_bytes(PREFIX[68:72], 'little')
    assert oracle.digest(0) == reference_digest(0, 0)


@pytest.mark.parametrize('prefix', [b'', bytes(75), 'x' * 76, None, memoryview(bytes(76))])
def test_invalid_prefix(prefix):
    with pytest.raises(ValueError, match='header prefix'):
        Sha256dTargetOracle(prefix, 0)


@pytest.mark.parametrize('target', [-1, 1 << 256, True, False, 1.0, '0', None])
def test_invalid_target(target):
    with pytest.raises(ValueError, match='unsigned 256-bit'):
        Sha256dTargetOracle(PREFIX, target)


@pytest.mark.parametrize('target', [0, (1 << 256) - 1])
def test_target_endpoints_are_accepted(target):
    assert Sha256dTargetOracle(PREFIX, target).target == target


def test_compact_target_accepts_integer_enum():
    class Bits(IntEnum):
        SMALL = 0x03012345
    assert target_from_bits(Bits.SMALL) == 0x012345


@pytest.mark.parametrize('data', [b'', b'abc', bytes(range(256))])
def test_sha256d_matches_two_independent_hash_calls(data):
    assert sha256d(data) == hashlib.sha256(hashlib.sha256(data).digest()).digest()
