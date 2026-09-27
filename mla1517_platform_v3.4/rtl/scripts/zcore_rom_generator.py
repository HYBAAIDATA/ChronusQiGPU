#!/usr/bin/env python3
"""ZCore ROM generator — emits the D5/D6 lookup images consumed by
``rtl/mla1517_zcore.sv`` via ``$readmemh``.

Exact integer arithmetic only (Rule 7): no floating point anywhere in the
generation path.

  D5 (zcore_d5_zeckendorf.mem): 32-bit Zeckendorf bitmask of the nonce index
      over the Fibonacci basis {1, 2, 3, 5, ...}. Non-adjacency invariant:
      ``code & (code << 1) == 0``.

  D6 (zcore_d6_binet_q.mem): Binet projection phi**n rendered in
      Q(fractional_bits) fixed point: ``round(phi**n * 2**frac)``.
      phi**n = (L_n + F_n*sqrt(5)) / 2 is computed exactly — L_n, F_n are
      integers and the sqrt(5) term is resolved by integer square root with
      exact round-half-up correction. 194-bit width covers n <= 255 at
      16 fractional bits (phi**255 * 2**16 < 2**194).

Outputs:
  zcore_d5_zeckendorf.mem  — one hex word per line, depth = max_nonce + 1
  zcore_d6_binet_q.mem     — one hex word per line, depth = max_nonce + 1
  zcore_rom_manifest.json  — depth, widths, fractional bits, generator digest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

FIBONACCI_BASIS = (1, 2)


def _fib_pairs(limit: int) -> list[int]:
    fibs = [FIBONACCI_BASIS[0], FIBONACCI_BASIS[1]]
    while fibs[-1] <= limit:
        fibs.append(fibs[-1] + fibs[-2])
    return fibs


def zeckendorf_code(value: int) -> int:
    """Zeckendorf bitmask of ``value`` over basis {1,2,3,5,...} — bit i set iff
    fibs[i] participates. Greedy descent guarantees non-adjacency."""
    if value < 0:
        raise ValueError("zeckendorf_code: negative value")
    fibs = _fib_pairs(max(value, 1))
    code = 0
    remainder = value
    for i in range(len(fibs) - 1, -1, -1):
        if fibs[i] <= remainder:
            remainder -= fibs[i]
            code |= 1 << i
    assert remainder == 0
    assert code & (code << 1) == 0  # Zeckendorf non-adjacency
    return code


def _fib_lucas(n: int) -> tuple[int, int]:
    """Return (F_n, L_n) exactly via the plain recurrences."""
    f_prev, f_cur = 0, 1
    l_prev, l_cur = 2, 1
    for _ in range(n):
        f_prev, f_cur = f_cur, f_prev + f_cur
        l_prev, l_cur = l_cur, l_prev + l_cur
    return f_prev, l_prev


def binet_q(n: int, frac_bits: int) -> int:
    """round(phi**n * 2**frac_bits) computed exactly.

    phi**n = (L_n + F_n*sqrt(5))/2, so
        phi**n * 2**frac = L_n * 2**(frac-1) + F_n * sqrt(5) * 2**(frac-1)
    The irrational term is resolved as round(F_n * sqrt(5 * 4**(frac-1)))
    via integer square root plus a one-ulp round-half correction.
    """
    if frac_bits < 1:
        raise ValueError("fractional_bits must be >= 1")
    f_n, l_n = _fib_lucas(n)
    int_part = l_n << (frac_bits - 1)
    if f_n == 0:
        return int_part
    # round(F_n * sqrt(5) * 2**(frac-1)) = round(sqrt(5 * F_n^2 * 4**(frac-1)))
    radicand = 5 * f_n * f_n * (1 << (2 * (frac_bits - 1)))
    root = math.isqrt(radicand)
    # exact round-half-up: sqrt(R) >= root + 1/2 iff 4R >= (2*root + 1)^2
    if 4 * radicand >= (2 * root + 1) ** 2:
        root += 1
    return int_part + root


def generate(max_nonce: int, frac_bits: int, out_dir: Path) -> dict:
    depth = max_nonce + 1
    d5 = [zeckendorf_code(n) for n in range(depth)]
    d6 = [binet_q(n, frac_bits) for n in range(depth)]

    d5_w = max(32, max(d5, default=0).bit_length())
    d6_w = max(1, max(d6, default=1).bit_length())

    out_dir.mkdir(parents=True, exist_ok=True)
    d5_path = out_dir / "zcore_d5_zeckendorf.mem"
    d6_path = out_dir / "zcore_d6_binet_q.mem"
    d5_path.write_text("".join(f"{v:0{(d5_w + 3) // 4}x}\n" for v in d5), encoding="ascii")
    d6_path.write_text("".join(f"{v:x}\n" for v in d6), encoding="ascii")

    manifest = {
        "depth": depth,
        "max_nonce": max_nonce,
        "fractional_bits": frac_bits,
        "d5_width_bits": d5_w,
        "d6_width_bits": d6_w,
        "d5_file": d5_path.name,
        "d6_file": d6_path.name,
        "digest_sha256": hashlib.sha256(
            d5_path.read_bytes() + d6_path.read_bytes()
        ).hexdigest(),
        "semantics": {
            "d5": "Zeckendorf bitmask of index over Fibonacci basis {1,2,3,5,...}",
            "d6": "round(phi**n * 2**fractional_bits), exact integer Binet",
        },
    }
    (out_dir / "zcore_rom_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate ZCore D5/D6 ROM images")
    ap.add_argument("--max-nonce", type=int, required=True)
    ap.add_argument("--fractional-bits", type=int, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    manifest = generate(args.max_nonce, args.fractional_bits, args.out_dir)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
