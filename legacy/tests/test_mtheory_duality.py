"""Exact-arithmetic tests for mtheory.kk_spectrum and mtheory.duality.

Every expected value below is computed by hand in integers/Fractions —
no floats anywhere in this file.
"""

from __future__ import annotations

from collections import Counter
from fractions import Fraction

from mtheory.kk_spectrum import KKTower, MILLENNIUM_BOUNDS, SECTOR_RADII
from mtheory.duality import (
    FIVE_LIMITS,
    S_ELEMENT,
    T_ELEMENT,
    bosonic_spectrum,
    circle_spectrum,
    coupling_from_tau,
    eleven_d_coupling,
    iia_to_11d,
    s_dualize,
    sl2z_act,
    sl2z_compose,
    t_dualize,
    tau_from_coupling,
    u_dualize,
    verify_iia_11d,
    verify_s_duality,
    verify_t_duality,
    verify_u_duality,
)


# ---------------------------------------------------------------------------
# KK tower on T^7
# ---------------------------------------------------------------------------

def test_sector_radii_are_millennium_bounds_exact():
    # Repo convention: the seven Millennium sector invariants as Fractions.
    assert MILLENNIUM_BOUNDS == (
        Fraction(1, 1000),
        Fraction(15),
        Fraction(1, 2),
        Fraction(2),
        Fraction(1),
        Fraction(1),
        Fraction(1),
    )
    assert SECTOR_RADII == MILLENNIUM_BOUNDS
    assert all(isinstance(r, Fraction) for r in SECTOR_RADII)


def test_mass_squared_exact_values_sector_radii():
    tower = KKTower(SECTOR_RADII)
    zero = (0, 0, 0, 0, 0, 0, 0)
    assert tower.mass_squared(zero) == 0
    # n_i^2 / R_i^2 by hand: R = (1/1000, 15, 1/2, 2, 1, 1, 1)
    assert tower.mass_squared((1, 0, 0, 0, 0, 0, 0)) == Fraction(1_000_000)
    assert tower.mass_squared((0, 1, 0, 0, 0, 0, 0)) == Fraction(1, 225)
    assert tower.mass_squared((0, 0, 1, 0, 0, 0, 0)) == Fraction(4)
    assert tower.mass_squared((0, 0, 0, 1, 0, 0, 0)) == Fraction(1, 4)
    assert tower.mass_squared((0, 0, 0, 0, 1, 0, 0)) == Fraction(1)
    # Mixed mode: 3^2/15^2 + 1^2/(1/2)^2 = 9/225 + 4 = 1/25 + 4 = 101/25.
    assert tower.mass_squared((0, 3, 1, 0, 0, 0, 0)) == Fraction(101, 25)
    # Evenness on the same vector, reflected.
    assert tower.mass_squared((0, -3, -1, 0, 0, 0, 0)) == Fraction(101, 25)


def test_spectrum_unit_torus_hand_computed():
    """On the unit T^7 with |n_i| <= 1, m^2 = |n|^2 = k has degeneracy
    C(7,k) * 2^k (choose the nonzero coords, then their signs)."""
    tower = KKTower((Fraction(1),) * 7)
    expected = Counter(
        {
            Fraction(0): 1,    # C(7,0)*1
            Fraction(1): 14,   # C(7,1)*2
            Fraction(2): 84,   # C(7,2)*4
            Fraction(3): 280,  # C(7,3)*8
            Fraction(4): 560,  # C(7,4)*16
            Fraction(5): 672,  # C(7,5)*32
            Fraction(6): 448,  # C(7,6)*64
            Fraction(7): 128,  # C(7,7)*128
        }
    )
    spec = tower.spectrum(1)
    assert spec == expected
    assert sum(spec.values()) == 3**7
    for m2, d in expected.items():
        assert tower.degeneracy(m2, 1) == d


def test_degeneracy_full_lattice_hand_computed():
    """Full-lattice degeneracies on the unit T^7, counted by hand.

    m^2 = 4:  four +-1 coords  -> C(7,4)*2^4 = 560
              one +-2 coord    -> 7*2          =  14    total 574
    m^2 = 5:  five +-1 coords  -> C(7,5)*2^5 = 672
              +-2 and +-1      -> 7*6*2*2      = 168    total 840
    m^2 = 8:  four +-1 and ... enumerate:
              (+-2, +-2)       -> C(7,2)*4     =  84
              eight +-1? impossible (max 7) ->
              (+-2, +-1 x4)    -> 7*C(6,4)*2*16= 3360  ... skip 8.
    """
    tower = KKTower((Fraction(1),) * 7)
    assert tower.degeneracy(Fraction(0)) == 1
    assert tower.degeneracy(Fraction(1)) == 14
    assert tower.degeneracy(Fraction(2)) == 84
    assert tower.degeneracy(Fraction(3)) == 280
    assert tower.degeneracy(Fraction(4)) == 560 + 14
    assert tower.degeneracy(Fraction(5)) == 672 + 168


def test_mixed_radius_tower_hand_computed():
    """R = (2, 1, 1, 1, 1, 1, 1), |n_i| <= 1.

    m^2 = n_1^2/4 + (number of nonzero coords among axes 2..7).
    m^2 = 1/4:  +-e_1                     -> 2
    m^2 = 1:    +-e_j (j>=2), 12 modes, plus +-2? no: n_1=+-2 not in box.
                also (n_1=... no other way)          -> 12
    m^2 = 5/4:  +-e_1 + one +-e_j         -> 2*6*2 = 24
    """
    tower = KKTower((Fraction(2),) + (Fraction(1),) * 6)
    spec = tower.spectrum(1)
    assert spec[Fraction(0)] == 1
    assert spec[Fraction(1, 4)] == 2
    assert spec[Fraction(1)] == 12
    assert spec[Fraction(5, 4)] == 24
    # Total count sanity.
    assert sum(spec.values()) == 3**7


def test_verify_tower_exact():
    for radii in (
        SECTOR_RADII,
        (Fraction(1),) * 7,
        (Fraction(2), Fraction(3, 5), Fraction(7), Fraction(1, 9),
         Fraction(4), Fraction(11, 2), Fraction(1, 3)),
    ):
        checks = KKTower(radii).verify_tower(1)
        assert all(checks.values()), (radii, checks)


def test_tower_rejects_bad_input():
    import pytest

    with pytest.raises(ValueError):
        KKTower((Fraction(1),) * 6)  # not 7 radii
    with pytest.raises(ValueError):
        KKTower((Fraction(0),) + (Fraction(1),) * 6)  # non-positive radius


# ---------------------------------------------------------------------------
# T-duality
# ---------------------------------------------------------------------------

def test_bosonic_spectrum_exact_values():
    ap = Fraction(1)
    # E^2 = (n/R)^2 + (wR)^2, by hand.
    assert bosonic_spectrum(1, 0, Fraction(2), ap) == Fraction(1, 4)
    assert bosonic_spectrum(0, 1, Fraction(2), ap) == Fraction(4)
    assert bosonic_spectrum(1, 1, Fraction(2), ap) == Fraction(17, 4)
    assert bosonic_spectrum(0, 0, Fraction(2), ap) == Fraction(0)
    assert bosonic_spectrum(2, -1, Fraction(3, 5), ap) == Fraction(100, 9) + Fraction(9, 25)
    # Non-unit alpha': E^2 = (n/R)^2 + (wR/a')^2, a' = 1/4, R = 3:
    # (2/3)^2 + (1*3/(1/4))^2 = 4/9 + 144 = 1300/9.
    assert bosonic_spectrum(2, 1, Fraction(3), Fraction(1, 4)) == Fraction(1300, 9)


def test_t_dualize_returns_swapped_data():
    assert t_dualize(3, -2, Fraction(2), Fraction(1)) == (-2, 3, Fraction(1, 2))
    assert t_dualize(1, 4, Fraction(3, 5), Fraction(2)) == (4, 1, Fraction(10, 3))


def test_t_duality_multiset_invariance():
    """Full truncated-spectrum Counter invariance under R -> a'/R."""
    for R in (Fraction(2), Fraction(3, 5)):
        for n_max in (1, 2, 3):
            assert verify_t_duality(n_max, R)
            before = circle_spectrum(n_max, R)
            after = circle_spectrum(n_max, 1 / R)
            assert before == after
            assert sum(before.values()) == (2 * n_max + 1) ** 2


def test_t_duality_nonunit_alpha_prime():
    ap = Fraction(1, 4)
    R = Fraction(3)
    assert verify_t_duality(2, R, ap)
    assert circle_spectrum(2, R, ap) == circle_spectrum(2, ap / R, ap)


# ---------------------------------------------------------------------------
# S-duality / SL(2,Z)
# ---------------------------------------------------------------------------

def test_s_dualize_exact():
    assert s_dualize(Fraction(2, 5)) == Fraction(5, 2)
    assert s_dualize(s_dualize(Fraction(2, 5))) == Fraction(2, 5)
    assert s_dualize(Fraction(1)) == Fraction(1)


def test_sl2z_S_involution_on_tau():
    """S^2 = id as a Mobius map on Gaussian-rational tau (exact pairs)."""
    for tau in (
        (Fraction(1, 3), Fraction(2, 5)),
        (Fraction(0), Fraction(7, 11)),
        (Fraction(-3, 4), Fraction(5)),
    ):
        assert sl2z_act(S_ELEMENT, sl2z_act(S_ELEMENT, tau)) == tau
    # S^2 = -I as a matrix — same Mobius transformation.
    assert sl2z_compose(S_ELEMENT, S_ELEMENT) == (-1, 0, 0, -1)


def test_sl2z_T_shifts_axion_exactly():
    tau = (Fraction(1, 3), Fraction(2, 5))
    assert sl2z_act(T_ELEMENT, tau) == (Fraction(4, 3), Fraction(2, 5))


def test_sl2z_imaginary_part_inverts_g():
    """tau = i/g -> S -> i*g: Im(tau) maps 1/g -> g exactly."""
    g = Fraction(2, 5)
    tau = tau_from_coupling(g)
    assert tau == (Fraction(0), Fraction(5, 2))
    out = sl2z_act(S_ELEMENT, tau)
    assert out == (Fraction(0), Fraction(2, 5))
    assert coupling_from_tau(out) == s_dualize(g) == Fraction(5, 2)


def test_verify_s_duality_all_checks():
    checks = verify_s_duality()
    assert all(checks.values()), checks


def test_five_limits_involution_laws():
    # The table is a bijection of its own label set and an involution.
    labels = set(FIVE_LIMITS)
    assert set(FIVE_LIMITS.values()) == labels
    for label in labels:
        assert FIVE_LIMITS[FIVE_LIMITS[label]] == label
    # Named laws.
    assert FIVE_LIMITS["I"] == "HET_SO32"
    assert FIVE_LIMITS["HET_SO32"] == "I"
    assert FIVE_LIMITS["IIB"] == "IIB"
    assert FIVE_LIMITS["IIA"] == "M11"
    assert FIVE_LIMITS["M11"] == "IIA"
    assert FIVE_LIMITS["HET_E8E8"] == "M11_Z2"
    assert FIVE_LIMITS["M11_Z2"] == "HET_E8E8"


# ---------------------------------------------------------------------------
# IIA <-> 11D
# ---------------------------------------------------------------------------

def test_iia_11d_roundtrip_and_growth_exact():
    g_s, l_p = Fraction(2, 5), Fraction(1)
    R11 = iia_to_11d(g_s, l_p)
    assert R11 == Fraction(2, 5)
    assert eleven_d_coupling(R11, l_p) == g_s
    assert iia_to_11d(eleven_d_coupling(R11, l_p), l_p) == R11
    # g_s -> lam*g_s grows R_11 by exactly lam.
    lam = Fraction(7, 3)
    assert iia_to_11d(lam * g_s, l_p) == lam * R11
    assert all(verify_iia_11d().values())


def test_iia_11d_nontrivial_planck_length():
    g_s, l_p = Fraction(3, 7), Fraction(11, 13)
    R11 = iia_to_11d(g_s, l_p)
    assert R11 == Fraction(33, 91)
    assert eleven_d_coupling(R11, l_p) == g_s
    checks = verify_iia_11d(g_s, l_p, Fraction(5, 2))
    assert all(checks.values()), checks


# ---------------------------------------------------------------------------
# U-duality: T x S on disjoint factors
# ---------------------------------------------------------------------------

def _sample_state():
    return (
        (1, -2, 0),
        (0, 3, -1),
        (Fraction(2), Fraction(3, 5), Fraction(7)),
        Fraction(2, 5),
        Fraction(1),
    )


def test_u_dualize_exact_action():
    state = _sample_state()
    out = u_dualize([("T", 0), ("S",)], state)
    # T on circle 0: n0<->w0, R0 -> 1/R0 = 1/2.  S: g -> 5/2.
    assert out == (
        (0, -2, 0),
        (1, 3, -1),
        (Fraction(1, 2), Fraction(3, 5), Fraction(7)),
        Fraction(5, 2),
        Fraction(1),
    )


def test_u_duality_t_and_s_commute():
    state = _sample_state()
    for i in range(3):
        assert u_dualize([("T", i), ("S",)], state) == u_dualize(
            [("S",), ("T", i)], state
        )
    # T factors on different circles commute.
    assert u_dualize([("T", 0), ("T", 2)], state) == u_dualize(
        [("T", 2), ("T", 0)], state
    )
    # Each factor is an involution.
    assert u_dualize([("S",), ("S",)], state) == state
    assert u_dualize([("T", 1), ("T", 1)], state) == state
    assert all(verify_u_duality().values())


def test_no_floats_in_public_results():
    """Exact-type spot audit: everything returned is int/Fraction/tuple/Counter."""
    tower = KKTower(SECTOR_RADII)
    assert isinstance(tower.mass_squared((1,) * 7), Fraction)
    assert all(isinstance(k, Fraction) for k in tower.spectrum(1))
    e2 = bosonic_spectrum(1, 1, Fraction(2))
    assert isinstance(e2, Fraction)
    n2, w2, R2 = t_dualize(1, 1, Fraction(2))
    assert isinstance(n2, int) and isinstance(w2, int) and isinstance(R2, Fraction)
    assert isinstance(iia_to_11d(Fraction(1, 3), Fraction(2)), Fraction)
    re_im = sl2z_act(S_ELEMENT, (Fraction(0), Fraction(5, 2)))
    assert all(isinstance(v, Fraction) for v in re_im)
