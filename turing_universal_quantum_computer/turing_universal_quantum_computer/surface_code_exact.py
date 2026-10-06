"""Exact CSS commutation proof for a planar square-lattice surface code.

Pauli commutation is decided over GF(2): an X check and a Z check commute iff
the parity of their shared data-edge support is zero. No amplitudes, floating
point, tolerance, or hardware model enters this proof.
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
class SurfaceCodeAlgebraReport:
    distance: int
    data_edges: int
    x_checks: int
    z_checks: int
    mixed_pairs_checked: int
    noncommuting_pairs: tuple[str, ...]
    logical_z_weight: int
    logical_x_weight: int
    logicals_anticommute: bool
    correction_bound: int
    verified: bool
    proof_digest: str

    def unsigned_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row.pop("proof_digest")
        return row


class PlanarSurfaceCodeAlgebra:
    """Square-lattice edge code with exact star/plaquette CSS checks."""

    def __init__(self, distance: int):
        distance = int(distance)
        if distance < 3 or distance % 2 == 0:
            raise ValueError("distance must be an odd integer >= 3")
        self.distance = distance

    def horizontal_edges(self) -> tuple[Edge, ...]:
        d = self.distance
        return tuple(("h", row, col) for row in range(d + 1) for col in range(d))

    def vertical_edges(self) -> tuple[Edge, ...]:
        d = self.distance
        return tuple(("v", row, col) for row in range(d) for col in range(d + 1))

    def data_edges(self) -> FrozenSet[Edge]:
        return frozenset(self.horizontal_edges() + self.vertical_edges())

    def star_checks(self) -> tuple[PauliCheck, ...]:
        d = self.distance
        checks = []
        for row in range(d + 1):
            for col in range(d + 1):
                support = set()
                if col > 0:
                    support.add(("h", row, col - 1))
                if col < d:
                    support.add(("h", row, col))
                if row > 0:
                    support.add(("v", row - 1, col))
                if row < d:
                    support.add(("v", row, col))
                checks.append(PauliCheck("X", f"star:{row}:{col}", frozenset(support)))
        return tuple(checks)

    def plaquette_checks(self) -> tuple[PauliCheck, ...]:
        d = self.distance
        checks = []
        for row in range(d):
            for col in range(d):
                support = frozenset(
                    {
                        ("h", row, col),
                        ("h", row + 1, col),
                        ("v", row, col),
                        ("v", row, col + 1),
                    }
                )
                checks.append(PauliCheck("Z", f"plaquette:{row}:{col}", support))
        return tuple(checks)

    def logical_z(self, column: int = 0) -> PauliCheck:
        d = self.distance
        if not 0 <= column <= d:
            raise ValueError("logical Z column is outside the lattice")
        support = frozenset(("v", row, column) for row in range(d))
        return PauliCheck("Z", f"logical_z:{column}", support)

    def logical_x(self, row: int = 0) -> PauliCheck:
        d = self.distance
        if not 0 <= row < d:
            raise ValueError("logical X row is outside the lattice")
        support = frozenset(("v", row, col) for col in range(d + 1))
        return PauliCheck("X", f"logical_x:{row}", support)

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

    def verify(self) -> SurfaceCodeAlgebraReport:
        x_checks = self.star_checks()
        z_checks = self.plaquette_checks()
        failures = self._pair_labels(x_checks, z_checks)
        logical_z = self.logical_z(0)
        logical_x = self.logical_x(0)
        anticommute = not logical_x.commutes_with(logical_z)
        unsigned = {
            "distance": self.distance,
            "data_edges": len(self.data_edges()),
            "x_checks": len(x_checks),
            "z_checks": len(z_checks),
            "mixed_pairs_checked": len(x_checks) * len(z_checks),
            "noncommuting_pairs": failures,
            "logical_z_weight": len(logical_z.support),
            "logical_x_weight": len(logical_x.support),
            "logicals_anticommute": anticommute,
            "correction_bound": (self.distance - 1) // 2,
            "verified": not failures
            and anticommute
            and len(logical_z.support) == self.distance,
        }
        return SurfaceCodeAlgebraReport(**unsigned, proof_digest=_digest(unsigned))


def verify_surface_code_algebra(distance: int = 21) -> SurfaceCodeAlgebraReport:
    return PlanarSurfaceCodeAlgebra(distance).verify()


__all__ = [
    "Edge",
    "PauliCheck",
    "PlanarSurfaceCodeAlgebra",
    "SurfaceCodeAlgebraReport",
    "verify_surface_code_algebra",
]
