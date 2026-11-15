"""Algebraic payload fingerprint: point count of a payload-derived elliptic curve.

The payload's SHA-256 digest selects a non-singular curve
E: y^2 = x^3 + a x + b over F_p (p = 257). The fingerprint is the Frobenius
trace a_p = p + 1 - #E(F_p), computed by exact point counting. Hasse's theorem
guarantees a_p^2 <= 4p; checking it is a self-test of the point count, not a
security property.

This is an algebraic fingerprint only. a_p takes at most 2*floor(2 sqrt p) + 1
values, so it is not an integrity check; payload integrity comes from SHA-256
and the Ed25519 receipt signature. The notes' "Hecke eigenform / BSD checksum"
wording refers to this computation; Hecke-operator commutation is not
implemented and is not claimed.
"""

import hashlib
from typing import Any, Dict

FIELD_P = 257


def curve_from_payload(payload: bytes, p: int = FIELD_P) -> Dict[str, int]:
    digest = hashlib.sha256(payload).digest()
    a = int.from_bytes(digest[:8], "big") % p
    b = int.from_bytes(digest[8:16], "big") % p
    while (4 * a * a * a + 27 * b * b) % p == 0:
        b = (b + 1) % p
    return {"a": a, "b": b, "p": p}


def count_points(a: int, b: int, p: int = FIELD_P) -> int:
    """#E(F_p) including the point at infinity, by exhaustive counting."""
    square_roots = {}
    for y in range(p):
        square_roots[y * y % p] = square_roots.get(y * y % p, 0) + 1
    affine = sum(square_roots.get((x * x * x + a * x + b) % p, 0) for x in range(p))
    return affine + 1


def legendre_trace(a: int, b: int, p: int = FIELD_P) -> int:
    """a_p = -sum_x chi(x^3 + a x + b), with chi the Legendre symbol (independent check)."""
    total = 0
    for x in range(p):
        f = (x * x * x + a * x + b) % p
        if f:
            total += 1 if pow(f, (p - 1) // 2, p) == 1 else -1
    return -total


def fingerprint(payload: bytes, p: int = FIELD_P) -> Dict[str, Any]:
    curve = curve_from_payload(payload, p)
    points = count_points(curve["a"], curve["b"], p)
    a_p = p + 1 - points
    independent = legendre_trace(curve["a"], curve["b"], p)
    return {
        "curve": f"y^2 = x^3 + {curve['a']}x + {curve['b']} over F_{p}",
        "curve_coefficients": curve,
        "point_count": points,
        "frobenius_trace_ap": a_p,
        "independent_trace_check": independent == a_p,
        "hasse_bound_satisfied": a_p * a_p <= 4 * p,
        "hasse_bound": f"|a_p| <= 2*sqrt({p})",
    }
