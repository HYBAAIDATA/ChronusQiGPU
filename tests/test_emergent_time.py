"""
tests/test_emergent_time.py -- Unit and integration tests for Page-Wootters emergent time
and Coppo, Cuccoli & Verrucchi (2024) magnetic clock model.
"""

from __future__ import annotations

import unittest
import numpy as np

from chronus.theory.emergent_time import (
    PageWoottersSystem,
    CoppoMagneticClock,
    von_neumann_entropy,
    test_zero_entanglement_absence_of_time as check_zero_entanglement_absence_of_time,
    _self_test,
)


class TestPageWoottersEmergentTime(unittest.TestCase):
    def test_self_test_passes(self):
        result = _self_test()
        self.assertEqual(result, "emergent_time._self_test: PASS")

    def test_wheeler_dewitt_stationary_constraint(self):
        """Global state |Psi> must be an exact zero-eigenvector of H_tot."""
        pw = PageWoottersSystem.create(dim_S=8, omega_S=1.5)
        psi = pw.create_entangled_stationary_state()

        h_psi = pw.H_tot @ psi
        residual = np.linalg.norm(h_psi)
        self.assertLess(residual, 1e-12, "H_tot |Psi> != 0 violated Wheeler-DeWitt constraint")

    def test_schrodinger_emergence_fidelity(self):
        """Conditioning on clock readout <t|_C must yield exact unitary Schrödinger evolution."""
        pw = PageWoottersSystem.create(dim_S=8, omega_S=1.0)
        psi = pw.create_entangled_stationary_state()

        for t in [0.0, 0.25, 0.5, 1.0, 2.5, 5.0]:
            projected, schrodinger, fidelity = pw.project_at_time(psi, t)
            self.assertAlmostEqual(
                fidelity,
                1.0,
                places=6,
                msg=f"Fidelity drifted from 1.0 at relational time t={t}",
            )
            # Both projected and theoretical states must be normalized
            self.assertAlmostEqual(np.linalg.norm(projected), 1.0, places=6)
            self.assertAlmostEqual(np.linalg.norm(schrodinger), 1.0, places=6)

    def test_zero_entanglement_freezes_time_and_dynamics(self):
        """Unentangled product states satisfying H_tot |Psi> = 0 must exhibit zero dynamics."""
        res = check_zero_entanglement_absence_of_time(dim_S=8)
        self.assertLess(res["entanglement_entropy"], 1e-12)
        self.assertLess(res["dynamics_variance"], 1e-12)
        self.assertEqual(res["is_static"], 1.0)

    def test_von_neumann_entropy_bounds(self):
        """Entangled state must have maximal/high entanglement entropy ln(dim_S)."""
        dim_S = 8
        pw = PageWoottersSystem.create(dim_S=dim_S)
        psi = pw.create_entangled_stationary_state()

        entropy = von_neumann_entropy(psi, pw.dim_C, pw.dim_S)
        max_entropy = np.log(dim_S)
        self.assertAlmostEqual(entropy, max_entropy, places=6)


class TestCoppoMagneticClock(unittest.TestCase):
    def test_magnetic_clock_convergence_monotonicity(self):
        """Fidelity with continuous Schrödinger time must increase monotonically with clock spin J."""
        spins = [5, 10, 50, 200, 1000]
        fidelities = []
        for J in spins:
            res = CoppoMagneticClock.simulate_scaling(J=J, n_max=4, steps=10)
            fidelities.append(res["mean_fidelity"])

        for i in range(len(fidelities) - 1):
            self.assertGreater(
                fidelities[i + 1],
                fidelities[i],
                f"Fidelity did not increase from J={spins[i]} to J={spins[i+1]}",
            )

    def test_macroscopic_clock_limit(self):
        """Macroscopic clock J=10000 must reproduce continuous time with relative error < 1e-5."""
        res = CoppoMagneticClock.simulate_scaling(J=10000, n_max=5, steps=12)
        self.assertGreater(res["mean_fidelity"], 0.99999)
        self.assertLess(res["relative_error"], 1e-5)


if __name__ == "__main__":
    unittest.main()
