"""Triad Grover at k=32: FoldedRegisterN, Lucas-Pisano schedule, OVID/THESEUS custody,
exact two-amplitude Grover.  Exact integer / Fraction arithmetic throughout."""
from __future__ import annotations

import sqlite3
import struct
from fractions import Fraction

import pytest

from chronus.geodesic.scheduler import (
    exact_fibonacci_lucas, exact_fibonacci_lucas_mod, hamming_step_histogram,
    lucas_pisano_geodesic_order, pisano_period_pow2, schedule_parameters,
)
from chronus.kernels import gl2_transform as gl2
from chronus.kernels.gl2_transform import FoldedRegister7, FoldedRegisterN, hensellift_m15, invert_gl2_mod2k
from chronus.security.al_haras.golden import fibonacci, lucas
from chronus.ovid.folded_custody import (
    OvidAdapter, OvidFoldedAdapter, TheseusAdapter, attest, verify_attested,
)
from chronus.ovid.transform import OvidTransformService
from chronus.execution.sha256d_oracle import Sha256dTargetOracle, sha256d, target_from_bits
from chronus.quantum.triad_grover import (
    _full_vector_step, _two_amplitude_step, exact_grover_two_amplitude_trajectory,
    exact_lucas_pisot_iterations, run_triad_exact_grover_search,
)
from chronus.storage.durable import DurableTheseusService
from chronus.storage.theseus import StorageIntegrityError
from chronus.triad import open_production_triad

pytestmark = pytest.mark.real

GENESIS = bytes.fromhex(
    "0100000000000000000000000000000000000000000000000000000000000000000000003ba3edfd7a7b12b27a"
    "c72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a29ab5f49ffff001d1dac2b7c")
GENESIS_NONCE = 2083236893
GENESIS_ID = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
MAINNET = [  # (height, header, bits, block id) - offline fixtures
    (976064, "008004204010b28c77fee52469c01ea7255cbf15fee39a8fdfc00000000000000000000074a9b08a10bfd7fffaa942d39c6de8e61cb0f250367ab50be99b0351e4d035926676fa6a73160217476f6405",
     386012787, "00000000000000000001c06ea254f586aa8976278188c11fbc4231b19aa6a8de"),
    (976063, "00207f27f71edaa4fe1a0af06be095fa956e79d251e51446abb7000000000000000000002d21eaf2e450a45825fb1c83e1fc041f53120ffc32107474e91ab440909c40f56574fa6a731602175a6b6e4b",
     386012787, "00000000000000000000c0df8f9ae3fe15bf5c25a71ec06924e5fe778cb21040"),
    (976062, "0000f827bb88c3193effa06cd788f6fce2dd022919dd56625b7000000000000000000000dc542ed725f82895561e7bae5bfb30e58b8264b421e1e4702c3201b8d017cf5c5d72fa6a731602172a3f941b",
     386012787, "00000000000000000000b7ab4614e551d2796e95fa95e06bf00a1afea4da1ef7"),
]
I2 = ((1, 0), (0, 1))


def _mul(a, b, m):
    return tuple(tuple(sum(a[i][t] * b[t][j] for t in range(2)) % m for j in range(2)) for i in range(2))


def _pow(a, e, m):
    r = I2
    while e:
        if e & 1:
            r = _mul(r, a, m)
        a = _mul(a, a, m)
        e >>= 1
    return r


# ---------------------------------------------------------------- exact Grover
@pytest.mark.parametrize("n,m,k", [(16, 1, 3), (4096, 1, 50), (65536, 1, 201), (4, 1, 1),
                                   (4096, 2, 35), (4096, 4, 25), (65536, 2, 142), (65536, 4, 100)])
def test_peak_iterations(n, m, k):
    assert exact_lucas_pisot_iterations(n, m) == k


def test_peak_probability_n16_exact():
    t, alpha, beta, p = exact_grover_two_amplitude_trajectory(16, 1)[-1]
    assert (t, alpha, beta) == (3, Fraction(251, 64), Fraction(-13, 64))   # scaled by sqrt(16)
    assert p == Fraction(63001, 65536)
    # independent: sin^2(7x), sin x = 1/4, via sin 7x = 7s - 56s^3 + 112s^5 - 64s^7 (exact)
    s = Fraction(1, 4)
    assert p == (7 * s - 56 * s**3 + 112 * s**5 - 64 * s**7) ** 2


@pytest.mark.parametrize("n", [4, 16, 64])
def test_two_amplitude_equals_full_vector_every_step(n):
    for marked_set in ({0}, {1, n - 1}, set(range(0, n, 3))):
        marked = [i in marked_set for i in range(n)]
        m = len(marked_set)
        vec, a, b = [Fraction(1)] * n, Fraction(1), Fraction(1)
        for _ in range(exact_lucas_pisot_iterations(n, m) + 3):
            vec = _full_vector_step(vec, marked)
            a, b = _two_amplitude_step(a, b, n, m)
            assert all(v == (a if mk else b) for v, mk in zip(vec, marked))
            assert m * a * a + (n - m) * b * b == n


def test_isqrt_bound_never_truncates_peak():
    for d in range(1, 15):
        for m in (1, 2, 3, 5):
            if m < (1 << d):
                exact_grover_two_amplitude_trajectory(1 << d, m)   # raises if the bound cut the walk


# ---------------------------------------------------------------- scheduler
def test_fast_doubling_matches_repo_golden():
    a, b = 0, 1                                   # plain iteration as a second reference
    for n in range(1001):
        assert exact_fibonacci_lucas(n)[0] == a
        a, b = b, a + b
    for n in range(1001):
        f, l = exact_fibonacci_lucas(n)
        assert (f, l) == (fibonacci(n), lucas(n))
        assert (l % 2 == 0) == (n % 3 == 0)
        assert exact_fibonacci_lucas_mod(n, 1 << 24) == (f % (1 << 24), l % (1 << 24))


def test_pisano_period_is_minimal():
    for d in range(1, 13):
        m, p = 1 << d, pisano_period_pow2(d)
        seq, a, b = [], 0, 1
        for _ in range(2 * p):
            seq.append(a)
            a, b = b, (a + b) % m
        assert seq[:p] == seq[p:] and all(seq[q:q + 2] != [0, 1] for q in range(1, p))


@pytest.mark.parametrize("d", range(1, 13))
def test_schedule_bijection_and_pisano_wrap(d):
    pi = pisano_period_pow2(d)
    for e in sorted({0, 1, 2, 5, pi - 1, pi, pi + 1}):
        o = lucas_pisano_geodesic_order(d, epoch_step=e)
        assert sorted(o) == list(range(1 << d))
    assert lucas_pisano_geodesic_order(d, epoch_step=1) == lucas_pisano_geodesic_order(d, epoch_step=1 + pi)
    for d2 in range(13, 25):
        assert schedule_parameters(d2, 1)["lucas_stride_mod"] % 2 == 1


def test_hamming_steps_unit_only_for_stride_one():
    assert hamming_step_histogram(lucas_pisano_geodesic_order(12, epoch_step=0)) == {1: 4095}
    assert set(hamming_step_histogram(lucas_pisano_geodesic_order(12, epoch_step=1))) != {1}


# ---------------------------------------------------------------- FoldedRegisterN
@pytest.mark.parametrize("k", (8, 16, 32, 64))
def test_mk_order_and_cayley_hamilton(k):
    m, M = 1 << k, hensellift_m15(k)
    assert _pow(M, 1 << (k - 1), m) == I2 and _pow(M, 1 << (k - 2), m) != I2
    tr = (M[0][0] + M[1][1]) % m
    assert invert_gl2_mod2k(M, k) == (((M[0][0] - tr) % m, M[0][1]), (M[1][0], (M[1][1] - tr) % m))


@pytest.mark.parametrize("k,n", [(16, 16), (32, 16), (32, 32), (64, 64)])
def test_register_n_bijection_commute_wire(k, n):
    reg = FoldedRegisterN.from_domain_offset(0x7C2B10005A5A5A5A % (1 << (2 * k)), num_generators=n, k=k)
    assert reg.fold_mk().unfold_mk() == reg == reg.unfold_mk().fold_mk()
    for j in range(n):
        for b in (0, 1):
            assert reg.fold_mk().collapse_generator(j, b) == reg.collapse_generator(j, b).fold_mk()
    f = reg.fold_mk().collapse_generator(0, 1)
    blob = f.to_wire_bytes()
    assert blob[:4] == b"GL2\x01" and FoldedRegisterN.from_wire_bytes(blob) == f
    bad = bytearray(blob)
    bad[20] ^= 1
    with pytest.raises(ValueError):
        FoldedRegisterN.from_wire_bytes(bytes(bad))


def test_register_n_wrap_and_guards():
    reg = FoldedRegisterN.from_domain_offset((0xDEADBEEF << 32) | 0xFFFFFFF0, num_generators=8, k=32)
    assert all(reg.evaluate_index(i) == (0xDEADBEEF, (0xFFFFFFF0 + i) & 0xFFFFFFFF) for i in range(256))
    with pytest.raises(ValueError):
        FoldedRegisterN.from_domain_offset(0, num_generators=9, k=8)
    with pytest.raises(ValueError):
        FoldedRegisterN.from_domain_offset(0, num_generators=4, k=12)


def test_register7_untouched_and_no_lossy_exports():
    for k in (8, 16):
        r7 = FoldedRegister7.from_domain_offset(0x7C2B1000, k=k).fold_mk()
        rn = FoldedRegisterN.from_domain_offset(0x7C2B1000, num_generators=7, k=k).fold_mk()
        assert (r7.base, r7.generators) == (rn.base, rn.generators)
    assert not any(hasattr(gl2, s) for s in ("fold_truncated", "trunc_fiber", "FLAG_TRUNCATED"))


# ---------------------------------------------------------------- OVID / THESEUS
def _adapter(path, tenant="t"):
    custody = DurableTheseusService(str(path / "theseus.sqlite3"))
    store = TheseusAdapter(custody, tenant)
    return custody, store, OvidFoldedAdapter(OvidAdapter(OvidTransformService()), store)


def test_ovid_selective_materialise_equals_full(tmp_path):
    _, _, ad = _adapter(tmp_path)
    h = ad.stage_domain("a", FoldedRegisterN.from_domain_offset((7 << 32) | 0xFFFFFE00, num_generators=10, k=32))
    full = ad.full_reconstruct(h)
    assert ad.materialise_indices(h, list(range(1024))) == full
    assert full == [(7 << 32) | ((0xFFFFFE00 + i) & 0xFFFFFFFF) for i in range(1024)]
    assert h.shard_ref["shard_id"] == "a:v0"


def test_theseus_restart_recovery(tmp_path):
    _, _, ad = _adapter(tmp_path)
    reg = FoldedRegisterN.from_domain_offset(1 << 40, num_generators=8, k=32)
    h = ad.commit_collapse_step(ad.commit_collapse_step(ad.stage_domain("c", reg), 2, 1), 7, 0)
    del ad
    custody2, store2, ad2 = _adapter(tmp_path)
    r = ad2.restore_from_theseus("c")
    assert (r.version, r.register, r.wire_frame) == (2, h.register, h.wire_frame)
    assert custody2.verify_journal_continuity("t")
    ad2.stage_domain("c2", reg)
    assert store2.counters.shards_reused == 1


def test_tamper_rejection(tmp_path):
    body = attest({"event": "X", "v": 1})
    with pytest.raises(ValueError):
        verify_attested(dict(body, v=2))
    custody, _, ad = _adapter(tmp_path)
    h = ad.stage_domain("d", FoldedRegisterN.from_domain_offset(5, num_generators=4, k=32))
    con = sqlite3.connect(custody.path)
    con.execute("UPDATE objects SET payload=? WHERE object_id=?", (b"\x00" * 10, h.shard_ref["object_id"]))
    con.commit()
    con.close()
    with pytest.raises(StorageIntegrityError):
        custody.reconstruct("t", h.shard_ref["object_id"])


# ---------------------------------------------------------------- end to end
def test_genesis_through_production_triad(tmp_path):
    tri = open_production_triad(tmp_path)
    out = tri.exact_grover_search("g", GENESIS[:76], target_from_bits(0x1D00FFFF), GENESIS_NONCE - 100, num_generators=8)
    r = out["result"]
    assert r.found and out["nonce"] == GENESIS_NONCE and out["digest"] == GENESIS_ID and r.marked_count == 1
    assert out["oracle_evaluations"] == 256 and r.handle_version == 8 and r.full_vector_checked is False
    assert tri.theseus.verify_journal_continuity("g")


@pytest.mark.parametrize("height,header,bits,block_id", MAINNET)
def test_mainnet_window_and_overfit(tmp_path, height, header, bits, block_id):
    h = bytes.fromhex(header)
    nonce = struct.unpack("<I", h[76:80])[0]
    tri = open_production_triad(tmp_path)
    hit = tri.exact_grover_search("m", h[:76], target_from_bits(bits), nonce - 1000, num_generators=12)
    assert hit["result"].found and hit["nonce"] == nonce and hit["digest"] == block_id == sha256d(h)[::-1].hex()
    miss = tri.exact_grover_search("m", h[:76], target_from_bits(bits), (nonce + 4096) & 0xFFFFFFFF, num_generators=12)
    assert not miss["result"].found and miss["result"].marked_count == 0 and miss["oracle_evaluations"] == 4096


def test_small_domain_full_vector_crosscheck(tmp_path):
    _, _, ad = _adapter(tmp_path)
    h = ad.stage_domain("s", FoldedRegisterN.from_domain_offset(100, num_generators=5, k=32))
    r = run_triad_exact_grover_search(adapter=ad, handle=h, oracle_predicate=lambda v: (v & 0xFFFFFFFF) in (103, 117))
    assert r.found and r.full_vector_checked and r.marked_count == 2
    assert (r.winner_value & 0xFFFFFFFF) in (103, 117)


def test_winner_index_keeps_pre_collapsed_bits(tmp_path):
    """Regression: a handle with generators already resolved to 1 must report the
    full register index (resolved bits | active winner bits), and the collapsed
    read-out must agree with it."""
    _, _, ad = _adapter(tmp_path)
    h = ad.stage_domain("p", FoldedRegisterN.from_domain_offset(1000, num_generators=6, k=32))
    for j, b in ((1, 1), (3, 1), (4, 0)):
        h = ad.commit_collapse_step(h, j, b)
    assert h.register.resolved_bits == 0b001010 and h.register.resolved_mask == 0b011010
    target = 1000 + 0b101011                     # active bits 0 and 5 set, plus resolved 1 and 3
    r = run_triad_exact_grover_search(adapter=ad, handle=h, oracle_predicate=lambda v: (v & 0xFFFFFFFF) == target)
    assert r.found and r.active_dim == 3 and r.states == 8 and r.marked_count == 1
    assert r.winner_index == 0b101011
    assert r.winner_value & 0xFFFFFFFF == target


def test_determinism_and_guards(tmp_path):
    h = bytes.fromhex(MAINNET[0][1])
    nonce = struct.unpack("<I", h[76:80])[0]
    outs = []
    for sub in ("a", "b"):
        (tmp_path / sub).mkdir()
        tri = open_production_triad(tmp_path / sub)
        o = tri.exact_grover_search("d", h[:76], target_from_bits(MAINNET[0][2]), nonce - 7, num_generators=10)
        st = TheseusAdapter(tri.theseus, "d")
        outs.append((o["result"].winner_value, o["result"].total_marked_probability,
                     [rec for _e, rec in st.journal_receipts(("OVID_FOLDED_STAGE", "OVID_GENERATOR_COLLAPSE",
                                                              "GROVER_TARGET_VERIFIED"))]))
    assert outs[0] == outs[1]
    _, _, ad = _adapter(tmp_path / "a")
    hd = ad.stage_domain("z", FoldedRegisterN.from_domain_offset(0, num_generators=2, k=32))
    with pytest.raises(ValueError):
        run_triad_exact_grover_search(adapter=ad, handle=hd, oracle_predicate=lambda v: False, geodesic_order=[0, 0, 1, 2])
    for j in range(2):
        hd = ad.commit_collapse_step(hd, j, 0)
    with pytest.raises(ValueError):
        run_triad_exact_grover_search(adapter=ad, handle=hd, oracle_predicate=lambda v: False)


def test_oracle_counts_every_evaluation():
    o = Sha256dTargetOracle(GENESIS[:76], target_from_bits(0x1D00FFFF))
    assert o((o.ntime << 32) | GENESIS_NONCE) and not o((o.ntime << 32) | 1)
    assert (o.evaluations, o.midstates, o.compressions) == (2, 1, 5)
