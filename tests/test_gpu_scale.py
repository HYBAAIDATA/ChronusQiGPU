from Intelligence.lucas_scales import IGPU_SCALE_RUNGS
from igpu.seam.gpu_scale import DIM, scale_job, snap_work_items, toe_t4_lucas_pisot
from kellogg.scales import lucas


def test_snap_is_a_rung_or_multiple():
    n = snap_work_items(17)
    assert n > 0
    assert any(n % r == 0 for r in IGPU_SCALE_RUNGS)


def test_default_collapse_rung():
    s = scale_job("job-a", 0)
    assert any(s.work_items % r == 0 for r in IGPU_SCALE_RUNGS)
    assert len(s.t11) == DIM


def test_same_job_same_wind():
    a = scale_job("job-a", 12)
    b = scale_job("job-a", 12)
    assert a.t11 == b.t11
    assert a.lucas_L == lucas(a.work_items)


def test_toe_t4_is_the_recurrence():
    for n in (1, 2, 7, 10, 15):
        assert toe_t4_lucas_pisot(n)
        assert lucas(n + 1) == lucas(n) + lucas(n - 1)


def test_large_windows_wind_without_overflow_and_stay_exact():
    # frac(delta_15 * L_m) against 3000-digit arithmetic, where the old float
    # product overflowed (m ~ 1475) and had lost its fraction (m ~ 70).
    from decimal import Decimal, getcontext

    from kellogg.scales import _drift_step

    getcontext().prec = 3000
    phi = (1 + Decimal(5).sqrt()) / 2
    delta = phi**15 - lucas(15)
    for m in (0, 21, 90, 1475, 4096):
        exact = float((delta * lucas(m)) % 1)
        error = abs(exact - _drift_step(m))
        assert min(error, 1 - error) < 1e-9, m
    s = scale_job("job-big", 4096)
    assert len(s.t11) == DIM and all(0.0 <= x < 1.0 for x in s.t11)
