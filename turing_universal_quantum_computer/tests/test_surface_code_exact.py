import unittest

from turing_universal_quantum_computer.surface_code_exact import (
    PauliCheck,
    PlanarSurfaceCodeAlgebra,
    verify_surface_code_algebra,
)


class SurfaceCodeExactTests(unittest.TestCase):
    def test_distance_3_commutation_and_logical_anticommutation(self):
        report = verify_surface_code_algebra(3)
        self.assertTrue(report.verified)
        self.assertEqual(report.data_edges, 24)
        self.assertEqual(report.x_checks, 16)
        self.assertEqual(report.z_checks, 9)
        self.assertEqual(report.mixed_pairs_checked, 144)
        self.assertEqual(report.noncommuting_pairs, ())
        self.assertEqual(report.logical_z_weight, 3)
        self.assertTrue(report.logicals_anticommute)
        self.assertEqual(report.correction_bound, 1)
        self.assertEqual(len(report.proof_digest), 64)

    def test_distance_21_checks_every_star_plaquette_pair(self):
        report = verify_surface_code_algebra(21)
        self.assertTrue(report.verified)
        self.assertEqual(report.x_checks, 22**2)
        self.assertEqual(report.z_checks, 21**2)
        self.assertEqual(report.mixed_pairs_checked, 22**2 * 21**2)
        self.assertEqual(report.logical_z_weight, 21)
        self.assertEqual(report.correction_bound, 10)

    def test_same_kind_commutes_and_odd_cross_overlap_anticommutes(self):
        edge = frozenset({("v", 0, 0)})
        x_check = PauliCheck("X", "x", edge)
        z_check = PauliCheck("Z", "z", edge)
        self.assertTrue(x_check.commutes_with(x_check))
        self.assertFalse(x_check.commutes_with(z_check))

    def test_invalid_distance_and_logical_coordinates_fail_closed(self):
        with self.assertRaises(ValueError):
            PlanarSurfaceCodeAlgebra(4)
        code = PlanarSurfaceCodeAlgebra(3)
        with self.assertRaises(ValueError):
            code.logical_z(4)
        with self.assertRaises(ValueError):
            code.logical_x(3)


if __name__ == "__main__":
    unittest.main()
