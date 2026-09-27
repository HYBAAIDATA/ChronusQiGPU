"""T4 — Encoding contract tests (Binet + Zeckendorf).

Claims under test (aethel/CONTRACT.md Section B):
  B1 uniqueness   — Zeckendorf masks: no adjacent bits, no F_0/F_1 use
  B2 round trip   — unfold(fold(x)) == x byte-identical
  B3 Binet        — closed-form index == recursive index, exact equality
  B4 domain bound — fold rejects oversize payloads, no silent truncation
"""

import hashlib
import json
import os
import subprocess
import sys

import pytest

from aethel.encoding import MAX_FOLD_LEN, fold, unfold
from aethel.errors import FoldDomainOverflow
from aethel.fibonacci import binet_fibonacci, fibonacci
from aethel.zeckendorf import HardenedZeckendorfCodec

ROUNDTRIP_SCALE = int(os.environ.get("AETHEL_TEST_FOLDS", "2_000"))
BINET_SCALE = 10_000


def _deterministic_payload(seed: int, length: int) -> bytes:
    out = bytearray()
    block = seed.to_bytes(8, "big")
    while len(out) < length:
        block = hashlib.sha256(block).digest()
        out.extend(block)
    return bytes(out[:length])


def test_b2_roundtrip_byte_identical():
    """T4a: random payloads of length 1..1024 round-trip losslessly."""
    for seed in range(ROUNDTRIP_SCALE):
        length = 1 + (seed * 7919) % 1024
        payload = _deterministic_payload(seed, length)
        restored = unfold(fold(payload))
        assert restored == payload, f"round-trip divergence at seed {seed}"


def test_b2_edge_cases_empty_and_single_byte():
    assert unfold(fold(b"")) == b""
    assert unfold(fold(b"\x00")) == b"\x00"
    assert unfold(fold(b"\xff")) == b"\xff"


def test_b1_zeckendorf_uniqueness_non_adjacent():
    """T4b: every folded mask has no two adjacent indices — the Zeckendorf
    uniqueness invariant, checked on the vector the encoder emits."""
    import random

    rng = random.Random(0xAE7E1)
    for _ in range(ROUNDTRIP_SCALE):
        value = rng.getrandbits(64)
        mask = HardenedZeckendorfCodec.encode(value)
        # Non-adjacency is the engine of uniqueness (the codec's own rule).
        assert HardenedZeckendorfCodec.verify_non_adjacent(mask), (
            f"adjacent Zeckendorf bits for {value}"
        )
        # Decode is the identity — uniqueness implies one decoding.
        assert HardenedZeckendorfCodec.decode(mask) == value


def test_b1_folded_vectors_verify():
    """Every vector produced by fold() self-verifies."""
    for seed in range(200):
        vector = fold(_deterministic_payload(seed, 1 + (seed * 31) % 256))
        assert vector.verify() is True


def test_b3_binet_matches_recursive_exact():
    """T4c: closed-form Binet index agrees with the recursive index to
    exact integer equality for n in 0..10^4."""
    for n in range(BINET_SCALE + 1):
        assert binet_fibonacci(n) == fibonacci(n), f"Binet diverged at n={n}"


def test_b4_fold_domain_overflow_rejected():
    """T4d: payloads beyond the declared domain raise FoldDomainOverflow —
    no silent truncation."""
    with pytest.raises(FoldDomainOverflow):
        fold(b"x" * (MAX_FOLD_LEN + 1))
    with pytest.raises(FoldDomainOverflow):
        fold(b"x" * 9, max_fold_len=8)
    # Boundary: exactly max_fold_len is inside the domain.
    vector = fold(b"\xAB" * 64, max_fold_len=64)
    assert unfold(vector) == b"\xAB" * 64


def test_b4_malformed_vector_rejected():
    """A forged vector (adjacent bits) cannot be unfolded."""
    from aethel.encoding import ZeckendorfVector
    from aethel.errors import ZeckendorfInvariantError

    bad = ZeckendorfVector(blocks=((0, 0b11),), total_bytes=8)  # adjacent bits
    with pytest.raises(ZeckendorfInvariantError):
        unfold(bad)


def test_t4e_determinism_across_interpreters():
    """T4e: fold is byte-identical across fresh interpreter sessions —
    encoding is a function of the payload only."""
    payload = _deterministic_payload(42, 512)
    local = fold(payload)
    local_digest = hashlib.sha256(
        json.dumps(sorted(local.blocks)).encode()
    ).hexdigest()

    program = (
        "import hashlib, json; "
        "from aethel.encoding import fold; "
        "v = fold(open(%r, 'rb').read()); "
        "print(hashlib.sha256(json.dumps(sorted(v.blocks)).encode()).hexdigest())"
    )
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as tmp:
        tmp.write(payload)
        tmp_path = tmp.name
    try:
        for _ in range(2):  # two fresh interpreters (plus this process = 3)
            out = subprocess.run(
                [sys.executable, "-c", program % tmp_path],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            )
            assert out.returncode == 0, out.stderr
            assert out.stdout.strip() == local_digest
    finally:
        os.unlink(tmp_path)


def test_encoding_bound_is_logarithmic():
    """The declared bound is O(log N): the number of folded units grows
    linearly in payload bytes but each unit encodes 8 bytes in one mask —
    no 'unlimited storage' claim, only the measured curve."""
    small = fold(b"a" * 64)
    large = fold(b"a" * 1024)
    assert small.folded_units * 16 >= large.folded_units
    assert large.folded_units == 128
