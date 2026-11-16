"""Bounded TURING exact-state scheduling for the polyhedral mining lanes.

Quantum state evolution chooses traversal order; SHA-256d target membership
remains the oracle used by the geometric/Galois candidate engine. Every order
is a permutation, so scheduling cannot discard a lane or duplicate its work.
"""

from fractions import Fraction
from math import gcd

import numpy as np
from chronus.tensor.geodesic import GeodesicScheduler, PhiMemoryHierarchy, TopologicalIntegrityGate

from chronus.hendrix import GF257
from turing.exact.core.state import StateZetaP, superpose
from turing.exact.core.unitary import ProjectiveUnitaryZetaP, UnitaryZetaP
from turing.exact.measurement.born import project, projective_born_probability
from turing.exact.physics.cayley import cayley_evolution
from turing.exact.physics.swarm import SwarmZetaP
from turing.exact.physics.tunneling import DiscreteBarrier, transmission_coefficient_exact
from turing.exact.ring.matrix import MatrixZetaP
from turing.exact.ring.zeta import ZetaP


class TuringMiningScheduler:
    """Two-amplitude exact register; fixed-size evolution and bounded coefficients."""

    def __init__(self, seed: bytes):
        if not isinstance(seed, bytes) or len(seed) != 32:
            raise ValueError("Scheduler seed must contain exactly 32 bytes")
        self._state_type = StateZetaP
        self._ring_type = ZetaP
        self._probability = projective_born_probability
        self._seed_offset = int.from_bytes(seed[:4], "big")
        one, zero = ZetaP.one(3), ZetaP.zero(3)
        state = superpose(StateZetaP.basis(0, 2, 3), StateZetaP.basis(1, 2, 3),
                          one * (1 + seed[4] % 3), one * (1 + seed[5] % 3))
        update = UnitaryZetaP(MatrixZetaP(2, 2, [[zero, one], [one, zero]], 3))
        self.swarm = SwarmZetaP(state, update, project)
        self._initial_state = state
        # A finite discrete cooling schedule. Continuous adiabatic annealing is
        # explicitly an Obstruction in TURING and is not substituted here.
        self._evolution = []
        self.couplings = (3, 2, 1)
        for coupling in self.couplings:
            h = MatrixZetaP(2, 2, [[zero, -one * coupling], [one * coupling, zero]], 3)
            result = cayley_evolution(h)
            if not isinstance(result, tuple):
                raise ArithmeticError("TURING Cayley evolution is obstructed")
            self._evolution.append(ProjectiveUnitaryZetaP(*result))
        barrier = DiscreteBarrier(1, [zero], one)
        transmission = transmission_coefficient_exact(barrier, one * (1 + seed[6] % 2))
        if not hasattr(transmission, "den"):
            raise ArithmeticError("TURING discrete transmission is obstructed")
        self._stride_seed = 2 * (transmission.den + GF257.discrete_log(1 + seed[7])) + 1
        self.steps = 0
        self.last_evidence = {}
        self.geodesic = GeodesicScheduler()
        self.memory = PhiMemoryHierarchy()
        self.integrity = TopologicalIntegrityGate(tolerance=0.0)

    def order(self, lane_count: int, start: int = 0) -> list[int]:
        if type(lane_count) is not int or not 1 <= lane_count <= 32:
            raise ValueError("lane_count must be between 1 and 32")
        # Reset after one cooling cycle to bound integer growth over long runs.
        phase = self.steps % len(self._evolution)
        if phase == 0:
            self.swarm.state = self._initial_state
        self.swarm.step()
        self.swarm.state = self._evolution[phase].apply(self.swarm.state)
        left = Fraction(*self._probability(self.swarm.state, 0))
        right = Fraction(*self._probability(self.swarm.state, 1))
        if left + right != 1 or left < 0 or right < 0:
            raise ArithmeticError("TURING scheduler probability invariant failed")
        stride = self._stride_seed
        while gcd(stride, lane_count) != 1:
            stride += 2
        if left < right:
            stride = -stride
        offset = (start + self._seed_offset + phase) % lane_count
        order = [(offset + index * stride) % lane_count for index in range(lane_count)]
        if len(set(order)) != lane_count:
            raise ArithmeticError("TURING scheduler lost lane coverage")
        # Chronus/Tensor is an internal organ. Its queue chooses dispatch order;
        # folded residency materialises only the selected row. No tensor output
        # can alter, drop, duplicate or resize a certified nonce lane.
        resident = np.asarray(order, dtype=np.uint8).reshape(-1, 1)
        state = self.memory.store("lane-order", resident)
        for position, lane in enumerate(order):
            distance = (position - phase) % lane_count
            self.geodesic.submit(position, distance=distance)
        dispatched = []
        while len(self.geodesic):
            position = self.geodesic.pop()
            row = self.memory.load_rows("lane-order", position, position + 1)
            if not self.integrity.verify(row, resident[position:position + 1]).passed:
                raise ArithmeticError("Geodesic lane reconstruction failed integrity")
            dispatched.append(int(row[0, 0]))
        if sorted(dispatched) != list(range(lane_count)):
            raise ArithmeticError("Geodesic advice changed certified lane coverage")
        order = dispatched
        self.last_evidence = {
            "engine": "turing-exact", "phase": phase,
            "born_weights": [str(left), str(right)], "lane_order": order,
            "transmission_stride": self._stride_seed,
            "overlay": {"dodecahedron_faces": 12, "icosahedron_faces": 20}
            if lane_count == 32 else None,
        }
        self.steps += 1
        return order
