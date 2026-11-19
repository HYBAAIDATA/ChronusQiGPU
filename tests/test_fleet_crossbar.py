# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""H4 600-cell crossbar: geometry computed from the graph, P2 diameter, geodesic routes."""

import unittest

from chronus.fleet.crossbar import CrossbarError, H4Crossbar, geometry_report, max_h4_diameter
import pytest

pytestmark = pytest.mark.real


class GeometryTests(unittest.TestCase):
    def test_counts_are_computed_from_the_graph(self):
        report = geometry_report()
        self.assertEqual(report["vertices"], 120)
        self.assertEqual(report["edges"], 720)
        self.assertEqual(report["vertex_degrees"], [12])
        self.assertEqual(report["triangular_faces"], 1200)
        self.assertEqual(report["tetrahedral_cells"], 600)
        self.assertEqual(report["vertices"] - report["edges"] + report["triangular_faces"] - report["tetrahedral_cells"], 0)

    def test_p2_diameter_is_five_and_every_vertex_has_that_eccentricity(self):
        crossbar = H4Crossbar()
        self.assertEqual(max_h4_diameter(), 5)
        for source in range(crossbar.vertex_count):
            self.assertEqual(max(crossbar.distance(source, v) for v in range(crossbar.vertex_count)), 5)

    def test_routes_are_shortest_geodesics_on_edges(self):
        crossbar = H4Crossbar()
        for src, dst in ((0, 0), (0, 1), (3, 77), (119, 5), (42, 101)):
            path = crossbar.route(src, dst)
            self.assertEqual(path[0], src)
            self.assertEqual(path[-1], dst)
            self.assertEqual(len(path) - 1, crossbar.distance(src, dst))
            self.assertLessEqual(len(path) - 1, max_h4_diameter())

    def test_non_vertices_are_rejected(self):
        crossbar = H4Crossbar()
        for bad in (-1, 120, 1.5, "3", True):
            with self.assertRaises(CrossbarError):
                crossbar.route(0, bad)


class PlacementTests(unittest.TestCase):
    def test_placement_is_deterministic_and_distinct(self):
        first, second = H4Crossbar(), H4Crossbar()
        names = [f"node-{i}" for i in range(50)]
        placed = [first.place(n) for n in names]
        self.assertEqual(placed, [second.place(n) for n in names])
        self.assertEqual(len(set(placed)), len(placed))

    def test_steal_order_is_nearest_first(self):
        crossbar = H4Crossbar()
        victims = {f"v{i}": crossbar.place(f"v{i}") for i in range(10)}
        thief = crossbar.place("thief")
        order = crossbar.steal_order("thief", victims)
        distances = [crossbar.distance(thief, victims[v]) for v in order]
        self.assertEqual(distances, sorted(distances))
        self.assertEqual(sorted(order), sorted(victims))


if __name__ == "__main__":
    unittest.main()
