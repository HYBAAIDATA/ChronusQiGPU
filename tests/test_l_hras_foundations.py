"""Tests for ``l_hras.foundations`` — the code-level answers to the
external review of the Guardian blueprint's physics/math claims.

Each test asserts the honest statement the corresponding module makes:
universal gate set (not Clifford), exact multipartite monotones, the
discrete U(1) gauge functor's honest labels, and the declared
non-isometric/many-to-one quantization bounds.
"""

from __future__ import annotations

import numpy as np
import pytest

from l_hras import substrates
from l_hras.foundations import complexity, entanglement, gauge, quantization

# --- D1: Gottesman-Knill and the real memory bound ----------------------


def test_gate_set_is_universal_not_clifford():
    cls = complexity.gate_set_classification()
    assert cls["is_clifford_only"] is False
    assert cls["is_universal"] is True
    assert cls["gottesman_knill_applies"] is False


def test_memory_bound_is_fail_closed_cap_not_tensor_network():
    m = complexity.memory_model(complexity.max_qubits())
    assert m["within_cap"] is True
    assert "2^" in m["scaling"] or "exponential" in m["scaling"]
    over = complexity.memory_model(complexity.max_qubits() + 1)
    assert over["within_cap"] is False


def test_joint_path_is_classically_simulable():
    path = complexity.joint_state_path()
    assert path["superposition_created"] is False
    assert path["entanglement_created"] is False
    assert path["classically_simulable"] is True


def test_verify_claims_holds():
    v = complexity.verify_claims()
    assert v["cap_fail_closed"] is True
    assert v["joint_is_basis_product"] is True
    assert v["parities_exact"] is True


# --- D3: F4 naming + real multipartite monotones ------------------------


def test_f4_is_cyclotomic_field_not_lie_group():
    info = entanglement.field_info()
    assert "Q(zeta_8)" in info["mathematical_object"]
    assert "Lie group" in info["not"]


def test_bell_state_meyer_wallach_q_is_one():
    q = entanglement.meyer_wallach_q(substrates.bell_state(), 1)
    assert q["normalized"] is True
    assert q["Q"] == pytest.approx(1.0)
    assert q["party_purities"] == pytest.approx([0.5, 0.5])


def test_bell_state_schmidt_rank_two_per_cut():
    assert entanglement.schmidt_rank_per_party(substrates.bell_state(), 1) == [2, 2]


def test_six_party_joint_is_unentangled_basis_product():
    report = entanglement.six_party_report()
    assert report["parties"] == 6
    assert report["joint_is_basis_product"] is True
    assert report["meyer_wallach_q"] == 0.0
    assert report["party_purities"] == [1.0] * 6
    assert report["schmidt_ranks_per_cut"] == [1] * 6


def test_partial_trace_of_bell_is_maximally_mixed_exact():
    rho = entanglement.partial_trace(substrates.bell_state(), (0,))
    half = substrates.F4(1).real / substrates.F4(2).real
    assert rho[0][0].real == half and rho[1][1].real == half
    assert rho[0][1] == substrates.F4(0) and rho[1][0] == substrates.F4(0)
    assert entanglement.matrix_rank(rho) == 2


# --- D2: the discrete gauge functor with honest labels ------------------


def _events(n=30, seed=1):
    return np.random.default_rng(seed).random((n, 2))


def test_gauge_field_spectral_gap_positive_and_honestly_named():
    g = gauge.DiscreteGaugeField(_events(), L=16)
    assert g.spectral_gap() > 0.0
    report = gauge.pde_functor_report(_events(), L=16)
    assert "not the continuum" in report["spectral_gap"]["honest_label"]


def test_plaquette_holonomy_is_field_strength():
    g = gauge.DiscreteGaugeField(_events(), L=8)
    flux = g.flux_spectrum()
    assert flux.shape == (64,)
    # flat embedded phase field -> plaquettes are vortex defects only
    assert np.all(np.abs(flux) <= np.pi + 1e-9)


def test_escape_cost_linear_in_distance():
    g = gauge.DiscreteGaugeField(_events(), L=16)
    c1 = g.escape_cost((0, 0), (4, 0))
    c2 = g.escape_cost((0, 0), (8, 0))
    assert c2 == pytest.approx(2.0 * c1)


def test_flow_field_reports_finite_time_quantities():
    f = gauge.DiscreteFlowField(_events(), L=16)
    assert f.enstrophy() >= 0.0
    assert f.incompressibility_residual() >= 0.0
    assert f.finite_time_lyapunov((0.5, 0.5), steps=16) >= 1.0
    report = gauge.pde_functor_report(_events(), L=16)
    assert "not a global Navier-Stokes" in report["navier_stokes"]["honest_label"]


# --- D4: declared non-isometric, many-to-one quantization ---------------


def test_quantization_is_declared_many_to_one():
    q = quantization.quantize_component(0.5)
    lo = 0.5 - quantization.preimage_width() / 4
    hi = 0.5 + quantization.preimage_width() / 4
    assert quantization.quantize_component(lo) == q == quantization.quantize_component(hi)


def test_component_error_bound():
    # |x*phi^15 - round(x*phi^15)| <= 1/2  =>  |err| <= 1/(2*phi^15)
    assert quantization.component_error_bound() == pytest.approx(
        1.0 / (2.0 * substrates.golden() ** 15)
    )


def test_fold_declared_non_isometric_with_measured_distortion():
    x = np.linspace(0.01, 1.1, 11)
    report = quantization.quantization_report(x)
    assert report["fold"]["is_isometry"] is False
    assert report["quantize"]["is_bijective"] is False
    assert report["quantize"]["many_to_one"] is True
    assert report["fold"]["roundtrip_error_measured"] < 1e-12
    assert report["fold"]["jacobian_condition_number"] > 1.0


def test_certificate_masks_non_adjacent():
    x = np.linspace(0.01, 1.1, 11)
    report = quantization.quantization_report(x, "ctx")
    assert report["zeckendorf"]["all_masks_non_adjacent"] is True
