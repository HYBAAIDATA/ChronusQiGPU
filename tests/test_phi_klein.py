import numpy as np

from chronus.seam.toe_loop import realize
from toe.geometric_contract import cassini_table_ok
from toe.phi_klein import HOROSPHERES, klein_identity, phi_norm


def test_horospheres_are_lucas():
    assert HOROSPHERES == (2, 1, 3, 4, 7, 11, 18, 29, 47, 76, 123)


def test_klein_identity_on_a_seed():
    x = np.linspace(0.01, 0.2, 11)
    assert klein_identity(x)
    assert phi_norm(x) / (1.0 + phi_norm(x)) < 1.0


def test_realize_both_twelves():
    out = realize("job-klein", 15)
    assert out["geometric"]["G10_norm_ball"] is True
    assert out["geometric"]["G8_fold_unfold"] is True
    assert out["geometric"]["G5_zeckendorf"] is True
    assert out["punch_isa"]["fold"] == 0x08
    assert out["punch_isa"]["phi_filter"] == 0x1A
    assert cassini_table_ok(5)
    assert out["passed"] is True
