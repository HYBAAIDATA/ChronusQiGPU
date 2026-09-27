from kellogg.scales import binet_fold, cassini_verify, fibonacci, pisot_wind, zeckendorf
from omega.axiom import AXIOM, THEOREMS
from omega.catalog import live_checks


def test_axiom_is_named():
    assert "mathematics" in AXIOM
    assert set(THEOREMS) >= {f"Ω{i}" for i in range(1, 27)}


def test_kellogg_is_the_substrate():
    assert binet_fold(8).a == fibonacci(8)
    assert cassini_verify(6)
    assert sum(fibonacci(k) for k in zeckendorf(144)) == 144
    assert len(pisot_wind(tuple(0.1 * i for i in range(11)), 2)) == 11


def test_omega_live_checks():
    c = live_checks()
    assert c["Ω8"]["ok"] is True
    assert c["Ω9"]["ok"] is True
    assert c["Ω10"]["ok"] is True
    assert c["Ω11"]["t11"] is True
    assert c["YM"]["status"] == "gap"
