"""Honest measurement tests for the Lucas / Pisot exponential-scaling claims.

What AGENTS.md actually claims (and what it does not):

- L_n = phi^n + (-phi)^(-n): exact Binet structure. TESTED.
- Pisot collapse: |L_n - phi^n| = phi^(-n) -> 0 exponentially. TESTED.
- Lucas-indexed scaling of *algorithmic budgets*: real. TESTED (L_15 = 1364).
- Lucas scaling multiplies PHYSICAL sha256d throughput or creates shares:
  NOT claimed by AGENTS.md, NOT supported by AUDIT_REPORT.md, and TESTED
  here as a negative control.

This file contains no mocks. Every digest below is really computed.
"""

import hashlib
import struct
from decimal import Decimal, getcontext, localcontext

import pytest

from Intelligence.lucas_attractor import LucasAttractor
from mining.hash_pipeline import double_sha256

getcontext().prec = 100


def lucas_int(n: int) -> int:
    """Exact integer Lucas number via the recurrence (no Binet error)."""
    a, b = 2, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def decimal_phi() -> Decimal:
    return (Decimal(1) + Decimal(5).sqrt()) / 2


def test_l15_is_1364_and_resonance_is_exact():
    assert lucas_int(15) == 1364
    att = LucasAttractor(n=15)
    assert att.attractor_score(1364.0) == pytest.approx(1.0, abs=1e-12)
    assert att.attractor_score(1000.0) < 1e-4


def test_lucas_growth_is_exponential():
    # L_n grows like phi^n: the ratio converges to phi from below.
    phi = (1.0 + 5.0**0.5) / 2.0
    for n in (50, 100, 200):
        ratio = lucas_int(n + 1) / lucas_int(n)
        assert ratio == pytest.approx(phi, rel=1e-12)
    assert lucas_int(100) > 10**20  # exponential in the index


def test_lucas_index_space_is_unbounded_but_storage_is_finite():
    # Exact integer recurrence: the INDEX space is unbounded and exact.
    assert lucas_int(5000) > 10**1044
    # The STORAGE substrate is finite: 25 primes x 1024 slots.
    from Intelligence.unified_punch import PRIME_COUNT, SLOTS_PER_PRIME, TOTAL_SLOTS

    assert TOTAL_SLOTS == PRIME_COUNT * SLOTS_PER_PRIME == 25 * 1024


# ---------------------------------------------------------------------------
# 2. Pisot collapse: |L_n - phi^n| = phi^(-n), exponentially decaying
# ---------------------------------------------------------------------------


def test_pisot_error_term_is_exactly_phi_to_minus_n():
    # localcontext: the module-level getcontext().prec is global mutable
    # state — another suite test can lower it before this test runs.
    with localcontext() as ctx:
        ctx.prec = 100
        phi = decimal_phi()
        for n in (10, 50, 76, 100, 150):
            expected = phi ** (-n)
            actual = abs(Decimal(lucas_int(n)) - phi**n)
            ratio = actual / expected
            assert abs(ratio - Decimal(1)) < Decimal("1e-20")


def test_pisot_collapse_threshold_truth():
    """The one-off threshold: 1e-16 is crossed at n = 77, not n = 76."""
    phi = decimal_phi()
    err_76 = abs(Decimal(lucas_int(76)) - phi**76)
    err_77 = abs(Decimal(lucas_int(77)) - phi**77)
    assert err_76 > Decimal("1e-16")  # 1.31e-16: the strict claim is off by one
    assert err_77 < Decimal("1e-16")


# ---------------------------------------------------------------------------
# 3. Does Lucas structure correlate with REAL sha256d output? (with a
#    cheating-oracle positive control the harness MUST detect)
# ---------------------------------------------------------------------------


def _digest_int(header: bytes, nonce: int) -> int:
    return int.from_bytes(double_sha256(header[:76] + struct.pack("<I", nonce & 0xFFFFFFFF)), "big")


def test_lucas_score_is_uncorrelated_with_real_sha256d_digests():
    """AGENTS.md 2.3 claims Lucas selection concentrates density in
    low-entropy hash regions. On the real double-SHA256 random oracle this
    harness measures the separation directly, with a cheating positive
    control to prove the harness itself detects real correlation."""
    att = LucasAttractor(n=15)
    separation = []
    control_separation = []
    for seed in range(5):
        header = hashlib.sha256(f"lucas-honesty-{seed}".encode()).digest() * 2 + bytes(16)
        assert len(header) == 80
        nonces = list(range(4000))
        digests = [_digest_int(header, n) for n in nonces]
        scores = [att.attractor_score(float(n)) for n in nonces]

        overall = sum(digests) / len(digests)
        order = sorted(range(len(nonces)), key=lambda i: scores[i], reverse=True)
        top = [digests[i] for i in order[:400]]
        separation.append((sum(top) / len(top)) / overall)

        # Positive control: order by the digest itself (a cheating oracle).
        corder = sorted(range(len(nonces)), key=lambda i: digests[i])
        ctop = [digests[i] for i in corder[:400]]
        control_separation.append((sum(ctop) / len(ctop)) / overall)

    mean_sep = sum(separation) / len(separation)
    mean_ctrl = sum(control_separation) / len(control_separation)
    # The cheating oracle MUST separate strongly (harness has teeth).
    assert mean_ctrl < 0.15
    # Lucas resonance shows no significant separation on the real oracle.
    assert 0.85 < mean_sep < 1.15


# ---------------------------------------------------------------------------
# 4. Lucas-scaled "effective hashrate" changes reported numbers, not
#    physical outcomes. Deterministic negative control.
# ---------------------------------------------------------------------------


def test_scaled_hashrate_does_not_create_shares():
    header = hashlib.sha256(b"scale-invariance").digest() * 2 + bytes(16)
    target_be = b"\x01" + b"\x00" * 31  # accept if digest < 2^248 (p = 1/256)
    nonces = list(range(2000))
    target = int.from_bytes(target_be, "big")
    digests = [_digest_int(header, n) for n in nonces]
    winners_physical = sum(1 for d in digests if d < target)

    # Recount: identical physical outcome, scale-independent.
    winners_recount = sum(1 for n in nonces if _digest_int(header, n) < target)
    assert winners_recount == winners_physical

    # The Lucas scale multiplies the REPORT, never the physics.
    report_scaled = winners_physical * lucas_int(15)
    assert report_scaled > winners_physical
    # ...but no additional digest is created below target by any scale.
    assert sum(1 for d in digests if d < target) == winners_physical
