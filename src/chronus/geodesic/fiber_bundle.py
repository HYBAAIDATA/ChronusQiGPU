"""Explicit finite H4 fiber coordinates and checked discrete transitions.

This defines a 32-domain base index and 600-point dual fiber without
assuming a continuous smooth bundle or asserting nontrivial topology.
Transport links must be supplied explicitly and must act as automorphisms
of the exact 120-cell graph. Holonomy is computed from actual links;
a phi-weighted metric alone is not evidence of twisting.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from chronus.geodesic.dual_120cell import build_dual_120_cell

FIBER_SIZE = 600
BASE_SIZE = 32
TOTAL_SECTIONS = BASE_SIZE * FIBER_SIZE
Permutation = tuple[int, ...]
IDENTITY: Permutation = tuple(range(FIBER_SIZE))


def _validate_permutation(perm: Permutation) -> None:
    if len(perm) != FIBER_SIZE or set(perm) != set(IDENTITY):
        raise ValueError("fiber transition must be a bijection on all 600 vertices")
    edges = frozenset(build_dual_120_cell().edges)
    for a, b in edges:
        if tuple(sorted((perm[a], perm[b]))) not in edges:
            raise ValueError("transition does not preserve H4 dual adjacency")


def _compose(first: Permutation, second: Permutation) -> Permutation:
    """Apply first, then second."""
    return tuple(second[first[x]] for x in IDENTITY)


def _inverse(perm: Permutation) -> Permutation:
    result = [0] * FIBER_SIZE
    for i, p in enumerate(perm):
        result[p] = i
    return tuple(result)


def inversion_transition() -> Permutation:
    """Central inversion of the regular 120-cell: exact H4 automorphism."""
    points = build_dual_120_cell().vertices
    lookup = {point: i for i, point in enumerate(points)}
    inverted = tuple(lookup[
        tuple((-a, -b) for a, b in point)
    ] for point in points)
    _validate_permutation(inverted)
    if _compose(inverted, inverted) != IDENTITY:
        raise AssertionError("central inversion must be an involution")
    return inverted


def encode_basis_index(domain: int, vertex: int) -> int:
    """Canonical lazy basis coordinate for the optional 32 x 600 tensor space."""
    if type(domain) is not int or not 0 <= domain < BASE_SIZE:
        raise ValueError("domain out of range")
    if type(vertex) is not int or not 0 <= vertex < FIBER_SIZE:
        raise ValueError("fiber vertex out of range")
    return domain * FIBER_SIZE + vertex


def decode_basis_index(index: int) -> tuple[int, int]:
    if type(index) is not int or not 0 <= index < TOTAL_SECTIONS:
        raise ValueError("combined index out of range")
    return divmod(index, FIBER_SIZE)


@dataclass(frozen=True)
class FiniteH4FiberBundle:
    """Finite index bundle with explicit automorphism-valued edge transports."""
    transitions: Mapping[tuple[int, int], Permutation]

    def __post_init__(self) -> None:
        # Freeze the exact graph-automorphism transition certificate before
        # validation, otherwise later caller mutation bypasses the gates.
        snapshot = {tuple(edge): tuple(perm)
                    for edge, perm in self.transitions.items()}
        object.__setattr__(self, "transitions", MappingProxyType(snapshot))
        for (i, j), perm in self.transitions.items():
            if i == j or not 0 <= i < BASE_SIZE or not 0 <= j < BASE_SIZE:
                raise ValueError("transition endpoints must be distinct M32 indices")
            _validate_permutation(perm)
            if (j, i) in self.transitions:
                if self.transitions[(j, i)] != _inverse(perm):
                    raise ValueError("reverse transition is not the inverse")

    def transition(self, i: int, j: int) -> Permutation:
        if not 0 <= i < BASE_SIZE or not 0 <= j < BASE_SIZE:
            raise ValueError("M32 domain outside range")
        if i == j:
            return IDENTITY
        if (i, j) in self.transitions:
            return self.transitions[(i, j)]
        if (j, i) in self.transitions:
            return _inverse(self.transitions[(j, i)])
        raise KeyError(f"no provided transport edge between domains {i}, {j}")

    def transport(self, path: tuple[int, ...], vertex: int) -> int:
        if type(vertex) is not int or not 0 <= vertex < FIBER_SIZE:
            raise ValueError("fiber vertex outside range")
        if not path or any(type(i) is not int or not 0 <= i < BASE_SIZE for i in path):
            raise ValueError("path must contain M32 domain indices")
        for i, j in zip(path, path[1:]):
            vertex = self.transition(i, j)[vertex]
        return vertex

    def holonomy(self, closed_path: tuple[int, ...]) -> Permutation:
        if len(closed_path) < 2 or closed_path[0] != closed_path[-1]:
            raise ValueError("holonomy requires a closed path")
        result = IDENTITY
        for i, j in zip(closed_path, closed_path[1:]):
            result = _compose(result, self.transition(i, j))
        return result

    def cocycle_verified(self, triples: tuple[tuple[int, int, int], ...]) -> bool:
        """Check g_ac = g_bc circ g_ab on explicitly specified triple overlaps."""
        return all(
            self.transition(a, c) ==
            _compose(self.transition(a, b), self.transition(b, c))
            for a, b, c in triples
        )

    def status(self) -> dict[str, object]:
        return {
            "base_domains": BASE_SIZE,
            "fiber_vertices": FIBER_SIZE,
            "finite_pairs": TOTAL_SECTIONS,
            "transition_edges_provided": len(self.transitions),
            "smooth_bundle_verified": False,
            "nontrivial_holonomy_claimed": False,
        }
