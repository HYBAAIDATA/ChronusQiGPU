"""Explicit non-production fault injection; no simulated device telemetry."""
from dataclasses import replace
import pytest
from chronus.storage.erasure import encode_stripe, recover_stripe

pytestmark = pytest.mark.real


def test_exact_single_shard_erasure():
    for payload in (b"A", b"abc", b"abcdefghijklm", bytes(range(251))):
        manifest, shards = encode_stripe(payload, 4)
        assert recover_stripe(manifest, shards) == payload
        for index in range(4):
            damaged = list(shards)
            damaged[index] = None
            assert recover_stripe(manifest, tuple(damaged)) == payload


def test_one_corrupted_shard_recovered():
    payload = b"original data" * 5
    manifest, shards = encode_stripe(payload, 3)
    damaged = list(shards)
    damaged[1] = b"x" * len(shards[1])
    assert recover_stripe(manifest, tuple(damaged)) == payload


def test_multiple_missing_shards_fail_closed():
    manifest, shards = encode_stripe(b"abcdef", 3)
    damaged = list(shards)
    damaged[0] = damaged[2] = None
    with pytest.raises(ValueError, match="multiple"):
        recover_stripe(manifest, tuple(damaged))


def test_corrupt_parity_fails_closed():
    manifest, shards = encode_stripe(b"abcdef", 3)
    with pytest.raises(ValueError, match="metadata or parity"):
        recover_stripe(replace(manifest, parity=b"?" * manifest.shard_bytes), shards)


def test_invalid_payload_and_shard_count():
    with pytest.raises(ValueError):
        encode_stripe(b"")
    with pytest.raises(ValueError):
        encode_stripe(b"x", 1)
    with pytest.raises(ValueError):
        encode_stripe(b"x", True)
