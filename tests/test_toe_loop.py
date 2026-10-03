from chronus.seam.toe_loop import realize
from toe.poincare_golden_11d import cassini_unimodular_det


def test_cassini_on_the_11d_table():
    assert cassini_unimodular_det(5) == ((-1) ** 5)


def test_realize_runs_the_twelve_theorems():
    out = realize("job-toe", 15)
    assert out["certificate"]["is_valid"] is True
    assert out["norm_phi_sq"] < 1.0
    assert out["roundtrip_ok"] is True
    assert out["ledger_ok"] is True
    assert "T1_cassini_identity" in out["theorems"]
    assert "T4_lucas_recurrence" in out["theorems"]
    assert "T5_zeckendorf_spacing" in out["theorems"]
    assert out["device_punches"]["punch_ids"]["phi_filter_score"] == 0x1A
    assert out["device_punches"]["punch_ids"]["poincare_fold"] == 0x08
