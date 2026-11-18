import pytest



def _fib_bytes(n: int) -> bytes:
    """[REVIEW FIX R5] Deterministic payload: Fibonacci mod 256 (Pisano period 384); replaces os.urandom."""
    out = bytearray(n)
    a, b = 0, 1
    for i in range(n):
        out[i] = a
        a, b = b, (a + b) & 0xFF
    return bytes(out)

from chronus.kernels.gl2_transform import (
    Folded,
    FoldStream,
    UnfoldStream,
    crc32c,
    fold,
    from_wire,
    hensellift_m15,
    invert_gl2_mod2k,
    to_wire,
    unfold,
)

pytestmark = pytest.mark.real


def test_hensel_lift_and_cayley_hamilton_across_rings() -> None:
    for k in (8, 16, 32, 64):
        mod = 1 << k
        mk = hensellift_m15(k)
        assert mk[0][0] % 256 == 219
        assert mk[0][1] % 256 == 98
        assert mk[1][1] % 256 == 121
        assert (mk[0][0] * mk[1][1] - mk[0][1] * mk[1][0]) % mod == mod - 1
        inv_mk = invert_gl2_mod2k(mk, k)
        assert (mk[0][0] * inv_mk[0][0] + mk[0][1] * inv_mk[1][0]) % mod == 1
        assert (mk[0][0] * inv_mk[0][1] + mk[0][1] * inv_mk[1][1]) % mod == 0
        assert (mk[1][0] * inv_mk[0][0] + mk[1][1] * inv_mk[1][0]) % mod == 0
        assert (mk[1][0] * inv_mk[0][1] + mk[1][1] * inv_mk[1][1]) % mod == 1


def test_exhaustive_bijection_and_gamma2_lsb_invariant() -> None:
    all_pairs = bytes(b for x in range(256) for y in range(256) for b in (x, y))
    folded = fold(all_pairs)
    assert len(folded) == 65536 * 2
    assert len(folded.data) == 65536 * 2
    # Every byte preserves its LSB because M15 === I_2 (mod 2)
    assert all((a & 1) == (b & 1) for a, b in zip(all_pairs, folded.data))
    assert unfold(folded) == all_pairs


# [REVIEW FIX R1] quotient-fiber test moved to tests/quotient_geometry_audit.py


def test_odd_padding_tampering_rejected() -> None:
    f = fold(b"ABC")
    assert len(f.data) == 4
    tampered = Folded(f.data[:-1] + bytes((f.data[-1] ^ 0x02,)), length=3)
    with pytest.raises(ValueError, match="canonical padding"):
        unfold(tampered)


def test_v2_wire_crc32c_and_v1_compat() -> None:
    assert crc32c(b"123456789") == 0xE3069283

    for msg in (b"", b"X", b"XY", b"CERN-HL-LHC", _fib_bytes(1025)):
        f = fold(msg)
        w2 = to_wire(f)
        assert unfold(from_wire(w2)) == msg

        # Any single-bit flip anywhere in header, payload, or CRC fails verification
        for idx in (0, 4, 15, len(w2) // 2, len(w2) - 1):
            corrupt = bytearray(w2)
            corrupt[idx] ^= 0x01
            with pytest.raises(ValueError):
                from_wire(corrupt)

        # Legacy v1 framing compatibility
        w1 = f.to_wire_v1()
        assert unfold(Folded.from_wire_v1(w1)) == msg


def test_chunked_streaming_roundtrip() -> None:
    for length in (0, 1, 2, 3, 17, 255, 4097):
        msg = _fib_bytes(length)
        enc = FoldStream()
        out_parts: list[bytes] = []
        pos = 0
        step = 1
        while pos < len(msg):
            out_parts.append(enc.update(msg[pos : pos + step]))
            pos += step
            step = (step % 11) + 1
        tail, footer = enc.finalize()
        wire = enc.header(len(msg)) + b"".join(out_parts) + tail + footer
        assert wire == to_wire(fold(msg))

        dec = UnfoldStream()
        rec_parts: list[bytes] = []
        for i in range(0, len(wire), 5):
            rec_parts.append(dec.update(wire[i : i + 5]))
        dec.finalize()
        assert b"".join(rec_parts) == msg

