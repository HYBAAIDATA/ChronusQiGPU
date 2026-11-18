"""Review additions: exact, deterministic (no RNG, no float) checks for the elevation."""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import shutil
import struct
import subprocess
import tempfile
import tracemalloc

import pytest

HERE = os.path.dirname(__file__)
from chronus.kernels import gl2_transform as g  # noqa: E402
from chronus.kernels.gl2_transform import (  # noqa: E402
    FoldedRegister7, FoldStream, UnfoldStream, _crc32c_combine, crc32c, fold,
    from_wire, hensellift_m15, invert_gl2_mod2k, to_wire, unfold,
)

pytestmark = pytest.mark.real

HEADERS = "/workspace/user_quantum_gpu_experiment/nonces500/headers.json"
I2 = ((1, 0), (0, 1))


def _mul(a, b, m):
    return (((a[0][0] * b[0][0] + a[0][1] * b[1][0]) % m, (a[0][0] * b[0][1] + a[0][1] * b[1][1]) % m),
            ((a[1][0] * b[0][0] + a[1][1] * b[1][0]) % m, (a[1][0] * b[0][1] + a[1][1] * b[1][1]) % m))


def _order_2group(a, m, k):
    p = a
    for j in range(k + 2):
        if p == I2:
            return 1 << j
        p = _mul(p, p, m)
    return None


def _fib_bytes(n: int) -> bytes:
    out = bytearray(n)
    a, b = 0, 1
    for i in range(n):
        out[i] = a
        a, b = b, (a + b) & 0xFF
    return bytes(out)


# ---------------------------------------------------------------- algebra
def test_hensel_k16_claim_and_gamma2_parity_and_order() -> None:
    assert hensellift_m15(16) == ((219, 98), (98, 39545))
    for k in (8, 16, 32, 64):
        m = 1 << k
        mk = hensellift_m15(k)
        assert (mk[0][0] * mk[1][1] - mk[0][1] * mk[1][0]) % m == m - 1          # det = -1
        assert tuple(tuple(e % 256 for e in r) for r in mk) == ((219, 98), (98, 121))  # = M15 mod 256
        assert tuple(tuple(e & 1 for e in r) for r in mk) == I2                     # Gamma(2): M_k = I mod 2
        assert _order_2group(mk, m, k) == 1 << (k - 1)                              # docstring claim
        inv = invert_gl2_mod2k(mk, k)
        tr = (mk[0][0] + mk[1][1]) % m
        assert inv == (((mk[0][0] - tr) % m, mk[0][1]), (mk[1][0], (mk[1][1] - tr) % m))  # CH: M - tr I
        assert _mul(mk, inv, m) == I2 and _mul(inv, mk, m) == I2


def test_lsb_invariance_exhaustive_k8_and_structural_k16() -> None:
    for x in range(256):
        for y in range(256):
            u, v = (219 * x + 98 * y) & 255, (98 * x + 121 * y) & 255
            assert (u & 1, v & 1) == (x & 1, y & 1)
    # k=16: (a x + b y) mod 2 = x mod 2 because a odd, b even (2^16 | 2^k keeps parity); check a grid
    mk = hensellift_m15(16)
    for i in range(65536):
        x, y = (i * 40503) & 0xFFFF, (i * 52429 + 1) & 0xFFFF
        u = (mk[0][0] * x + mk[0][1] * y) & 0xFFFF
        v = (mk[1][0] * x + mk[1][1] * y) & 0xFFFF
        assert (u & 1, v & 1) == (x & 1, y & 1)


def test_fibonacci_lift_q15_is_also_a_lift() -> None:
    """Q^15 = [[F16,F15],[F15,F14]] = [[987,610],[610,377]] has det -1 over Z (Cassini), so
    Q^15 mod 2^k is a second lift of M15 with trace L15 = 1364; same order 2^(k-1). Informational."""
    q15 = ((987, 610), (610, 377))
    assert 987 * 377 - 610 * 610 == -1 and 987 + 377 == 1364
    for k in (8, 16, 32, 64):
        m = 1 << k
        qk = tuple(tuple(e % m for e in r) for r in q15)
        assert tuple(tuple(e % 256 for e in r) for r in qk) == ((219, 98), (98, 121))
        assert _order_2group(qk, m, k) == 1 << (k - 1)
        assert (qk == hensellift_m15(k)) == (k == 8)


def test_m15_orbit_census() -> None:
    seen = bytearray(65536)
    census: dict[int, int] = {}
    for s in range(65536):
        if seen[s]:
            continue
        x, y, n = s >> 8, s & 255, 0
        while True:
            seen[(x << 8) | y] = 1
            n += 1
            x, y = (219 * x + 98 * y) & 255, (98 * x + 121 * y) & 255
            if (x << 8) | y == s:
                break
        census[n] = census.get(n, 0) + 1
    assert census == {1: 4, 2: 6, 4: 12, 8: 24, 16: 48, 32: 96, 64: 192, 128: 384}


# ---------------------------------------------------------------- CRC-32C
def test_crc32c_rfc3720_vectors_and_combine() -> None:
    assert crc32c(b"123456789") == 0xE3069283
    assert crc32c(bytes(32)) == 0x8A9136AA
    assert crc32c(b"\xff" * 32) == 0x62A8AB43
    assert crc32c(bytes(range(32))) == 0x46DD794E
    assert crc32c(bytes(range(31, -1, -1))) == 0x113FDB5C
    data = _fib_bytes(97)
    for cut in range(len(data) + 1):
        assert _crc32c_combine(crc32c(data[:cut]), crc32c(data[cut:]), len(data) - cut) == crc32c(data)
        assert crc32c(data[cut:], crc32c(data[:cut])) == crc32c(data)


# ---------------------------------------------------------------- wire & streaming
def test_every_single_bit_flip_rejected() -> None:
    for msg in (b"", b"X", b"XY", b"GOLD", _fib_bytes(9)):
        w = to_wire(fold(msg))
        for i in range(len(w)):
            for bit in range(8):
                c = bytearray(w)
                c[i] ^= 1 << bit
                with pytest.raises(ValueError):
                    from_wire(bytes(c))


def test_streaming_all_chunk_sizes() -> None:
    for n in range(0, 41):
        msg = _fib_bytes(n)
        wire = to_wire(fold(msg))
        for step in range(1, 21):
            enc = FoldStream()
            parts = [enc.update(msg[i:i + step]) for i in range(0, n, step)]
            tail, footer = enc.finalize()
            assert enc.header(n) + b"".join(parts) + tail + footer == wire
            dec = UnfoldStream()
            out = b"".join(dec.update(wire[i:i + step]) for i in range(0, len(wire), step))
            dec.finalize()
            assert out == msg


def test_500_mainnet_headers_roundtrip_and_hash() -> None:
    if not os.path.exists(HEADERS):
        pytest.skip("headers fixture not present")
    rows = json.load(open(HEADERS))
    assert len(rows) == 500
    for r in rows:
        h = bytes.fromhex(r["header_hex"])
        assert len(h) == 80
        assert unfold(from_wire(to_wire(fold(h)))) == h
        assert hashlib.sha256(hashlib.sha256(unfold(fold(h))).digest()).digest()[::-1].hex() == r["id"]
        assert struct.unpack("<I", h[76:80])[0] == r["nonce_api"]


def test_genesis_header() -> None:
    gen = bytes.fromhex(
        "01000000" + "00" * 32
        + "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a"
        + "29ab5f49" + "ffff001d" + "1dac2b7c")
    assert struct.unpack("<I", gen[76:])[0] == 2083236893
    assert hashlib.sha256(hashlib.sha256(unfold(fold(gen))).digest()).digest()[::-1].hex() == \
        "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"


# ---------------------------------------------------------------- native C parity & zero copy
def _build(flags: list[str]) -> str | None:
    cc = shutil.which("gcc")
    if cc is None:
        return None
    d = tempfile.mkdtemp()
    so = os.path.join(d, "lib.so")
    subprocess.run([cc, "-O3", *flags, "-Wall", "-Wextra", "-Werror", "-shared", "-fPIC",
                    os.path.join(HERE, "..", "src", "chronus", "kernels", "gl2_fast.c"), "-o", so], check=True)
    return so


@pytest.mark.parametrize("flags", [["-march=native"], ["-mno-avx2", "-mno-sse4.2"]])
def test_native_kernel_bit_exact(flags: list[str]) -> None:
    so = _build(flags)
    if so is None:
        pytest.skip("no gcc")
    lib = ctypes.CDLL(so)
    assert not hasattr(lib, "gl2_fold_truncated_pairs")
    for fn in (lib.gl2_fold_pairs, lib.gl2_unfold_pairs):
        fn.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t]
    lib.gl2_crc32c.argtypes = [ctypes.c_uint32, ctypes.c_char_p, ctypes.c_size_t]
    lib.gl2_crc32c.restype = ctypes.c_uint32
    src = bytes(b for x in range(256) for y in range(256) for b in (x, y))
    for n_pairs in (65536, 65535, 17, 16, 15, 1):  # SIMD body + scalar tail
        s = src[: 2 * n_pairs]
        f = ctypes.create_string_buffer(2 * n_pairs)
        u = ctypes.create_string_buffer(2 * n_pairs)
        lib.gl2_fold_pairs(s, f, n_pairs)
        lib.gl2_unfold_pairs(f.raw, u, n_pairs)
        assert f.raw == fold(s).data
        assert u.raw == s
    for n in range(0, 200):
        d = _fib_bytes(n)
        assert lib.gl2_crc32c(0, d, n) == crc32c(d)
        assert lib.gl2_crc32c(0x12345678, d, n) == crc32c(d, 0x12345678)


def test_buffer_address_zero_copy() -> None:
    b = _fib_bytes(1 << 20)
    v = memoryview(b)
    a0 = g._buffer_address(v)
    assert ctypes.string_at(a0, 64) == b[:64]
    assert g._buffer_address(v[1000:]) == a0 + 1000           # slice: same memory, no copy
    ba = bytearray(b)
    assert g._buffer_address(memoryview(ba), writable=True) == ctypes.addressof(
        (ctypes.c_char * len(ba)).from_buffer(ba))
    with pytest.raises(BufferError):
        g._buffer_address(v, writable=True)                    # read-only must not be written
    tracemalloc.start()
    for _ in range(8):
        g._buffer_address(v[123:])
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert peak < 16384                                         # no N-sized (1 MiB) allocation


# ---------------------------------------------------------------- FoldedRegister7
def _state(r: FoldedRegister7, x: int) -> tuple[int, int]:
    """Value of virtual state x: base + sum of the generators selected by x (reference only)."""
    mask = (1 << r.k) - 1
    u, v = r.base
    for j in range(7):
        if (x >> j) & 1:
            u, v = (u + r.generators[j][0]) & mask, (v + r.generators[j][1]) & mask
    return (u, v)


def test_folded_register7_fold_roundtrip_and_commutation() -> None:
    domain_base = 0x7C2B1000
    target = 0b1011010
    for k in (8, 16):
        mask = (1 << k) - 1
        r = FoldedRegister7.from_domain_offset(domain_base, k=k)
        f = r.fold_mk()
        assert f.unfold_mk() == r and r.unfold_mk().fold_mk() == r
        for idx in range(7):
            for b in (0, 1):
                assert r.collapse_generator(idx, b).fold_mk() == f.collapse_generator(idx, b)
        assert f.collapse_generator(3, 1).active_dimension == 6
        c = f
        for j in range(7):
            c = c.collapse_generator(j, (target >> j) & 1)
        assert c.active_dimension == 0
        exp = domain_base + target
        x, folded_base = c.readout_winner()          # readout returns the base as-is (folded here)
        assert x == target and c.unfold_mk().readout_winner() == (target, ((exp >> k) & mask, exp & mask))


@pytest.mark.parametrize("k", [8, 16])
def test_folded_register7_exhaustive_128(k: int) -> None:
    mask = (1 << k) - 1
    mk = hensellift_m15(k)
    rows = json.load(open(HEADERS)) if os.path.exists(HEADERS) else [{"nonce_api": 2083236893}]
    for nonce in [2083236893] + [r["nonce_api"] for r in rows[:20]]:
        base = nonce & ~0x7F
        r = FoldedRegister7.from_domain_offset(base, k=k)
        f = r.fold_mk()
        for x in range(128):
            want = base + x
            plain = ((want >> k) & mask, want & mask)
            assert _state(r, x) == plain
            assert _state(f, x) == ((mk[0][0] * plain[0] + mk[0][1] * plain[1]) & mask,
                                    (mk[1][0] * plain[0] + mk[1][1] * plain[1]) & mask)
            c = f
            for j in (3, 0, 6, 1, 5, 2, 4):        # order-independent collapse
                c = c.collapse_generator(j, (x >> j) & 1)
            assert c.unfold_mk().readout_winner() == (x, plain)
        x = nonce & 0x7F
        c = f
        for j in range(7):
            c = c.collapse_generator(j, (x >> j) & 1)
        assert c.unfold_mk().readout_winner()[1] == (((nonce >> k) & mask), nonce & mask)


def test_folded_register7_bad_input_and_documented_wrap() -> None:
    r = FoldedRegister7.from_domain_offset(0).collapse_generator(0, 1)
    with pytest.raises(ValueError):
        r.collapse_generator(0, 0)                  # contradictory collapse
    with pytest.raises(RuntimeError):
        r.readout_winner()                          # generators still active
    # Documented behaviour (no raise by design): with nonzero low 7 bits the offset wraps inside
    # lane1 (mod 2^k) instead of carrying into lane0.
    w = FoldedRegister7.from_domain_offset(0x7C2B10FF)
    assert _state(w, 1) == (0x10, 0x00)            # 0x...10FF + 1 -> lane1 wraps to 0x00, lane0 stays 0x10


def test_unaligned_and_readonly_views_match_reference() -> None:
    src = _fib_bytes(4099)
    ref_ba = bytearray(src)
    for off in range(0, 5):
        v = memoryview(src)[off:]
        f = fold(v)
        assert f == fold(bytes(v)) == fold(bytearray(v)) == fold(memoryview(ref_ba)[off:])
        assert unfold(f) == bytes(v)
        assert crc32c(v) == crc32c(bytes(v)) == crc32c(memoryview(ref_ba)[off:])
