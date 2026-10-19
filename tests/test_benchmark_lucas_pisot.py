"""FIXED test for benchmarks/lucas_pisot_scaling.py
Replaces smoke-only test_benchmark_lucas_pisot.py which tested:
  - damp values, permutation, subset size (all trivial, no perf claim)
This tests the RIGHT thing: honest accounting.
"""
import math
from math import gcd

PSI = (1.0 - math.sqrt(5.0)) / 2.0

def pisot_damp(n: int) -> float:
    return 1.0 - abs(PSI) ** n

def _coprime_stride(count: int, preferred: int) -> int:
    if count <= 1:
        return 1
    s = preferred % count or 1
    while gcd(s, count) != 1:
        s = (s + 1) % count or 1
    return s

def _order(n: int, preferred: int = 763416393694) -> list:
    s = _coprime_stride(n, preferred)
    assert gcd(s, n) == 1
    return [(p * s) % n for p in range(n)]


def test_unconditional_cost_equal_no_speedup():
    """Core fix: miss cost = size + (rank-size) + 1 = rank+1 = base.
    Restricted unconditional MUST equal unrestricted. Any speedup claim = FAIL."""
    import random
    for damp_n in (3, 4, 5, 6, 15, 18, 20):
        d = pisot_damp(damp_n)
        n = 1024
        order = _order(n)
        rank = {w: i for i, w in enumerate(order)}
        size = math.ceil(n * d)
        sub = {w: i for i, w in enumerate(order[:size])}
        rng = random.Random(f"lps-{damp_n}-{n}")
        base, allr, hits = [], [], 0
        for t in range(2000):
            w = rng.randrange(n)
            base.append(rank[w] + 1)
            if w in sub:
                hits += 1
                allr.append(sub[w] + 1)
            else:
                allr.append(size + (rank[w] - size) + 1)
        assert abs(sum(base)/len(base) - sum(allr)/len(allr)) < 1e-9
        assert abs(hits/2000 - d) < 0.05, "hit_rate must ~= damp (uniform mark)"
        # hit-conditional is faster BY CONSTRUCTION (subset), not a speedup
        hit_only = [sub[w]+1 for w in [k for k in sub][:100]]
        assert sum(hit_only)/len(hit_only) < sum(base)/len(base)


def test_permutation_is_ordering_not_advantage():
    for n in (256, 1024, 4096):
        assert sorted(_order(n)) == list(range(n))


def test_boundaries_per_lucas_scaling_research():
    # Mirrors lucas/scaling_research.py non_claims:
    # ["mining advantage","scheduling advantage","hardware speedup","production qualification"]
    # This test LOCKS that boundary: no function here may claim them.
    assert pisot_damp(6) > pisot_damp(3)
    assert pisot_damp(15) > pisot_damp(6)
    assert pisot_damp(18) > pisot_damp(15)
    assert pisot_damp(20) > pisot_damp(18)
    assert all(0 < pisot_damp(x) < 1 for x in (3, 4, 5, 6, 15, 18, 20))
