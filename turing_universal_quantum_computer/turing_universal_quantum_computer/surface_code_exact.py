"""Exact CSS algebra for the planar square-lattice surface code (edge picture).

Pauli commutation is decided over GF(2): an X check and a Z check commute iff
the parity of their shared data-edge support is zero. No amplitudes, floating
point, tolerance, or hardware model enters this proof.

Lattice (distance d, unrotated, data on edges):

* vertices V(r, c), r in 0..d-1, c in 0..d-2, each carrying an X star;
* horizontal edges h(r, c), r in 0..d-1, c in 0..d-1 — the first and last of
  each row dangle off the rough left and right boundaries;
* vertical edges v(r, c), r in 0..d-2, c in 0..d-2;
* faces F(r, c), r in 0..d-2, c in 0..d-1, each carrying a Z plaquette —
  the top and bottom boundaries are smooth.

That gives n = d^2 + (d-1)^2 data edges, d(d-1) stars and d(d-1)
plaquettes, and k = 1 logical qubit. The logical qubit count and the code
distance are computed exactly (GF(2) ranks and the shortest odd-parity
boundary path, via ``kellogg.surface_code.CSSCode``), not declared.

The earlier convention placed a star on every vertex and a plaquette on every
face of a (d+1) x (d+1) grid. Those checks commute ((d+1)^2 d^2 pairs), but
they encode k = 0 logical qubits, so "distance" and "correction bound" are
undefined for it. ``all_vertex_star_report`` reproduces that count for the
record.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, FrozenSet, Iterable

Edge = tuple[str, int, int]


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True)
class PauliCheck:
    kind: str
    label: str
    support: FrozenSet[Edge]

    def __post_init__(self) -> None:
        if self.kind not in {"X", "Z"}:
            raise ValueError("Pauli check kind must be X or Z")
        if not self.label or not self.support:
            raise ValueError("Pauli checks require a label and non-empty support")

    def commutes_with(self, other: "PauliCheck") -> bool:
        if self.kind == other.kind:
            return True
        return len(self.support & other.support) % 2 == 0


@dataclass(frozen=True)
class SurfaceCodeConvention:
    """The exact convention under which an algebra report is exhaustive."""

    lattice_kind: str = "unrotated_square_edge_code"
    boundary_kind: str = "rough_left_right_smooth_top_bottom"
    data_placement: str = "edges"
    stabilizer_support: str = "weight_4_bulk_weight_3_boundary"
    distance_definition: str = "exact_minimum_nontrivial_logical_weight"

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class SurfaceCodeAlgebraReport:
    convention: dict[str, str]
    distance: int
    data_edges: int
    x_checks: int
    z_checks: int
    mixed_pairs_checked: int
    noncommuting_pairs: tuple[str, ...]
    logical_qubits: int
    logicals_commute_with_checks: bool
    logical_z_weight: int
    logical_x_weight: int
    logicals_anticommute: bool
    exact_x_distance: int
    exact_z_distance: int
    correction_bound: int
    verified: bool
    proof_digest: str

    def unsigned_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row.pop("proof_digest")
        return row


class PlanarSurfaceCodeAlgebra:
    """Planar edge code with exact star/plaquette CSS checks and exact distance."""

    def __init__(self, distance: int):
        distance = int(distance)
        if distance < 3 or distance % 2 == 0:
            raise ValueError("distance must be an odd integer >= 3")
        self.distance = distance
        self.convention = SurfaceCodeConvention()

    def horizontal_edges(self) -> tuple[Edge, ...]:
        d = self.distance
        return tuple(("h", row, col) for row in range(d) for col in range(d))

    def vertical_edges(self) -> tuple[Edge, ...]:
        d = self.distance
        return tuple(("v", row, col) for row in range(d - 1) for col in range(d - 1))

    def data_edges(self) -> FrozenSet[Edge]:
        return frozenset(self.horizontal_edges() + self.vertical_edges())

    def star_checks(self) -> tuple[PauliCheck, ...]:
        d = self.distance
        checks = []
        for row in range(d):
            for col in range(d - 1):
                support = {("h", row, col), ("h", row, col + 1)}
                if row > 0:
                    support.add(("v", row - 1, col))
                if row < d - 1:
                    support.add(("v", row, col))
                checks.append(PauliCheck("X", f"star:{row}:{col}", frozenset(support)))
        return tuple(checks)

    def plaquette_checks(self) -> tuple[PauliCheck, ...]:
        d = self.distance
        checks = []
        for row in range(d - 1):
            for col in range(d):
                support = {("h", row, col), ("h", row + 1, col)}
                if col > 0:
                    support.add(("v", row, col - 1))
                if col < d - 1:
                    support.add(("v", row, col))
                checks.append(PauliCheck("Z", f"plaquette:{row}:{col}", frozenset(support)))
        return tuple(checks)

    def logical_z(self, row: int = 0) -> PauliCheck:
        """Z along one row of horizontal edges, rough boundary to rough boundary."""
        d = self.distance
        if not 0 <= row < d:
            raise ValueError("logical Z row is outside the lattice")
        support = frozenset(("h", row, col) for col in range(d))
        return PauliCheck("Z", f"logical_z:{row}", support)

    def logical_x(self, column: int = 0) -> PauliCheck:
        """X down one column of horizontal edges, smooth boundary to smooth boundary."""
        d = self.distance
        if not 0 <= column < d:
            raise ValueError("logical X column is outside the lattice")
        support = frozenset(("h", row, column) for row in range(d))
        return PauliCheck("X", f"logical_x:{column}", support)

    @staticmethod
    def _pair_labels(
        x_checks: Iterable[PauliCheck], z_checks: Iterable[PauliCheck]
    ) -> tuple[str, ...]:
        failures = []
        for x_check in x_checks:
            for z_check in z_checks:
                if not x_check.commutes_with(z_check):
                    failures.append(f"{x_check.label}|{z_check.label}")
        return tuple(failures)

    def css_code(self):
        """The same code as GF(2) bitsets, for exact rank and distance checks."""
        from kellogg.surface_code import CSSCode

        index = {edge: i for i, edge in enumerate(sorted(self.data_edges()))}

        def bits(check: PauliCheck) -> int:
            return sum(1 << index[e] for e in check.support)

        return CSSCode(
            n=len(index),
            hx=[bits(c) for c in self.star_checks()],
            hz=[bits(c) for c in self.plaquette_checks()],
            logical_x=bits(self.logical_x(0)),
            logical_z=bits(self.logical_z(0)),
            distance=self.distance,
        )

    def verify(self) -> SurfaceCodeAlgebraReport:
        x_checks = self.star_checks()
        z_checks = self.plaquette_checks()
        failures = self._pair_labels(x_checks, z_checks)
        logical_z = self.logical_z(0)
        logical_x = self.logical_x(0)
        anticommute = not logical_x.commutes_with(logical_z)
        logicals_ok = all(logical_z.commutes_with(x) for x in x_checks) and all(
            logical_x.commutes_with(z) for z in z_checks
        )
        exact = self.css_code().verify()
        unsigned = {
            "convention": self.convention.as_dict(),
            "distance": self.distance,
            "data_edges": len(self.data_edges()),
            "x_checks": len(x_checks),
            "z_checks": len(z_checks),
            "mixed_pairs_checked": len(x_checks) * len(z_checks),
            "noncommuting_pairs": failures,
            "logical_qubits": exact.logical_qubits,
            "logicals_commute_with_checks": logicals_ok,
            "logical_z_weight": len(logical_z.support),
            "logical_x_weight": len(logical_x.support),
            "logicals_anticommute": anticommute,
            "exact_x_distance": exact.exact_x_distance,
            "exact_z_distance": exact.exact_z_distance,
            "correction_bound": (min(exact.exact_x_distance, exact.exact_z_distance) - 1) // 2,
        }
        unsigned["verified"] = bool(
            not failures
            and logicals_ok
            and anticommute
            and exact.logical_qubits == 1
            and exact.logicals_nontrivial
            and exact.exact_x_distance == exact.exact_z_distance == self.distance
        )
        return SurfaceCodeAlgebraReport(**unsigned, proof_digest=_digest(unsigned))


def verify_surface_code_algebra(distance: int = 21) -> SurfaceCodeAlgebraReport:
    return PlanarSurfaceCodeAlgebra(distance).verify()


def all_vertex_star_report(distance: int) -> dict[str, Any]:
    """The earlier star-on-every-vertex convention, counted exactly: k = 0."""
    from kellogg.surface_code import edge_star_report

    return edge_star_report(int(distance))


__all__ = [
    "Edge",
    "PauliCheck",
    "PlanarSurfaceCodeAlgebra",
    "SurfaceCodeAlgebraReport",
    "SurfaceCodeConvention",
    "all_vertex_star_report",
    "verify_surface_code_algebra",
]
