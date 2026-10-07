import unittest

from turing_universal_quantum_computer.surface_code_exact import (
    PauliCheck,
    PlanarSurfaceCodeAlgebra,
    all_vertex_star_report,
    verify_surface_code_algebra,
)


class SurfaceCodeExactTests(unittest.TestCase):
    def test_distance_3_encodes_one_qubit_at_exact_distance_3(self):
        report = verify_surface_code_algebra(3)
        self.assertTrue(report.verified)
        self.assertEqual(report.data_edges, 3**2 + 2**2)
        self.assertEqual(report.x_checks, 3 * 2)
        self.assertEqual(report.z_checks, 3 * 2)
        self.assertEqual(report.mixed_pairs_checked, 36)
        self.assertEqual(report.noncommuting_pairs, ())
        self.assertEqual(report.logical_qubits, 1)
        self.assertTrue(report.logicals_commute_with_checks)
        self.assertEqual(report.logical_z_weight, 3)
        self.assertTrue(report.logicals_anticommute)
        self.assertEqual((report.exact_x_distance, report.exact_z_distance), (3, 3))
        self.assertEqual(report.correction_bound, 1)
        self.assertEqual(report.convention["lattice_kind"], "unrotated_square_edge_code")
        self.assertEqual(len(report.proof_digest), 64)

    def test_distance_21_checks_every_star_plaquette_pair(self):
        report = verify_surface_code_algebra(21)
        self.assertTrue(report.verified)
        self.assertEqual(report.x_checks, 21 * 20)
        self.assertEqual(report.z_checks, 21 * 20)
        self.assertEqual(report.mixed_pairs_checked, (21 * 20) ** 2)
        self.assertEqual(report.logical_qubits, 1)
        self.assertEqual(report.exact_x_distance, 21)
        self.assertEqual(report.correction_bound, 10)

    def test_same_kind_commutes_and_odd_cross_overlap_anticommutes(self):
        edge = frozenset({("v", 0, 0)})
        x_check = PauliCheck("X", "x", edge)
        z_check = PauliCheck("Z", "z", edge)
        self.assertTrue(x_check.commutes_with(x_check))
        self.assertFalse(x_check.commutes_with(z_check))

    def test_distance_31_exhaustive_declared_convention(self):
        report = verify_surface_code_algebra(31)
        self.assertTrue(report.verified)
        self.assertEqual(report.data_edges, 31**2 + 30**2)
        self.assertEqual(report.x_checks, 31 * 30)
        self.assertEqual(report.z_checks, 31 * 30)
        self.assertEqual(report.mixed_pairs_checked, (31 * 30) ** 2)
        self.assertEqual(report.logical_qubits, 1)
        self.assertEqual(report.logical_z_weight, 31)
        self.assertEqual(report.logical_x_weight, 31)
        self.assertEqual((report.exact_x_distance, report.exact_z_distance), (31, 31))
        self.assertEqual(report.correction_bound, 15)
        self.assertEqual(report.noncommuting_pairs, ())

    def test_all_vertex_star_convention_commutes_but_encodes_no_qubit(self):
        legacy = all_vertex_star_report(31)
        self.assertEqual(legacy["mixed_pairs"], 32**2 * 31**2)
        self.assertEqual(legacy["noncommuting_pairs"], 0)
        self.assertEqual(legacy["logical_qubits"], 0)
        self.assertFalse(legacy["encodes_a_qubit"])

    def test_invalid_distance_and_logical_coordinates_fail_closed(self):
        with self.assertRaises(ValueError):
            PlanarSurfaceCodeAlgebra(4)
        code = PlanarSurfaceCodeAlgebra(3)
        with self.assertRaises(ValueError):
            code.logical_z(3)
        with self.assertRaises(ValueError):
            code.logical_x(3)


if __name__ == "__main__":
    unittest.main()
