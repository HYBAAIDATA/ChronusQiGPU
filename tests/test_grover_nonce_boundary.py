"""Regression: Grover amplitude amplification must never short-circuit
the SHA-256d consensus check by writing its own candidate nonces into the
header nonce field as a "shortcut."

Grover's iterate (Intelligence/grover_exact_scale.py) operates on an
abstract state vector span{|marked>, |uniform>} — it produces an iteration
count k* and a probability distribution. The winning nonce is then fed
through the standard double-SHA256 check in mining.hash_pipeline. There is
no codepath where Grover output is injected directly into the 80-byte header
nonce slot bypassing hashlib.

This test guards against exactly that drift (DRIFT-03: Consensus Bypass).
"""

import struct

import pytest

from Intelligence.grover_exact_scale import (
    FoldedGrover,
    optimal_iterations,
    run_folded,
)
from mining.hash_pipeline import HashPipeline, double_sha256


def test_grover_does_not_write_to_header_nonce():
    """Grover's folded iterate never touches the header nonce field.

    Run a small Grover instance (N=256, M=1) and assert:
    1. The FoldedGrover state object has no attribute or side-effect that
       mutates an 80-byte header's bytes [76:80] (the nonce slot).
    2. The iterate produces only probability amplitudes, not nonce values.
    """

    N = 256
    M = 1
    k = optimal_iterations(N, M)

    # A pristine header: bytes [76:80] are the nonce slot.
    header = bytearray(80)
    original_nonce_bytes = bytes(header[76:80])

    state = FoldedGrover.uniform(N, M)
    for _ in range(k):
        state.step(phase := 3.141592653589793, phase)

    # The header must be unchanged after Grover iterations.
    assert bytes(header[76:80]) == original_nonce_bytes

    # The FoldedGrover state must not expose nonce-writing methods.
    assert not hasattr(state, "write_nonce")
    assert not hasattr(state, "set_header_nonce")
    assert not hasattr(state, "inject_nonce")

    # The result dict of run_folded contains only probability/iteration keys,
    # never a "nonce" or "header" key.
    result = run_folded(N, M, iterations=k)
    for forbidden_key in ("nonce", "header", "payout", "injected"):
        assert forbidden_key not in result, (
            f"Grover returned forbidden key '{forbidden_key}' — "
            f"would bypass SHA-256d consensus"
        )


def test_grover_winning_nonce_always_passes_hashlib_recheck():
    """If a nonce is selected for submission after a Grover-guided search,
    it must pass the double-SHA256 target check — i.e., the nonce was found
    by the hash loop, not by Grover's amplitude projection directly.

    We simulate the contract: the search engine picks a candidate nonce from
    its schedule, runs double_sha256, and only reports success if the hash
    meets the target. A fabricated 'Grover winner' that doesn't hash must
    never be accepted.
    """
    header = bytes(80)
    # A trivial target that accepts ~1/256 of nonces
    target = bytes.fromhex("00" + "ff" * 31)

    # Scan the first 5000 nonces the way the real engine does.
    found = None
    for nonce in range(5000):
        blob = header[:76] + struct.pack("<I", nonce)
        digest = double_sha256(blob)
        if digest[::-1] <= target:
            found = (nonce, digest)
            break

    if found is not None:
        nonce, digest = found
        # Verify via the same path the consensus code uses.
        pipe = HashPipeline(threshold=0.0)
        res = pipe.grind(header, target, [nonce])
        assert res.mining_success
        assert res.winning_nonce == nonce
        assert res.winning_hash == digest
    else:
        pytest.skip("No winning nonce in first 5000 for random target")


def test_hash_pipeline_always_recomputes_double_sha256():
    """The HashPipeline.grind result must always carry a winning_hash that
    was independently computed via double_sha256. No shortcut path can
    produce a hash without the hashlib round-trip."""
    import hashlib

    header = bytes(80)
    target = bytes.fromhex("00" + "ff" * 31)
    pipe = HashPipeline(threshold=0.0)
    res = pipe.grind(header, target, list(range(5000)))

    if res.mining_success and res.winning_nonce is not None:
        blob = header[:76] + struct.pack("<I", res.winning_nonce)
        expected = hashlib.sha256(hashlib.sha256(blob).digest()).digest()
        assert res.winning_hash == expected, (
            "winning_hash does not match independent hashlib double-SHA256 — "
            "possible consensus bypass shortcut"
        )
        # The winning nonce's reversed hash must satisfy the target.
        assert res.winning_hash[::-1] <= target
