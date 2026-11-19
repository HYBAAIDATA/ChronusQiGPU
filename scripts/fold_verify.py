"""Standalone verifier for the GoldenArithmetic modular word fold.

Only the standard library is required. A matrix witness alone never attests
payload integrity: every canonical folded pair has a preimage. A trusted
original or digest of the canonical original bytes is needed for VALID.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from hmac import compare_digest


def _parameters(steps, bits):
    if type(bits) is not int or not 8 <= bits <= 4096 or bits % 8:
        raise ValueError("bits must be a multiple of eight in [8,4096]")
    if type(steps) is not int or steps < 0:
        raise ValueError("steps must be a nonnegative integer")
    return 1 << bits, steps % (3 << (bits - 1))


def _multiply(x, y, m):
    a, b, c, d = x
    e, f, g, h = y
    return ((a*e+b*g)%m, (a*f+b*h)%m, (c*e+d*g)%m, (c*f+d*h)%m)


def _fib(n, m):
    a, b = 0, 1
    for bit in bin(n)[2:]:
        c, d = a*(2*b-a)%m, (a*a+b*b)%m
        a, b = (d, (c+d)%m) if bit == "1" else (c, d)
    return a, b


def certificate(steps, bits):
    m, n = _parameters(steps, bits)
    # Independent matrix exponentiation, not the producer's Fibonacci formula.
    matrix, base, k = (1, 0, 0, 1), (1, 1, 1, 0), n
    while k:
        if k & 1:
            matrix = _multiply(matrix, base, m)
        base = _multiply(base, base, m)
        k >>= 1
    a, b, c, d = matrix
    f, g = _fib(n, m)
    determinant, trace = (a*d-b*c)%m, (a+d)%m
    want_det, want_trace = (-1 if n%2 else 1)%m, (2*g-f)%m
    if matrix != (g, f, f, (g-f)%m) or determinant != want_det or trace != want_trace:
        raise ArithmeticError("matrix certificate mismatch")
    return {"schema": "golden-fold/1", "bits": bits, "steps": steps, "n": n,
            "matrix": list(matrix), "cassini": {"det": determinant, "want": want_det},
            "lucas": {"trace": trace, "want": want_trace}}


def _words(words, m):
    if not isinstance(words, (tuple, list)) or not words or len(words)%2:
        raise ValueError("nonempty even word sequence required")
    if any(type(w) is not int or not 0 <= w < m for w in words):
        raise ValueError("noncanonical unsigned word")
    return list(words)


def _apply(words, matrix, m):
    a, b, c, d = matrix
    out = []
    for x, y in zip(words[::2], words[1::2]):
        out.extend(((a*x+b*y)%m, (c*x+d*y)%m))
    return out


def fold(words, steps, bits):
    m, _ = _parameters(steps, bits)
    return _apply(_words(words, m), certificate(steps, bits)["matrix"], m)


def unfold(words, steps, bits):
    m, n = _parameters(steps, bits)
    a, b, c, d = certificate(steps, bits)["matrix"]
    s = -1 if n%2 else 1
    return _apply(_words(words, m), (s*d, -s*b, -s*c, s*a), m)


def original_digest(words, bits):
    m, _ = _parameters(0, bits)
    # Fixed-width big-endian words; domain and width bound into the digest.
    payload = b"golden-fold/1:" + bits.to_bytes(2, "big")
    payload += b"".join(w.to_bytes(bits//8, "big") for w in _words(words, m))
    return hashlib.sha256(payload).hexdigest()


def verify(folded, steps, bits, originals=None, *, digest=None, witness=None):
    try:
        cert = certificate(steps, bits)
        decoded = unfold(folded, steps, bits)
        if witness is not None and (type(witness) is not dict or
                json.dumps(witness, sort_keys=True, allow_nan=False) !=
                json.dumps(cert, sort_keys=True, allow_nan=False)):
            raise ValueError("supplied certificate differs from recomputation")
        if originals is not None and decoded != _words(originals, 1 << bits):
            raise ValueError("original words mismatch")
        if digest is not None:
            if (type(digest) is not str or len(digest) != 64 or
                    any(c not in "0123456789abcdef" for c in digest) or
                    not compare_digest(original_digest(decoded, bits), digest)):
                raise ValueError("trusted original digest mismatch")
        verdict = "VALID" if originals is not None or digest is not None else "UNBOUND"
        return {"verdict": verdict, "certificate": cert, "failures": []}
    except (ValueError, TypeError, ArithmeticError, OverflowError) as exc:
        return {"verdict": "INVALID", "failures": [str(exc)]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folded", required=True)
    parser.add_argument("--steps", type=int, required=True)
    parser.add_argument("--bits", type=int, required=True)
    parser.add_argument("--originals")
    parser.add_argument("--digest")
    parser.add_argument("--certificate", help="JSON certificate file")
    args = parser.parse_args(argv)
    try:
        def parse(value):
            return [int(x) for x in value.split(",")]
        witness = None
        if args.certificate:
            with open(args.certificate, encoding="utf-8") as handle:
                witness = json.load(handle)
        result = verify(parse(args.folded), args.steps, args.bits,
                        parse(args.originals) if args.originals is not None else None,
                        digest=args.digest, witness=witness)
    except (ValueError, TypeError, OSError) as exc:
        result = {"verdict": "INVALID", "failures": [str(exc)]}
    print(json.dumps(result, sort_keys=True))
    return {"VALID": 0, "INVALID": 1, "UNBOUND": 2}[result["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
