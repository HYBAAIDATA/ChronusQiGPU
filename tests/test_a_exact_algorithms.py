"""Owner A — exact-arithmetic algorithm modules.

Covers the previously untested exact-math surfaces: toe.strict_quantum's
Q(i) work-window certificate, toe.solovay_kitaev's gate synthesis,
kellogg.scales' Z[phi] exact layer, thermo/model's sourced energy model,
and mtheory's duality group arithmetic + KK spectrum. All assertions are
on exact values (Fractions, integer tuples, Zphi elements) — no
statistical checks.
"""

from __future__ import annotations

import math
from fractions import Fraction

import pytest

from kellogg import scales
from mtheory import duality as md
from mtheory.kk_spectrum import KKTower, MILLENNIUM_BOUNDS, SECTOR_RADII
from thermo import model as thermo
from toe import strict_quantum as sq
from toe import solovay_kitaev as sk

# --- toe.strict_quantum: exact Q(i) certification ---------------------------


def test_certify_work_window_exact_norms():
    r = sq.certify_work_window(bytes(range(76)), 0, 16)
    assert r["mode"] == "strict_quantum_q_i"
    # Unitarity is certified exactly: error numerator is 0.
    assert r["unitary_error_sq"]["numerator"] == 0
    # Evolution preserves the norm exactly.
    assert r["initial_norm_sq"] == r["evolved_norm_sq"]
    # Born probabilities are exact fractions summing to 1.
    total = sum(Fraction(p["numerator"], p["denominator"]) for p in r["born_probabilities"])
    assert total == 1
    # Selected basis state is the argmax, reported honestly.
    probs = [Fraction(p["numerator"], p["denominator"]) for p in r["born_probabilities"]]
    assert probs[r["selected_basis"]] == max(probs)
    # Honesty: the certificate never claims consensus authority.
    assert r["consensus_authority"] is False
    assert r["theorem_proven"] is False
    assert r["nonce_end_exclusive"] == 16


def test_certify_work_window_deterministic():
    a = sq.certify_work_window(bytes(range(76)), 8, 8)
    b = sq.certify_work_window(bytes(range(76)), 8, 8)
    assert a == b


# --- toe.solovay_kitaev ------------------------------------------------------


def test_sk_length_bound_grows_logarithmically():
    # c * log(1/eps)^p shape: finer epsilon -> larger bound.
    assert 0 < sk.sk_length_bound(0.1) < sk.sk_length_bound(0.01) < sk.sk_length_bound(1e-4)


def test_synthesize_recovers_exact_gates():
    inv_sqrt2 = 1.0 / math.sqrt(2.0)
    h = ((inv_sqrt2, inv_sqrt2), (inv_sqrt2, -inv_sqrt2))
    res = sk.synthesize(h, max_depth=3, beam_width=128)
    assert len(res) > 0
    best = min(res, key=lambda c: c["epsilon_frobenius"])
    assert best["word"] == ["H"]
    assert best["epsilon_frobenius"] < 1e-12


def test_synthesize_pauli_words():
    # The Clifford+T alphabet {H,S,T,Sdg,Tdg} has no X/Z atoms: X is
    # H.S^dg.S^dg.H and Z is S.S — the search must find them exactly.
    x = ((0, 1), (1, 0))
    res = sk.synthesize(x, max_depth=5, beam_width=128)
    best = min(res, key=lambda c: c["epsilon_frobenius"])
    assert best["word"] == ["H", "Sdg", "Sdg", "H"]
    assert best["epsilon_frobenius"] < 1e-12
    z = ((1, 0), (0, -1))
    res = sk.synthesize(z, max_depth=3, beam_width=128)
    best = min(res, key=lambda c: c["epsilon_frobenius"])
    assert best["word"] == ["S", "S"]
    assert best["epsilon_frobenius"] < 1e-12


# --- kellogg.scales: exact Z[phi] layer --------------------------------------


def test_phi_power_is_exact_zphi():
    # phi^n = F_{n-1} + F_n phi in Z[phi].
    for n in (10, 15, 20, 50):
        p = scales.phi_power(n)
        assert p == scales.Zphi(scales.fibonacci(n - 1), scales.fibonacci(n))


def test_pisot_drift_exact_element_and_norm():
    for n in range(2, 40):
        d = scales.pisot_drift(n)
        # phi^n - L_n as a Z[phi] element, norm is (-1)^n exactly.
        assert d == scales.phi_power(n) - scales.Zphi(scales.lucas(n), 0)
        assert d.norm() == (-1) ** n


def test_cassini_verify_range():
    for n in range(1, 31):
        assert scales.cassini_verify(n) is True, n


def test_zeckendorf_greedy_nonadjacent():
    for n in (1, 2, 4, 10, 100, 10_000, 28143753123):
        idx = scales.zeckendorf(n)
        assert sum(scales.fibonacci(k) for k in idx) == n
        assert all(abs(a - b) >= 2 for i, a in enumerate(idx) for b in idx[i + 1 :])


# --- thermo.model: sourced, falsifiable ---------------------------------------


def test_landauer_bound_is_kTln2():
    e = thermo.landauer_bound(1, 300.0)
    assert e == pytest.approx(1.380649e-23 * 300.0 * math.log(2))
    assert thermo.landauer_bound(8, 300.0) == pytest.approx(8 * e)


def test_adiabatic_beats_conventional_at_slow_switch():
    c, v, r = 10e-15, 1.8, 1e3
    slow = thermo.adiabatic_energy(c, v, r, 1e-6)
    fast = thermo.adiabatic_energy(c, v, r, 1e-12)
    conv = thermo.conventional_energy(c, v)
    assert conv == pytest.approx(0.5 * c * v * v)
    assert 0 < slow < conv
    assert fast > slow  # adiabatic gain requires slow switching


def test_predict_energy_technologies_and_unknown():
    for tech, expected_rel in (
        ("conventional_cmos", None),
        ("adiabatic_cmos_2lal", None),
        ("adiabatic_cmos_crl", None),
        ("superconducting_aqfp", None),
    ):
        e, unc, note = thermo.predict_energy(tech, 10**6)
        assert e > 0 and 0 < unc <= e
        assert isinstance(note, str) and note
    # The adiabatic and superconducting paths must beat conventional.
    e_conv, _, _ = thermo.predict_energy("conventional_cmos", 10**6)
    e_2lal, _, _ = thermo.predict_energy("adiabatic_cmos_2lal", 10**6)
    e_aqfp, _, _ = thermo.predict_energy("superconducting_aqfp", 10**6)
    assert e_2lal < e_conv and e_aqfp < e_conv
    with pytest.raises(ValueError, match="unknown technology"):
        thermo.predict_energy("cold fusion", 1)


def test_thermo_constants_all_sourced():
    assert thermo.all_constants_sourced() is True
    assert set(thermo.falsification_tests()) >= {
        "conventional_energy",
        "adiabatic_energy",
        "landauer_bound",
    }


# --- mtheory.duality: exact group arithmetic -----------------------------------


def test_t_duality_spectrum_invariance_exact():
    assert md.verify_t_duality(3, Fraction(2)) is True
    assert md.verify_t_duality(2, Fraction(7, 3), Fraction(2)) is True


def test_s_duality_group_laws():
    checks = md.verify_s_duality()
    assert all(checks.values()), checks
    # SL(2,Z) relations: S^2 = -I (identity as a Mobius map), (ST)^3 = -I.
    assert md.sl2z_compose(md.S_ELEMENT, md.S_ELEMENT) == (-1, 0, 0, -1)
    st = md.sl2z_compose(md.S_ELEMENT, md.T_ELEMENT)
    st3 = md.sl2z_compose(md.sl2z_compose(st, st), st)
    assert st3 == (-1, 0, 0, -1)


def test_sl2z_act_preserves_upper_half_plane_and_det():
    tau = (Fraction(1, 3), Fraction(2, 5))
    out = md.sl2z_act(md.T_ELEMENT, tau)
    assert out == (tau[0] + 1, tau[1])
    out_s = md.sl2z_act(md.S_ELEMENT, tau)
    assert out_s[1] > 0
    with pytest.raises(ValueError, match="determinant"):
        md.sl2z_act((1, 0, 0, 2), tau)
    with pytest.raises(ValueError, match="upper half-plane"):
        md.sl2z_act(md.T_ELEMENT, (Fraction(0), Fraction(-1)))


def test_iia_11d_and_u_duality_exact():
    assert all(md.verify_iia_11d().values())
    assert all(md.verify_u_duality().values())


def test_five_limits_is_involution():
    for k, v in md.FIVE_LIMITS.items():
        assert md.FIVE_LIMITS[v] == k


# --- mtheory.kk_spectrum --------------------------------------------------------


def test_kk_tower_zero_mode_and_first_level():
    t = KKTower()
    assert t.mass_squared((0,) * 7) == 0
    # Spectrum Counter contains exactly one zero mode.
    assert t.spectrum(1)[Fraction(0)] == 1
    v = t.verify_tower(2)
    assert all(v.values()), v


def test_kk_mass_formula_exact():
    t = KKTower()
    # m^2(n) = sum n_i^2 / R_i^2 — check one mode by hand.
    n = (1, 0, 0, 0, 0, 0, 0)
    expected = Fraction(1) / (SECTOR_RADII[0] ** 2)
    assert t.mass_squared(n) == expected
    # Sector 1 has radius 1/1000 -> huge mass gap vs unit-radius sectors.
    m_sector1 = t.mass_squared((1, 0, 0, 0, 0, 0, 0))
    m_sector5 = t.mass_squared((0, 0, 0, 0, 1, 0, 0))
    assert m_sector1 / m_sector5 == 1_000_000


def test_kk_radii_convention_and_validation():
    assert SECTOR_RADII == MILLENNIUM_BOUNDS
    with pytest.raises(ValueError, match="7"):
        KKTower((Fraction(1), Fraction(1)))
    with pytest.raises(ValueError, match="positive"):
        KKTower((Fraction(1),) * 6 + (Fraction(0),))
