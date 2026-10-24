"""
Aggregates every module in theory/ -- the real, computable mathematics for
the 10 "unbuilt" physical-hardware sections in the user's "Real Maths for
the Unbuilt Parts" document. Per explicit instruction, none of this
simulates or specifies physical apparatus; every function here is pure,
hardware-agnostic mathematics, genuinely computed and self-tested.
"""
from __future__ import annotations

from typing import Any, Dict

import numpy as np

from . import (
    oscillator_array,
    cryogenics,
    superconductivity,
    photonics,
    anyons,
    metrology,
    qcd,
    control,
    error_correction,
    chemistry,
    emergent_time,
)
from ..academic.caltech import Caltech_Surface_Code


def self_test_all() -> Dict[str, str]:
    return {
        "oscillator_array": oscillator_array._self_test(),
        "cryogenics": cryogenics._self_test(),
        "superconductivity": superconductivity._self_test(),
        "photonics": photonics._self_test(),
        "anyons": anyons._self_test(),
        "metrology": metrology._self_test(),
        "qcd": qcd._self_test(),
        "control": control._self_test(),
        "error_correction": error_correction._self_test(),
        "chemistry": chemistry._self_test(),
        "emergent_time": emergent_time._self_test(),
    }


def run_unbuilt_maths() -> Dict[str, Any]:
    report: Dict[str, Any] = {}

    omega = np.array([5.0e9, 5.02e9, 4.98e9, 5.01e9])
    positions = np.array([[0, 0, 0], [10e-6, 0, 0], [0, 10e-6, 0], [10e-6, 10e-6, 0]])
    moments = np.array([[1e-9, 0, 0]] * 4)
    g = oscillator_array.coupling_matrix_from_point_currents(omega, positions, moments)
    modes = oscillator_array.diagonalize_oscillator_array(omega, g)
    report["oscillator_array"] = {
        "input_frequencies_hz": omega.tolist(),
        "coupling_matrix_hz": g.tolist(),
        "normal_mode_frequencies_hz": modes.normal_frequencies.tolist(),
        "zero_point_energy_j": modes.zero_point_energy_j,
    }

    report["cryogenics"] = {
        "dilution_fridge_stage_cooling_power_w": cryogenics.dilution_fridge_stage_powers(25_000.0),
        "bose_occupation_at_15mK_5GHz": cryogenics.bose_occupation(2 * np.pi * 5e9, 0.015),
        "cooling_power_constant_cp_w": cryogenics.cooling_power_thermodynamic(1e-3, lambda t: 20.0, 0.015, 300.0),
    }

    tc = 9.2
    delta0 = 1.76 * 1.380649e-23 * tc
    lam = superconductivity.penetration_depth(9.109e-31, 5.6e28)
    xi = superconductivity.coherence_length(1.6e6, delta0)
    rs = superconductivity.surface_resistance(4.2, 2 * np.pi * 1.3e9, lam, delta0, tc)
    report["superconductivity"] = {
        "gap_at_4.2K_j": superconductivity.bcs_gap(4.2, delta0, tc),
        "penetration_depth_m": lam,
        "coherence_length_m": xi,
        "surface_resistance_ohm": rs,
        "quality_factor": superconductivity.quality_factor(1.0, rs) if rs > 0 else float("inf"),
    }

    report["photonics"] = {
        "propagation_constant_propagating": str(
            photonics.propagation_constant(2 * np.pi * 2e14, 4e-7 * np.pi, 2.1 * photonics.EPS_0, 1e5)
        ),
        "coupling_vs_separation_m": {
            str(d): photonics.gaussian_mode_overlap_coupling(1.5, 1.44, 1.55e-6, 3e-6, d)
            for d in [2e-6, 5e-6, 10e-6]
        },
    }

    report["anyons"] = {
        "braid_relations": anyons.verify_braid_relations(),
        "markov_trace_sigma1_cubed": str(anyons.markov_trace([1, 1, 1])),
    }

    r = 1.2
    report["metrology"] = {
        "qfi_squeezed_light_r=1.2": metrology.qfi_squeezed_light(r),
        "cramer_rao_bound_N=1000": metrology.cramer_rao_bound(metrology.qfi_squeezed_light(r), 1000),
    }

    q0_sq = 91.19 ** 2
    report["qcd"] = {
        "alpha_s_at_MZ": qcd.running_coupling(q0_sq, q0_sq, 0.118, n_f=5),
        "alpha_s_at_1TeV": qcd.running_coupling(1000.0 ** 2, q0_sq, 0.118, n_f=5),
        "debye_mass_squared_at_200MeV": qcd.debye_screening_mass_squared(1.0, 200.0),
    }

    a = np.array([[0.0, 1.0], [-1.0, -0.2]])
    c = np.eye(2)
    q_noise = 0.01 * np.eye(2)
    r_noise = 0.1 * np.eye(2)
    p = control.solve_continuous_riccati(a, c, q_noise, r_noise)
    report["control"] = {
        "steady_state_error_covariance": p.tolist(),
        "kalman_gain": (p @ c.T @ np.linalg.inv(r_noise)).tolist(),
    }

    code = Caltech_Surface_Code(distance=3)
    report["error_correction"] = error_correction.verify_stabilizer_algebra(code)

    scf = chemistry.run_scf()
    report["chemistry"] = {
        "total_energy_hartree_like": scf.total_energy,
        "kinetic_energy": scf.kinetic_energy,
        "external_energy": scf.external_energy,
        "hartree_energy": scf.hartree_energy,
        "exchange_energy": scf.exchange_energy,
        "n_electrons_integrated": scf.n_electrons_integrated,
        "converged": scf.converged,
        "iterations": scf.iterations,
    }

    report["emergent_time"] = {
        "page_wootters_self_test": emergent_time._self_test(),
        "coppo_magnetic_clock_scaling_j1000": emergent_time.CoppoMagneticClock.simulate_scaling(J=1000, n_max=5),
        "zero_entanglement_check": emergent_time.test_zero_entanglement_absence_of_time(dim_S=8),
    }

    return report
