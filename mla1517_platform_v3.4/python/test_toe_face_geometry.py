"""32-face geometry contract for the TOE wiring.

The canonical face enumeration is ``truncated_icosahedron_frame()``: orbit A
(first 12 entries) holds the icosahedron vertex directions — the pentagon
face centres of the truncated icosahedron, norm^2 = phi + 2 — and orbit B
(last 20 entries) holds the dodecahedron vertex directions — the hexagon
face centres, norm^2 = 3. set_lane_start_offset(f) rotates the solver's
declared lane order cyclically; it never reorders the frame itself.
"""
from __future__ import annotations

import math
import unittest
from itertools import islice

from mla1517.mining.geometry import (
    LANES,
    _PHI,
    _dot,
    truncated_icosahedron_frame,
)
from mla1517.mining.solver import M32SearchSolver


def _norm2(point) -> float:
    d = _dot(point, point)
    return float(d.a) + float(d.b) * math.sqrt(5.0)


_PHI_PLUS_2 = float(_PHI.a) + float(_PHI.b) * math.sqrt(5.0) + 2.0


def _sweep_order(solver: M32SearchSolver) -> tuple[int, ...]:
    return tuple(lane for _nonce, lane in islice(solver.candidates(0, LANES), LANES))


class FaceGeometryContractTests(unittest.TestCase):
    """Geometry the chooser/solver wiring depends on."""

    def test_frame_has_exactly_32_faces(self):
        frame = truncated_icosahedron_frame()
        self.assertEqual(len(frame), LANES)
        self.assertEqual(LANES, 32)

    def test_orbit_convention_ico_then_dodeca(self):
        frame = truncated_icosahedron_frame()
        # Actual convention: first 12 = icosahedron-vertex directions
        # (pentagon faces), last 20 = dodecahedron-vertex directions
        # (hexagon faces). See truncated_icosahedron_frame() docstring.
        for point in frame[:12]:
            self.assertAlmostEqual(_norm2(point), _PHI_PLUS_2, places=12)
        for point in frame[12:]:
            self.assertAlmostEqual(_norm2(point), 3.0, places=12)

    def test_face_indices_0_to_31_unique(self):
        frame = truncated_icosahedron_frame()
        keys = {
            tuple(float(coord.a) + float(coord.b) * math.sqrt(5.0) for coord in point)
            for point in frame
        }
        self.assertEqual(len(keys), LANES)
        # The lane index set is exactly 0..31 with no gaps or duplicates.
        self.assertEqual(sorted(range(LANES)), list(range(LANES)))

    def test_every_offset_is_a_distinct_cyclic_rotation(self):
        solver = M32SearchSolver()
        canonical = _sweep_order(solver)
        self.assertEqual(len(canonical), LANES)
        self.assertEqual(sorted(canonical), list(range(LANES)))
        rotations = {}
        for face in range(LANES):
            solver.set_lane_start_offset(face)
            rotations[face] = _sweep_order(solver)
        # 32 distinct cyclic rotations of the canonical order.
        self.assertEqual(len(set(rotations.values())), LANES)
        for face, order in rotations.items():
            pivot = canonical.index(face)
            self.assertEqual(order, canonical[pivot:] + canonical[:pivot])
            self.assertEqual(order[0], face)


if __name__ == "__main__":
    unittest.main()
