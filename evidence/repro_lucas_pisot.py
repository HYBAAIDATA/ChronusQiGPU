"""Repro of benchmarks/lucas_pisot_scaling.py accounting.
Shows why test_benchmark_lucas_pisot.py tested the wrong thing."""
import math, random
from math import gcd

PSI = (1.0 - math.sqrt(5.0)) / 2.0
def pisot_damp(n): return 1.0 - abs(PSI)**n

def coprime_stride(count, preferred):
    if count <= 1: return 1
    s = preferred % count or 1
    while gcd(s, count) != 1:
        s = (s+1) % count or 1
    return s

def order(n, preferred=1473620615217855600982175579145):  # lucas(76)-scale preferred
    s = coprime_stride(n, preferred)
    return [(p*s) % n for p in range(n)]

if __name__ == "__main__":
    # 1. What agent tested: trivial invariants
    n = 1024
    o = order(n)
    assert sorted(o) == list(range(n)), "permutation must hold (gcd=1)"
    print("PASS trivial: _order is permutation (coprime => bijection, not speedup)")

    # 2. What agent DID NOT test: unconditional cost
    for damp_n in (3, 4, 5, 6):
        d = pisot_damp(damp_n)
        for n in (256, 1024, 4096):
            o = order(n)
            rank = {w: i for i, w in enumerate(o)}
            size = math.ceil(n * d)
            sub = {w: i for i, w in enumerate(o[:size])}
            rng = random.Random(f"lps-{damp_n}-{n}-0")
            base = []
            allr = []
            for t in range(2000):
                w = rng.randrange(n)
                base.append(rank[w] + 1)
                if w in sub:
                    allr.append(sub[w] + 1)
                else:
                    allr.append(size + (rank[w] - size) + 1)  # exact line from benchmark
            mb = sum(base) / len(base)
            ma = sum(allr) / len(allr)
            print(f"n={n:5d} damp_n={damp_n} damp={d:.4f} hit_rate~{d:.4f} mean_base={mb:.1f} mean_restricted_unconditional={ma:.1f} equal={abs(mb-ma)<1e-9}")
            assert abs(mb - ma) < 1e-9, "unconditional means must be IDENTICAL by algebra"
    print("\nCONCLUSION: restricted unconditional == unrestricted, always.")
    print("Agent tests (damp values, permutation, subset size) never measured this.")
    print("FIX: assert unconditional equality + report hit-conditional ONLY as conditional, never as speedup.")
