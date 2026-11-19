"""Provenance verification for the M15 byte map over Z/256Z.

Three claims, settled computationally:

1. det(M15) = 16895 = -1 (mod 256): an odd determinant, which is the
   load-bearing fact - it makes the pair map a bijection on {0..255}^2.
2. M15 x M15_INV == I (the inverse is derived from det^-1 * adj).
3. The provenance claim "M15 = M^15 in GL(2, Z/256)":
   - the reviewer-proposed witness M = ((15,198),(198,15)) is tested directly;
   - an exhaustive 2-adic Hensel search enumerates EVERY X in GL(2, Z/256)
     with X^15 == M15, lifting from mod 2 (where the solutions of x^15 = I in
     GL(2,2) = S3 are exactly {I, the two 3-cycles} - transpositions have
     order 2, so x^15 = x != I);
   - structural note: powers of a circulant matrix ((a,b),(b,a)) remain
     circulant, and M15 = ((219,98),(98,121)) is not circulant, so no
     circulant witness can exist.

Also verifies the maintained implementation exhaustively: fold_pair followed
by unfold_pair is the identity on all 65,536 byte pairs.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from chronus.execution.structural import fold_pair, unfold_pair  # noqa: E402

M15 = ((219, 98), (98, 121))
M15_INV = ((135, 98), (98, 37))


def mul(a, b, m=256):
    return tuple(
        tuple(sum(a[i][k] * b[k][j] for k in range(2)) % m for j in range(2))
        for i in range(2)
    )


def mat_pow(base, exponent, m=256):
    result = ((1, 0), (0, 1))
    while exponent:
        if exponent & 1:
            result = mul(result, base, m)
        base = mul(base, base, m)
        exponent >>= 1
    return result


def mat_mod(mat, m):
    return tuple(tuple(v % m for v in row) for row in mat)


def main() -> int:
    print(f"M15 = {M15}")
    det = (M15[0][0] * M15[1][1] - M15[0][1] * M15[1][0]) % 256
    print(f"det(M15) mod 256  = {det}  (odd -> bijection: {det % 2 == 1})")
    product = mul(M15, M15_INV)
    print(f"M15 x M15_INV     = {product}  (identity: {product == ((1, 0), (0, 1))})")

    ok = all(
        unfold_pair(*fold_pair(a, b)) == (a, b)
        for a in range(256)
        for b in range(256)
    )
    print(f"maintained fold/unfold exhaustive roundtrip (65,536 pairs): {ok}")

    witness = ((15, 198), (198, 15))
    power = mat_pow(witness, 15)
    print(f"reviewer witness M^15 = {power}")
    print(f"witness satisfies the claim = {power == M15}")
    square = mat_pow(witness, 2)
    print(f"powers stay circulant = "
          f"{square[0][0] == square[1][1] and square[0][1] == square[1][0]}; "
          f"M15 circulant = "
          f"{M15[0][0] == M15[1][1] and M15[0][1] == M15[1][0]}")

    branches = [((1, 0), (0, 1)), ((0, 1), (1, 1)), ((1, 1), (1, 0))]
    mod = 2
    candidates = branches
    while mod < 256 and candidates:
        higher = mod * 2
        target = mat_mod(M15, higher)
        lifted = []
        for base in candidates:
            for d0 in (0, mod):
                for d1 in (0, mod):
                    for d2 in (0, mod):
                        for d3 in (0, mod):
                            cand = (
                                (base[0][0] + d0, base[0][1] + d1),
                                (base[1][0] + d2, base[1][1] + d3),
                            )
                            if mat_pow(cand, 15, higher) == target:
                                lifted.append(cand)
        candidates = lifted
        mod = higher
        print(f"lifted to mod {mod}: {len(candidates)} candidate(s)")

    print(f"15th roots of M15 in GL(2, Z/256): {len(candidates)} found")
    for root in candidates[:4]:
        print(f"  root {root} -> X^15 = {mat_pow(root, 15)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
