"""Independent verification of Chronus' Lucas/Pisot scaling math.

Every expected value below is computed here from first principles (exact integers, Fractions,
120-digit Decimals) and never by calling the code under test. Where the implementation has a
deliberate-but-surprising behaviour, the test PINS it so a change is a conscious decision.
"""

from __future__ import annotations

from decimal import Decimal, localcontext

import pytest

from chronus.seam.scale import (
    MAX_WORK_ITEMS,
    REF_LUCAS_N,
    compute_effective_capacity,
    memory_budget_bytes,
    scale_job,
    snap_work_items,
    toe_t4_lucas_pisot,
)
from kellogg.scales import _drift_step, lucas
from Intelligence.lucas_scales import CHRONUS_SCALE_RUNGS, ladder_multiples_of


def L(n: int) -> int:
    a, b = 2, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def F(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


# --- Lucas arithmetic ----------------------------------------------------------------------


def test_lucas_matches_independent_recurrence_and_identities() -> None:
    for n in list(range(0, 401)) + [1000, 5000, 10_000]:
        assert lucas(n) == L(n), n
    for n in range(1, 300):
        assert L(n) == F(n - 1) + F(n + 1)
        assert L(n) ** 2 - 5 * F(n) ** 2 == 4 * (-1) ** n
        assert toe_t4_lucas_pisot(n) and L(n + 1) - L(n) == L(n - 1)
    assert not toe_t4_lucas_pisot(0)


def test_ladder_rungs_and_documented_literals() -> None:
    assert CHRONUS_SCALE_RUNGS == (10, 12, 15, 18, 20, 31, 50, 76)
    documented = {
        10: 123, 12: 322, 15: 1364, 18: 5778, 20: 15127,
        31: 3010349, 50: 28143753123, 76: 7639424778862807,
    }  # fmt: skip
    for n, value in documented.items():
        assert L(n) == value == lucas(n)


def test_pisot_drift_constant_is_phi_inverse_to_the_15th() -> None:
    with localcontext() as ctx:
        ctx.prec = 120
        phi = (1 + Decimal(5).sqrt()) / 2
        delta = phi**15 - L(15)
        assert abs(delta - 1 / phi**15) < Decimal("1e-100")  # delta_15 = phi^-15 (odd k)
        assert Decimal("7.33e-4") < delta < Decimal("7.34e-4")  # AGENTS.md: ~7.33e-4


# --- effective capacity: effective = physical * L_n // L_10 --------------------------------


@pytest.mark.parametrize("physical", [0, 1, 2, 7, 80, 1000, 10**6])
@pytest.mark.parametrize("n", [1, 3, 9, 10, 11, 12, 15, 18, 20, 31, 50, 76])
def test_effective_capacity_matches_independent_formula(physical: int, n: int) -> None:
    got = compute_effective_capacity(physical, n)
    ref = L(REF_LUCAS_N)
    expected = physical * L(n) // ref if physical else 0
    if physical and L(n) >= ref and expected < physical:
        expected = physical
    assert got.physical == physical
    assert got.effective == expected
    assert got.lucas_L == L(n) and got.ref_L == ref


def test_effective_capacity_documented_witnesses() -> None:
    assert compute_effective_capacity(80, 15).effective == 887  # 80 * 1364 // 123
    assert compute_effective_capacity(80, 10).effective == 80  # reference rung is identity
    assert compute_effective_capacity(1000, 76).effective == 62109144543600056  # exact bigint


def test_effective_capacity_is_monotone_in_both_arguments() -> None:
    for n in range(1, 40):
        row = [compute_effective_capacity(p, n).effective for p in range(0, 300, 7)]
        assert row == sorted(row)
    for p in (1, 5, 80, 1000):
        col = [compute_effective_capacity(p, n).effective for n in range(1, 60)]
        assert col == sorted(col)


def test_below_reference_rung_rounds_a_nonzero_fleet_to_zero_effective() -> None:
    """PINNED BEHAVIOUR (surprising): rungs below L_10 can give effective == 0 for physical > 0."""
    assert compute_effective_capacity(1, 9).effective == 0  # 1 * 76 // 123
    assert compute_effective_capacity(80, 1).effective == 0  # 80 * 1 // 123
    assert compute_effective_capacity(0, 15).effective == 0


# --- memory budget -------------------------------------------------------------------------


@pytest.mark.parametrize("base", [0, 1, 4096, 1 << 20])
@pytest.mark.parametrize("n", [1, 5, 10, 12, 15, 20])
def test_memory_budget_matches_formula_and_never_shrinks_below_base(base: int, n: int) -> None:
    expected = 0 if base == 0 else max(base, base * L(n) // L(10))
    assert memory_budget_bytes(base, n) == expected
    assert memory_budget_bytes(base, n) >= base


def test_memory_budget_does_not_scale_down_below_reference_rung() -> None:
    """PINNED: the docstring says 'at least base when L_n >= L_ref' but the clamp is unconditional."""
    assert memory_budget_bytes(1 << 20, 1) == 1 << 20
    assert (1 << 20) * L(1) // L(10) < 1 << 20  # the raw ratio WOULD shrink


# --- ladder snapping ----------------------------------------------------------------------


def _is_stop(n: int) -> bool:
    return n > 0 and any(n % r == 0 for r in CHRONUS_SCALE_RUNGS)


def test_snap_work_items_is_the_nearest_ladder_stop_with_upward_ties() -> None:
    stops = [n for n in range(1, MAX_WORK_ITEMS + 1) if _is_stop(n)]
    for requested in list(range(1, 400)) + [1000, 4321, 30000, 65535, 65536, 70000]:
        got = snap_work_items(requested)
        clamped = max(1, min(MAX_WORK_ITEMS, requested))
        best = min(abs(s - clamped) for s in stops)
        assert _is_stop(got) and abs(got - clamped) == best
        if abs(got - clamped) and (clamped + best) in stops and (clamped - best) in stops:
            assert got == clamped + best  # ties go up


def test_scale_job_is_deterministic_and_reports_rungs_that_divide() -> None:
    a = scale_job("job-x", 1000, "p")
    b = scale_job("job-x", 1000, "p")
    assert a == b
    assert a.rungs and all(a.work_items % r == 0 for r in a.rungs)
    assert list(a.rungs) == ladder_multiples_of(a.work_items)
    assert len(a.t11) == 11 and all(
        len(c) == 2 and all(isinstance(x, int) for x in c) for c in a.t11
    )
    assert scale_job("job-y", 1000, "p").t11 != a.t11


# --- Pisot drift step ----------------------------------------------------------------------


def test_drift_step_matches_120_digit_reference() -> None:
    with localcontext() as ctx:
        ctx.prec = 120
        phi = (1 + Decimal(5).sqrt()) / 2
        delta = phi**15 - L(15)
        for m in range(0, 90):
            exact = (delta * L(m)) % 1
            got = Decimal(_drift_step(m))
            err = abs(exact - got)
            assert min(err, 1 - err) < Decimal("1e-9"), m


def test_drift_step_vanishes_for_large_m_so_long_orbits_are_not_ergodic() -> None:
    """PINNED: the winding step -> 0 for m >~ 60, so pisot_wind only perturbs for small m
    (production uses m = 1..11). It is a one-step observational rotation, not an ergodic orbit."""
    assert _drift_step(5) > 1e-3 and _drift_step(11) > 1e-2
    assert _drift_step(76) < 1e-9
    assert _drift_step(200) < 1e-30
