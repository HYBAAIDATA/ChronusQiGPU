"""Golden-stride (ASIC-like) traversal gates.

nonce_i = (seed + i·⌊2³²/φ⌋) mod 2³² — an odd stride, so the walk is a
bijection over the nonce domain: full coverage, header-seeded order, no
nonce upload. sha256d ≤ target stays the sole accept authority on every
path.
"""

import hashlib
import struct

import pytest

from hyba.inventory import DeviceInfo
from hyba.math_ir.emit_cpu import _GOLDEN_STRIDE, emit_cpu
from hyba.math_ir.emit_opencl import emit_opencl
from hyba.math_ir.executor import IRExecutor
from hyba.math_ir.specs import get_spec
from mining.bitcoin_hasher import BitcoinHasher

REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]


def _cpu_device() -> DeviceInfo:
    return DeviceInfo(
        name="CPU (hashlib)",
        vendor="test",
        backend="cpu",
        type="cpu",
        compute_units=8,
        global_mem_mb=None,
        capabilities=(("hashlib_sha256d", True),),
    )


def _header(seed_byte: int = 0) -> bytes:
    return bytes([seed_byte]) * 76


def _walk(seed: int, count: int):
    return [(seed + i * _GOLDEN_STRIDE) & 0xFFFFFFFF for i in range(count)]


def test_stride_constant_is_odd_floor_phi():
    import math

    assert _GOLDEN_STRIDE == int(math.floor(2**32 / ((1 + math.sqrt(5)) / 2)))
    assert _GOLDEN_STRIDE % 2 == 1  # odd ⇒ coprime with 2^32 ⇒ bijective


def test_walk_is_unique_per_window():
    """Every probe index maps to a distinct nonce — full coverage, no skips."""
    seq = _walk(seed=12345, count=200_000)
    assert len(set(seq)) == len(seq)


def test_emit_opencl_finds_canonical_entry():
    em = emit_opencl("sha256d_gold")
    assert "__kernel void bitcoin_sha256d_gold" in em.source
    assert em.entry == "bitcoin_sha256d_gold"


def test_cpu_oracle_matches_hashlib_walk():
    """The spec's oracle must hash exactly what it claims to hash."""
    header = _header(7)
    run = emit_cpu("sha256d_gold")
    target = int(2**256 * 0.9)
    out = run({"header": header, "seed": 0xABCDEF, "count": 64, "target": target}, {})
    assert out["hashes"] == 64
    for nonce in out["hits"]:
        blob = header + struct.pack("<I", nonce)
        d = hashlib.sha256(hashlib.sha256(blob).digest()).digest()
        assert int.from_bytes(d, "little") <= target
    # winner is the first hit in probe order
    if out["hits"]:
        assert out["winning_nonce"] == out["hits"][0]


def test_grind_target_gold_cpu_path():
    hasher = BitcoinHasher(backend="cpu")
    assert hasher.backend == "cpu"
    header = _header(3) + b"\x00" * 4
    target = (int(2**256 * 0.5)).to_bytes(32, "big")
    seed = hasher.gold_seed(header, target)
    win, digest, hashes, hits = hasher.grind_target_gold(header, target, 4096, seed)
    assert hashes == 4096
    assert win is not None
    blob = bytearray(header)
    struct.pack_into("<I", blob, 76, win)
    d = hashlib.sha256(hashlib.sha256(bytes(blob)).digest()).digest()
    assert d == digest
    # winner is the first hit under the golden walk order
    expected_hits = []
    for n in _walk(seed, 4096):
        blob2 = bytearray(header)
        struct.pack_into("<I", blob2, 76, n)
        if int.from_bytes(
            hashlib.sha256(hashlib.sha256(bytes(blob2)).digest()).digest(),
            "little",
        ) <= int.from_bytes(target, "big"):
            if len(expected_hits) < 8:
                expected_hits.append(n)
    assert hits == expected_hits
    assert win == expected_hits[0]


def test_grind_target_gold_deterministic_seed():
    h1 = _header(9) + b"\x00" * 4
    t = (int(2**256 * 0.5)).to_bytes(32, "big")
    assert BitcoinHasher.gold_seed(h1, t) == BitcoinHasher.gold_seed(h1, t)
    h2 = _header(10) + b"\x00" * 4
    assert BitcoinHasher.gold_seed(h1, t) != BitcoinHasher.gold_seed(h2, t)


def test_executor_oracle_rechecks_gold_winner():
    """Executor-level: a gold winner is hashlib-reverified; a lie raises."""
    cpu = _cpu_device()
    ex = IRExecutor(cpu, "sha256d_gold").compile()
    header = _header(5)
    target = int(2**256 * 0.5)
    res = ex.run(
        {"header": header, "seed": 42, "count": 512, "target": target},
        {"lucas_dispatch": {"rungs": []}},
    )
    assert res.spec_name == "sha256d_gold"
    if res.outputs["winning_nonce"] is not None:
        assert res.oracle_checked is True
        blob = header + struct.pack("<I", res.outputs["winning_nonce"])
        d = hashlib.sha256(hashlib.sha256(blob).digest()).digest()
        assert int.from_bytes(d, "little") <= target


def test_gold_spec_registered_with_exact_oracle():
    spec = get_spec("sha256d_gold")
    assert spec.precision_bound == "exact"
    assert spec.canonical_source == "kernels/bitcoin_sha256d.cl"
    assert spec.executor == "bitcoin_hasher"


def test_opencl_device_path_skipped_without_silicon():
    """On a host with OpenCL, grind_target_gold on device must equal the
    CPU oracle's hit list — otherwise honestly NOT_RUN."""
    try:
        import pyopencl as cl

        devices = [d for p in cl.get_platforms() for d in p.get_devices()]
    except Exception:
        devices = []
    if not devices:
        pytest.skip("NOT_RUN: no OpenCL device on this host")
    hasher = BitcoinHasher(backend="opencl")
    if hasher.backend == "cpu":
        pytest.skip(f"NOT_RUN: OpenCL init failed ({hasher.fallback_reason})")
    header = _header(11) + b"\x00" * 4
    target = (int(2**256 * 0.5)).to_bytes(32, "big")
    seed = 777
    w_dev, d_dev, n_dev, hits_dev = hasher.grind_target_gold(
        header, target, 4096, seed
    )
    cpu = BitcoinHasher(backend="cpu")
    w_cpu, d_cpu, n_cpu, hits_cpu = cpu.grind_target_gold(
        header, target, 4096, seed
    )
    assert (w_dev, d_dev, n_dev) == (w_cpu, d_cpu, n_cpu)
    assert sorted(hits_dev) == sorted(hits_cpu)


# ---------------------------------------------------------------------------
# Elevations: lemma signoff, observable audit, FIFO derivation, silicon gate
# ---------------------------------------------------------------------------


def test_golden_stride_lemma_verifies():
    """The bijection proof is executed: gcd(odd stride, 2^32) == 1."""
    from hyba.operating_model.lemma import verify_golden_stride

    rec = verify_golden_stride()
    assert rec[0]["verdict"] == "HOLDS"
    assert rec[0]["theorem_proven"] is False


def test_resonance_ordering_lemma_verifies():
    """Header-dependent permutation, executed on deterministic vectors."""
    from hyba.operating_model.lemma import verify_resonance_ordering

    rec = verify_resonance_ordering()
    assert rec[0]["verdict"] == "HOLDS"
    assert rec[0]["theorem_proven"] is False


def test_ordering_lemma_scope_guard():
    from hyba.operating_model.lemma import (
        ScopeViolation,
        use_ordering_lemma,
        GOLDEN_STRIDE,
    )

    assert use_ordering_lemma(
        "order_device_probe_walk", lemma="golden_stride_bijection"
    )["authorized"] is True
    with pytest.raises(ScopeViolation):
        use_ordering_lemma("order_device_probe_walk", stride=0xDEADBEEF,
                           lemma="golden_stride_bijection")
    with pytest.raises(ScopeViolation):
        use_ordering_lemma("order_device_probe_walk")
    with pytest.raises(ScopeViolation):
        use_ordering_lemma("predict_sha256d_output")
    assert GOLDEN_STRIDE == _GOLDEN_STRIDE == 0x9E3779B9


def test_ordering_lemmas_signoff_written():
    """require_ordering_lemmas executes the verifications and pins the
    signoff sha to the doc — editing the doc re-opens the gate."""
    from hyba.operating_model import lemma as lemma_mod

    rec = lemma_mod.require_ordering_lemmas(write=True)
    assert rec["theorem_proven"] is False
    assert lemma_mod.ordering_lemmas_signed() is True


def test_fifo_depth_is_derived_not_magic():
    """GOLD_FIFO_DEPTH = fib(6) = 8 — drawn from the Lucas pool; the
    kernel literal must equal it."""
    import re

    from lucas.core import fibonacci

    assert BitcoinHasher.GOLD_FIFO_DEPTH == fibonacci(6) == 8
    src = (REPO_ROOT / "kernels" / "bitcoin_sha256d.cl").read_text()
    m = re.search(r"#define GOLD_FIFO_DEPTH (\d+)u", src)
    assert m and int(m.group(1)) == BitcoinHasher.GOLD_FIFO_DEPTH


def test_silicon_status_honest_without_device():
    """device_run reports NOT_RUN on the CPU oracle path — the kernel is
    a hypothesis until silicon executes it."""
    hasher = BitcoinHasher(backend="cpu")
    st = hasher.silicon_status()
    assert st["device_run"] == "NOT_RUN"
    assert st["theorem_proven"] is False
    assert st["fifo_depth"] == 8
