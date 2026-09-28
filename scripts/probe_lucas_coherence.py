"""Run TOE's real scale program across the canonical Lucas ladder.

This is the test that matters. TOE defines its scales through the
Lucas/Pisot theorems (T1 Cassini, T3 Binet, T4 Lucas-Pisot scaling), not
through a nonce budget. Earlier experiments measured search effort; this one
measures the theorems the ladder actually claims.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lucas.ladder import FULL_LADDER, ladder_values  # noqa: E402
from toe.system import TOESystem  # noqa: E402


class _Cand:
    """Minimal PrecomputedCandidate stand-in carrying real arithmetic."""

    def __init__(self, nonce=1, mask=0b1010101, born=0.9, galois=10**12):
        self.nonce = nonce
        self.zeckendorf_mask = mask
        self.born_probability = born
        self.galois_composite = galois


if __name__ == "__main__":
    toe = TOESystem()
    print("=== TOE 12-theorem arbiter across the canonical Lucas ladder ===")
    print(f"{'rung':>5} {'L_n':>8} {'all_pass':>9}  failing")
    for rung, value in zip(FULL_LADDER, ladder_values()):
        ok, results = toe.verify_12_theorems_candidate(_Cand(), n_anchor=rung)
        failing = [k for k, v in results.items() if not v]
        print(f"{rung:>5} {value:>8} {str(ok):>9}  {failing or 'none'}")

    print()
    print("=== NEGATIVE CONTROLS: a checker that cannot fail proves nothing ===")
    # Each case violates exactly one theorem. If the arbiter reports all_pass
    # for any of these, that check is vacuous and the ladder pass above is
    # meaningless.
    cases = [
        ("T5 zeckendorf adjacent bits", _Cand(mask=0b11), "T5_zeckendorf_spacing"),
        ("T11 born prob below 0.5", _Cand(born=0.1), "T11_born_rule_threshold"),
        ("T12 galois >= 2^61-1", _Cand(galois=(2**61) + 1), "T12_galois_bound"),
        ("T8 nonce=0 and mask!=0", _Cand(nonce=0, mask=0b101), "T8_structure_existence"),
    ]
    for label, cand, expect_key in cases:
        ok, res = toe.verify_12_theorems_candidate(cand, n_anchor=15)
        caught = res.get(expect_key) is False
        flag = "CAUGHT" if caught else "!!! VACUOUS !!!"
        print(f"  {label:32} {expect_key:26} -> all_pass={str(ok):5} {flag}")

    print()
    print("=== T4 is a genuine identity check (L_{n+1}-L_n == L_{n-1}) ===")
    from toe.system import CassiniVerifier

    for n in FULL_LADDER:
        lhs = CassiniVerifier.lucas(n + 1) - CassiniVerifier.lucas(n)
        rhs = CassiniVerifier.lucas(n - 1)
        print(f"  n={n:2}  L_{n + 1}-L_n={lhs:6}  L_{n - 1}={rhs:6}  " f"match={lhs == rhs}")
    sys.stdout.flush()
