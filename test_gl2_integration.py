import sys
sys.path.insert(0, r'd:\chronus-quantum-igpu\src')

from chronus.kernels.gl2_transform import (
    hensellift_m15, invert_gl2_mod2k, M15, M15_INV,
    trunc_fiber, fold, unfold, crc32c, Folded
)

print("Imports OK")

# Test Hensel lift across rings
for k in (8, 16, 32, 64):
    mk = hensellift_m15(k)
    assert mk[0][0] % 256 == 219
    assert mk[0][1] % 256 == 98
    assert mk[1][1] % 256 == 121
    det = (mk[0][0] * mk[1][1] - mk[0][1] * mk[1][0]) % (1 << k)
    assert det == (1 << k) - 1, f"det failed for k={k}: {det}"
    inv_mk = invert_gl2_mod2k(mk, k)
    assert (mk[0][0] * inv_mk[0][0] + mk[0][1] * inv_mk[1][0]) % (1 << k) == 1
    assert (mk[0][0] * inv_mk[0][1] + mk[0][1] * inv_mk[1][1]) % (1 << k) == 0
    assert (mk[1][0] * inv_mk[0][0] + mk[1][1] * inv_mk[1][0]) % (1 << k) == 0
    assert (mk[1][0] * inv_mk[0][1] + mk[1][1] * inv_mk[1][1]) % (1 << k) == 1
    print(f"k={k}: OK")

# Test basic fold/unfold
for msg in (b"", b"A", b"AB", b"CERN-TDAQ-2026"):
    f = fold(msg)
    assert unfold(f) == msg
    print(f"fold/unfold {msg!r}: OK")

# Test trunc_fiber
for u in (0, 1, 42, 128, 255):
    fib = list(trunc_fiber(u))
    assert len(fib) == 256
    assert len(set(fib)) == 256
    for x, y in fib:
        assert (219 * x + 98 * y) % 256 == u
    print(f"trunc_fiber({u}): OK")

# Test Folded wire
import os
for msg in (b"", b"X", b"XY", b"LHC-Run4-HL", os.urandom(1023)):
    f = fold(msg)
    w2 = f.to_wire()
    f2 = Folded.from_wire(w2)
    assert f2 == f and unfold(f2) == msg
    # Flip 1 bit and verify rejection
    tampered = bytearray(w2)
    tampered[-5] ^= 0x01
    try:
        Folded.from_wire(tampered)
        assert False, "Should have detected bit flip!"
    except ValueError:
        pass
    print(f"wire CRC tamper {msg!r}: OK")

print("\nALL TESTS PASSED!")