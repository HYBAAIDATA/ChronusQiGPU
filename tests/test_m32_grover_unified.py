"""Tests for m32_grover_unified.py, BitSlicedDomainOracle, and Grover helper fixes."""
import hashlib
import inspect
import json
import math
import random
import struct
from pathlib import Path

import numpy as np
import pytest

from fractions import Fraction

from python_backend import m32_grover_unified as u
from python_backend import phi_grover_v4 as pg
from python_backend.bit_sliced_domain_oracle import (
    BitSlicedDomainOracle,
    derive_early_abort_constraints,
    hash_meets_target,
    sha256d,
    target_from_bits,
)
from python_backend.exact_folded_grover import (
    ITERATION_CAP,
    QSqrt5,
    exceeds_phi_inverse,
    pisot_damp_qsqrt5,
)

HEADERS = Path("/workspace/user_quantum_gpu_experiment/nonces500/headers.json")
GENESIS_NONCE = 2083236893
GENESIS_MERKLE = bytes.fromhex(
    "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"
)[::-1]


def genesis_header(nonce: int = GENESIS_NONCE) -> bytes:
    return struct.pack("<I", 1) + bytes(32) + GENESIS_MERKLE + struct.pack(
        "<III", 1231006505, 0x1d00ffff, nonce
    )


def hashlib_mask(header_prefix76: bytes, nonces, target: int) -> int:
    m = 0
    for i, n in enumerate(nonces):
        digest = sha256d(header_prefix76 + struct.pack("<I", n & 0xFFFFFFFF))
        if hash_meets_target(digest, target):
            m |= 1 << i
    return m



SEARCH_PATH = [
    Path(__file__).resolve().parents[1] / "python_backend" / "m32_grover_unified.py",
    Path(__file__).resolve().parents[1] / "python_backend" / "exact_folded_grover.py",
    Path(__file__).resolve().parents[1] / "python_backend" / "bit_sliced_domain_oracle.py",
]


def _float_reference_p(N, M, k):
    theta = math.asin(math.sqrt(M / N))
    return math.sin((2 * k + 1) * theta) ** 2


def test_search_path_has_no_float_trig():
    import re
    pat = re.compile(r"math\.(sin|cos|sqrt|asin|pi)\b|import cmath|cmath\.")
    hits = []
    for path in SEARCH_PATH:
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if pat.search(line):
                hits.append(f"{path.name}:{i}:{line}")
    assert hits == [], "trig in search path:\n" + "\n".join(hits)


def test_fold_state_is_int_or_fraction_never_float():
    st = u.FoldedGrover.uniform(4096, 1)
    assert st.a == 1 and st.b == 1
    assert type(st.a) is int and type(st.b) is int
    for _ in range(8):
        st.step()
        assert isinstance(st.a, (int, Fraction)) and isinstance(st.b, (int, Fraction))
        assert type(st.a) is not float and type(st.b) is not float
        assert not isinstance(st.a, float) and not isinstance(st.b, float)


def test_fold_norm_is_exactly_one_and_scaled_is_N():
    for N, M in ((2, 1), (16, 1), (16, 3), (4096, 1), (4096, 3), (1024, 7)):
        st = u.FoldedGrover.uniform(N, M)
        for _ in range(u.peak_iterations(N, M) + 3):
            assert st.cassini_scaled() == N
            assert st.cassini_witness() == 1
            assert st.cassini_witness() == Fraction(1)
            st.step()
        assert st.cassini_scaled() == N
        assert st.cassini_witness() == 1


def test_threshold_is_exact_phi_inverse():
    # 1/2 is below phi^{-1}; a value just above the golden cut must pass.
    assert exceeds_phi_inverse(Fraction(1, 2)) is False
    # Fibonacci ratios F_{n-1}/F_n alternate about phi^{-1}.
    # Below the cut: 1/2, 3/5.  Above: 2/3, 5/8.
    assert exceeds_phi_inverse(Fraction(3, 5)) is False
    assert exceeds_phi_inverse(Fraction(2, 3)) is True
    assert exceeds_phi_inverse(Fraction(5, 8)) is True
    # Cross-multiply identity: p = 5/8, (2*5+8)^2 = 324, 5*64=320, 324>320.
    assert (2 * 5 + 8) ** 2 > 5 * 8 ** 2
    from lucas.core import fibonacci
    for n in range(3, 20):
        rat = Fraction(fibonacci(n - 1), fibonacci(n))
        num, den = rat.numerator, rat.denominator
        s = 2 * num + den
        assert exceeds_phi_inverse(rat) is (s > 0 and s * s > 5 * den * den)
    # Uniform 1/N is below the threshold.
    assert exceeds_phi_inverse(Fraction(1, 4096)) is False
    st = u.FoldedGrover.uniform(4096, 1)
    for _ in range(u.peak_iterations(4096, 1)):
        st.step()
    assert exceeds_phi_inverse(st.marked_probability) is True


def test_fold_matches_float_closed_form_to_1e12():
    for N, M in ((16, 1), (64, 1), (256, 3), (4096, 1), (1024, 5)):
        k = u.peak_iterations(N, M)
        st = u.FoldedGrover.uniform(N, M)
        for _ in range(k):
            st.step()
        ref = _float_reference_p(N, M, k)
        assert abs(float(st.marked_probability) - ref) < 1e-12, (N, M, k)


def test_optimal_iterations_found_by_exact_stepping():
    # N=4096, M=1 used to be floor(pi/4/theta) = 50; the exact peak is 50.
    assert u.peak_iterations(4096, 1) == 50
    # N=2, M=1: p stays 1/2, so the peak is at 0 iterates.
    assert u.peak_iterations(2, 1) == 0
    huge = u.optimal_iterations if hasattr(u, "optimal_iterations") else None
    from python_backend.exact_folded_grover import optimal_iterations
    assert optimal_iterations(10**100, 1) == ITERATION_CAP + 1


def test_pisot_damp_is_exact_in_qsqrt5_not_a_phase():
    # 1 - |psi| = 1 - (sqrt5-1)/2 = (3-sqrt5)/2
    assert pisot_damp_qsqrt5(1) == QSqrt5(Fraction(3, 2), Fraction(-1, 2))
    # 1 - |psi|^2 = 1 - (3-sqrt5)/2 wait |psi|^2 = (3-sqrt5)/2? 
    # |psi|^2 = ((sqrt5-1)/2)^2 = (5-2sqrt5+1)/4 = (3-sqrt5)/2
    # 1 - that = 1 - (3-sqrt5)/2 = (2-3+sqrt5)/2 = (sqrt5-1)/2
    assert pisot_damp_qsqrt5(2) == QSqrt5(Fraction(-1, 2), Fraction(1, 2))
    with pytest.raises(ValueError):
        from python_backend.exact_folded_grover import run_folded
        run_folded(16, 1, damp=Fraction(1, 2))


def test_module_has_no_rng():
    src = inspect.getsource(u)
    for line in src.splitlines():
        s = line.split("#", 1)[0]
        assert "import random" not in s
        assert "from random " not in s
        # allow the words "RNG" / "no RNG" in comments and docs only
        if "random." in s:
            pytest.fail(f"search path still references random: {line!r}")


def test_search_is_deterministic():
    hdr = genesis_header()
    T = target_from_bits(0x1d00ffff)
    nonce = GENESIS_NONCE
    base = nonce - 73
    a = u.unified_search(hdr, T, base, 128)
    b = u.unified_search(hdr, T, base, 128)
    assert a.found_nonce == b.found_nonce == nonce
    assert a.lane_order == b.lane_order
    assert a.lane_compressions == b.lane_compressions
    assert a.distinct_nonces_hashed == b.distinct_nonces_hashed
    assert [r["phase_mask"] for r in a.lane_runs] == [r["phase_mask"] for r in b.lane_runs]


def test_same_header_same_domain_order():
    hdr = genesis_header()
    occupied = list(range(32))
    assert u.domain_order(hdr, occupied) == u.domain_order(hdr, occupied)
    # nonce field must not affect the order (seed is header[:76])
    hdr2 = genesis_header(nonce=GENESIS_NONCE + 99)
    assert hdr[:76] == hdr2[:76]
    assert u.domain_order(hdr, occupied) == u.domain_order(hdr2, occupied)
    # a different prefix changes the order (or is astronomically unlikely to
    # collide — flip a bit in ntime)
    alt = bytearray(hdr)
    alt[68] ^= 1
    assert u.domain_order(bytes(alt), occupied) != u.domain_order(hdr, occupied)


def test_genesis_lane_73_phase_mask():
    hdr = genesis_header()
    T = target_from_bits(0x1d00ffff)
    nonces = [GENESIS_NONCE - 73 + i for i in range(128)]
    assert nonces[73] == GENESIS_NONCE
    o = BitSlicedDomainOracle(hdr, T)
    mask = o.phase_mask(nonces)
    assert mask == (1 << 73)
    assert hashlib_mask(hdr[:76], nonces, T) == mask
    # honest accounting: not 1 per pass
    assert o.telemetry.lanes == 128
    assert o.telemetry.bitsliced_lane_compressions == pytest.approx(128 * (61 + 61) / 64)
    assert o.telemetry.lane_compressions > o.telemetry.bitsliced_lane_compressions


@pytest.mark.parametrize("bits", [0x207fffff, 0x1f00ffff, 0x1d00ffff])
def test_phase_mask_bit_exact_under_difficulty(bits):
    hdr = genesis_header()
    T = target_from_bits(bits)
    h7, h6 = derive_early_abort_constraints(T)
    if bits == 0x207fffff:
        assert (h7, h6) == (1, 0)
    elif bits == 0x1f00ffff:
        assert (h7, h6) == (16, 0)
    else:
        assert (h7, h6) == (32, 0)
    rng = random.Random(bits)
    # one domain that contains the genesis nonce at a known lane, plus
    # several random 128-nonce domains (may or may not contain a hit)
    domains = [[GENESIS_NONCE - 73 + i for i in range(128)]]
    for _ in range(8):
        base = rng.randrange(0, 2**32 - 128)
        domains.append([base + i for i in range(128)])
    o = BitSlicedDomainOracle(hdr, T)
    for nonces in domains:
        mask = o.phase_mask(nonces)
        truth = hashlib_mask(hdr[:76], nonces, T)
        assert mask == truth  # zero false negatives and zero false positives


@pytest.mark.skipif(not HEADERS.exists(), reason="verified mainnet headers not available")
def test_phase_mask_bit_exact_on_all_500_headers():
    rows = json.loads(HEADERS.read_text())
    assert len(rows) == 500
    rng = random.Random(500)
    for i, r in enumerate(rows):
        hdr = bytes.fromhex(r["header_hex"])
        T = target_from_bits(int(r["bits"]))
        nonce = struct.unpack("<I", hdr[76:80])[0]
        # domain containing the winner at lane i % 128
        lane = i % 128
        base = (nonce - lane) & 0xFFFFFFFF
        nonces = [(base + j) & 0xFFFFFFFF for j in range(128)]
        assert nonces[lane] == nonce
        o = BitSlicedDomainOracle(hdr, T)
        mask = o.phase_mask(nonces)
        truth = hashlib_mask(hdr[:76], nonces, T)
        assert mask == truth, f"header {r['height']}"
        assert (mask >> lane) & 1, f"false negative on winner at height {r['height']}"
        # one extra random domain under the same target
        b2 = rng.randrange(0, 2**32 - 128)
        nonces2 = [b2 + j for j in range(128)]
        assert o.phase_mask(nonces2) == hashlib_mask(hdr[:76], nonces2, T)


def test_lane_oracle_hashes_every_lane_candidate():
    hdr = bytes(80)
    T = (1 << 256) >> 6  # ~1/64 of nonces satisfy
    res = u.unified_search(hdr, T, 0, 1024)
    processed = sum(r["candidates"] for r in res.lane_runs)
    assert res.distinct_nonces_hashed == processed
    assert processed >= 1
    # compressions are not "1 per bit-sliced pass"
    assert res.lane_compressions >= res.bitsliced_lane_compressions
    assert res.bitsliced_lane_compressions >= processed * 61 / 64


def test_lanes_are_m32_voronoi_partition():
    lanes = u.assign_lanes(1000, 512)
    assert sum(len(v) for v in lanes.values()) == 512
    for f, ns in lanes.items():
        assert all(pg.voronoi(n) == f for n in ns)


@pytest.mark.skipif(not HEADERS.exists(), reason="verified mainnet headers not available")
def test_recovers_true_winner_on_real_headers():
    rows = json.loads(HEADERS.read_text())[:8]
    for i, r in enumerate(rows):
        hdr = bytes.fromhex(r["header_hex"])
        nonce = struct.unpack("<I", hdr[76:80])[0]
        base = u.window_base_including_winner(nonce, 1024, hdr)
        res = u.unified_search(hdr, u.target_from_bits(r["bits"]), base, 1024)
        assert res.found_nonce == nonce
        h = pg.sha256d(hdr[:76] + struct.pack("<I", res.found_nonce))
        assert int.from_bytes(h, "little") <= u.target_from_bits(r["bits"])


@pytest.mark.skipif(not HEADERS.exists(), reason="verified mainnet headers not available")
def test_window_without_winner_returns_none():
    r = json.loads(HEADERS.read_text())[0]
    hdr = bytes.fromhex(r["header_hex"])
    nonce = struct.unpack("<I", hdr[76:80])[0]
    base = u.window_base_excluding_winner(nonce, 512)
    assert not (base <= nonce < base + 512)
    res = u.unified_search(hdr, u.target_from_bits(r["bits"]), base, 512)
    assert res.found_nonce is None
    assert res.distinct_nonces_hashed == 512


def test_lucas_enhanced_oracle_marks_only_solutions():
    from Intelligence.quantum_algorithms import GroverSearch

    g = GroverSearch(8)
    assert g.lucas_enhanced_oracle([200]) == [200]
    assert g.lucas_enhanced_oracle([200, 7, 7, 999]) == [7, 200]
    assert g.run(g.lucas_enhanced_oracle([200]))["peak_success_probability"] > 0.999


def test_lucas_adaptive_iterations_uses_pisot_phases():
    from Intelligence.quantum_algorithms import GroverSearch

    g = GroverSearch(12)
    assert g.lucas_adaptive_iterations(1) == g.optimal_iterations(4096, 1) == 50
    assert g.lucas_adaptive_iterations(1, lucas_index=3) == 53


def test_pool_kernel_score_uses_real_folded_state():
    from turing_universal_quantum_computer import grover_exact_scale as ges

    s = ges.pool_kernel_score(4096, 1)
    assert s["fold_state_bytes"] == 32 and s["fold_pair_ops"] == 16 and s["fold_bounded"]
