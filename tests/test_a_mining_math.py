"""Owner A — mining/ root modules: nonce schedule, difficulty, search.

These are the deterministic search primitives the miner actually runs:
the Zeckendorf-derived nonce schedule, the per-block difficulty
controller, and the Grover-ordered / preimage / Merkle search wrappers —
each with its honest lucas pool route and theorem_proven=False status.
"""

from __future__ import annotations

import hashlib

import pytest

import turing_core
from mining.difficulty import MAX_ZERO_BITS, MIN_ZERO_BITS, DifficultyController
from mining.nonce_scheduler import NonceScheduler
from mining.search import GroverStyleSearch, MerklePathVerifier, PreimageSearch

HEADER = bytes(range(76)) + b"\x00\x00\x00\x00"


def _sha256d(blob: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(blob).digest()).digest()


# --- NonceScheduler --------------------------------------------------------


def test_nonce_schedule_is_deterministic():
    s = NonceScheduler(nonce_window=4096, cap=256)
    a = s.schedule(HEADER)
    b = s.schedule(HEADER)
    assert a == b and len(a) > 0
    assert all(0 <= n <= 0xFFFFFFFF for n in a)


def test_nonce_schedule_depends_on_header():
    s = NonceScheduler(nonce_window=4096, cap=256)
    other = bytes([42]) * 76 + b"\x00" * 4
    assert s.schedule(HEADER) != s.schedule(other)


def test_nonce_schedule_bounded_by_mining_kernel():
    s = NonceScheduler(nonce_window=4096, cap=256)
    sched = s.schedule(HEADER)
    r = s.kernel_check(len(sched))
    assert r["is_lucas_bounded"] is True
    assert r["lucas_bound"] >= len(sched)
    assert r["theorem_proven"] is False
    assert r["module"] == "mining.nonce_scheduler"


# --- DifficultyController ---------------------------------------------------


def test_difficulty_tightens_on_winner_relaxes_on_miss():
    d = DifficultyController()
    assert d.status()["zero_bits"] == MIN_ZERO_BITS
    r = d.update(True)
    assert r["zero_bits_after"] == 1 and r["winner_found"] is True
    assert d.difficulty() == pytest.approx(2.0)
    r = d.update(False)
    assert r["zero_bits_after"] == 0
    assert d.difficulty() == pytest.approx(1.0)


def test_difficulty_clamped_at_bounds():
    d = DifficultyController()
    for _ in range(MAX_ZERO_BITS + 5):
        d.update(True)
    assert d.status()["zero_bits"] == MAX_ZERO_BITS
    for _ in range(MAX_ZERO_BITS + 5):
        d.update(False)
    assert d.status()["zero_bits"] == MIN_ZERO_BITS


def test_difficulty_target_bytes_consistent():
    d = DifficultyController()
    assert d.target_bytes() == d.target_int().to_bytes(32, "big")
    d.update(True)
    assert d.target_int() == turing_core.MAX_TARGET >> 1


# --- GroverStyleSearch -------------------------------------------------------


def test_grover_style_search_finds_easy_target():
    g = GroverStyleSearch()
    schedule = list(range(512))
    # Max target: every digest wins; first probed nonce is returned.
    easy = (1 << 256) - 1
    r = g.search(HEADER, schedule, easy)
    assert r["mining_success"] is True
    assert r["winner_nonce"] in schedule
    # Consensus check: the returned nonce's digest does meet the target.
    blob = HEADER[:76] + r["winner_nonce"].to_bytes(4, "little")
    assert turing_core.hash_meets_target(_sha256d(blob), easy)
    assert r["theorem_proven"] is False


def test_grover_style_search_impossible_target():
    g = GroverStyleSearch()
    r = g.search(HEADER, list(range(64)), 0)
    assert r["mining_success"] is False and r["winner_nonce"] == -1
    assert r["probed"] == 64


def test_grover_style_search_lucas_scaling():
    g = GroverStyleSearch()
    r = g.search(HEADER, list(range(64)), 0, scale_index=15)
    assert r["lucas_value"] == 1364
    assert r["scaled_space"] == 64 * 1364
    assert r["grover_k_star"] == g.optimal_iterations(64 * 1364)
    with pytest.raises(ValueError, match="rung"):
        g.search(HEADER, list(range(8)), 0, scale_index=11)


def test_grover_style_kernel_check_route():
    g = GroverStyleSearch()
    r = g.kernel_check(10)
    assert r["kernel"] == "path_kernel" and r["theorem_proven"] is False
    assert r["module"] == "mining.search"


# --- PreimageSearch / MerklePathVerifier -------------------------------------


def test_preimage_scan_finds_winner():
    p = PreimageSearch()
    nonces = list(range(64))
    # Pick the nonce whose digest is minimal -> set target just above it.
    best = min(
        nonces,
        key=lambda n: int.from_bytes(_sha256d(HEADER[:76] + n.to_bytes(4, "little")), "little"),
    )
    target = int.from_bytes(_sha256d(HEADER[:76] + best.to_bytes(4, "little")), "little")
    r = p.scan(HEADER[:76], nonces, target)
    assert r["mining_success"] is True
    # The scan returns the FIRST nonce under target in schedule order.
    first = next(
        n
        for n in nonces
        if int.from_bytes(_sha256d(HEADER[:76] + n.to_bytes(4, "little")), "little") <= target
    )
    assert r["winner_nonce"] == first


def test_merkle_verifier_inclusion():
    m = MerklePathVerifier()
    leaf = _sha256d(b"coinbase")
    branches = [_sha256d(b"sib1"), _sha256d(b"sib2")]
    root = turing_core.PythiaMiningEngine.compute_merkle_root(leaf, branches)
    r = m.verify(leaf, branches, root)
    assert r["included"] is True
    r2 = m.verify(leaf, branches, _sha256d(b"wrong root"))
    assert r2["included"] is False
