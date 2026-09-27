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
