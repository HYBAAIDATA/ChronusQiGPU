"""The batched numpy Reed-Solomon decoder against the pure-Python reference.

``decode_block`` (Berlekamp-Welch, one block at a time) is the reference.
``decode_blocks`` / ``heal`` (syndromes, Berlekamp-Massey, Chien, Forney,
vectorised) must return exactly the same result on every input, including
inputs with more errors than the code can correct.
"""

from __future__ import annotations

import hashlib
import random

import numpy as np
import pytest

from chronus.security.al_haras import reed_solomon as rs

pytestmark = pytest.mark.real

N, K = rs.DEFAULT_N, rs.DEFAULT_K
T = (N - K) // 2


def _reference(word):
    res = rs.decode_block(word, N, K)
    if res["status"] == "uncorrectable":
        return None
    return res["data"]


def _random_codeword(rng):
    data = [rng.randrange(256) for _ in range(K)]
    return data + rs.encode_block(data, N, K)


def test_encode_blocks_matches_reference_encoder():
    rng = random.Random(1)
    trace = bytes(rng.randrange(256) for _ in range(32 * 37 + 5))
    fast = rs.encode_blocks(trace)
    for b, start in enumerate(range(0, len(trace), K)):
        block = list(trace[start:start + K])
        block += [0] * (K - len(block))
        assert fast[b].tolist() == rs.encode_block(block, N, K)


@pytest.mark.parametrize("errors", list(range(0, T + 4)) + [16, 24])
def test_batched_decoder_agrees_with_reference(errors):
    rng = random.Random(1000 + errors)
    words = []
    for _ in range(60):
        word = _random_codeword(rng)
        for pos in rng.sample(range(N), errors):
            word[pos] = (word[pos] + rng.randrange(1, rs.P)) % rs.P
        words.append(word)
    corrected, ok, damaged = rs.decode_blocks(np.array(words), N, K)
    for i, word in enumerate(words):
        ref = _reference(word)
        assert bool(damaged[i]) == (errors > 0)
        if ref is None:
            assert not ok[i], (errors, i)
        else:
            assert ok[i], (errors, i)
            assert corrected[i, :K].tolist() == ref
    if errors <= T:
        assert ok.all()


def test_heal_repairs_every_block_at_the_bound_byte_exact():
    rng = random.Random(7)
    trace = bytes(rng.randrange(256) for _ in range(4096 + 17))
    env = rs.protect(trace)
    bad = bytearray(trace)
    for start in range(0, len(bad), K):
        span = min(K, len(bad) - start)
        for pos in rng.sample(range(span), min(T, span)):
            bad[start + pos] ^= rng.randrange(1, 256)
    out = rs.heal(bytes(bad), env)
    assert out["repaired"] == trace
    assert out["integrity_verified"]
    assert out["uncorrectable_blocks"] == []
    assert hashlib.sha256(out["repaired"]).hexdigest() == env["sha256"]


def test_heal_beyond_bound_reports_block_and_keeps_bytes():
    trace = bytes(range(256)) * 2
    env = rs.protect(trace)
    bad = bytearray(trace)
    for pos in range(T + 1):
        bad[64 + pos] ^= 0xFF
    out = rs.heal(bytes(bad), env)
    assert 2 in out["uncorrectable_blocks"]
    assert not out["integrity_verified"]
    assert out["repaired"][64:96] == bytes(bad[64:96])


def test_symbols_outside_field_rejected():
    with pytest.raises(rs.ReedSolomonError):
        rs.decode_blocks(np.full((1, N), rs.P), N, K)
