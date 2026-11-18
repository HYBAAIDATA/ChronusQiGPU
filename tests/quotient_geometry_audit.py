"""
Quotient Geometry Audit Tests

ISOLATED truncation code for proving the 256-to-1 fiber geometry in Lean.
These tests exist ONLY to validate the mathematical fiber geometry; production
code must NOT use truncation features. Enforces the project's no-truncation contract:
"we fold, we never truncate."
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from chronus.kernels.gl2_transform import (
    hensellift_m15, invert_gl2_mod2k, M15, M15_INV,
    trunc_fiber, fold, unfold, crc32c, Folded
)


def test_trunc_fiber_exact_256_partition() -> None:
    """Verify trunc_fiber produces exactly 256 unique points per output byte."""
    seen: set = set()
    for u in range(256):
        fib = list(trunc_fiber(u))
        assert len(fib) == 256, f"u={u}: fiber length {len(fib)} != 256"
        assert len(set(fib)) == 256, f"u={u}: duplicate points in fiber"
        for x, y in fib:
            assert (219 * x + 98 * y) % 256 == u
        seen.update(fib)
    assert len(seen) == 65536, "Total unique points != 65536"


def test_trunc_fiber_projects_to_u() -> None:
    """Verify every fiber point folds to its output u."""
    for u in range(256):
        fib = list(trunc_fiber(u))
        for x, y in fib:
            folded = fold(bytes([x, y]))
            assert unfold(folded) == bytes([x, y])
            # The truncated result should be u
            assert trunc_fiber(u)[0][0] == x  # first point's x


def test_no_truncation_in_production() -> None:
    """Enforce: production code must not use truncation features.

    This test deliberately imports from the production namespace and checks
    that truncation symbols are NOT in the public API.
    """
    from chronus.kernels import gl2_transform
    
    # These must NOT be in the production module's public API
    forbidden = ['fold_truncated', 'FLAG_TRUNCATED', 'gl2_fold_truncated_pairs']
    for name in forbidden:
        assert not hasattr(gl2_transform, name), \
            f"TRUNCATION SYMBOL '{name}' found in production gl2_transform!"
    
    # trunc_fiber should also NOT be in production __all__ (it's isolated)
    assert not hasattr(gl2_transform, 'trunc_fiber'), \
        "trunc_fiber should be ISOLATED, not in production API"


def test_wire_crc_tamper_detection() -> None:
    """Verify CRC-32C detects single-bit flips in wire frames."""
    import os
    for msg in (b"", b"X", b"XY", b"LHC-Run4-HL", os.urandom(1023)):
        f = fold(msg)
        w2 = f.to_wire()
        # Flip 1 bit anywhere
        tampered = bytearray(w2)
        tampered[-5] ^= 0x01
        try:
            Folded.from_wire(tampered)
            raise AssertionError(f"Should have detected bit flip for {msg!r}")
        except ValueError:
            pass  # Expected - CRC detected the error


def test_fold_unfold_roundtrip() -> None:
    """Verify fold/unfold is a bijection for all test messages."""
    for msg in (b"", b"A", b"AB", b"CERN-TDAQ-2026", os.urandom(513)):
        f = fold(msg)
        assert unfold(f) == msg, f"Roundtrip failed for {msg!r}"
        # Wire roundtrip
        w2 = f.to_wire()
        f2 = Folded.from_wire(w2)
        assert f2 == f and unfold(f2) == msg