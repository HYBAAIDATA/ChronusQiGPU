"""Exact PEPS and tree tensor network amplitudes over Kellogg Q(zeta8).

Sites have one physical leg followed by named virtual bonds. Fixing the
physical indices and eliminating bonds computes an amplitude without
materialising the statevector. Contraction cost depends on graph width and
bond dimensions. Explicit intermediate and arithmetic-work budgets are
checked before each contraction; exceeding either refuses, never truncates.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from math import prod
from typing import Mapping

from .certificate import TensorCertificate, certify, cex_digest
from .cyclotomic import ZERO8, Q8


@dataclass(frozen=True)
class GraphSite:
    physical_dimension: int
    bonds: tuple[str, ...]
    dimensions: tuple[int, ...]
    data: tuple[Q8, ...]

    def __post_init__(self) -> None:
        if type(self.physical_dimension) is not int or self.physical_dimension < 1:
            raise ValueError("physical dimension must be positive integer")
        if (
            len(self.bonds) != len(self.dimensions)
            or len(set(self.bonds)) != len(self.bonds)
            or any(not isinstance(b, str) or not b for b in self.bonds)
        ):
            raise ValueError("bonds must be distinct names with matching dimensions")
        if any(type(d) is not int or d < 1 for d in self.dimensions):
            raise ValueError("bond dimensions must be positive integers")
        if len(self.data) != self.physical_dimension * prod(self.dimensions):
            raise ValueError("site data does not match shape")
        if any(not isinstance(v, Q8) for v in self.data):
            raise ValueError("site data requires Q8 exact field elements")


@dataclass(frozen=True)
class GraphContraction:
    amplitude: Q8
    peak_elements: int
    scalar_products: int
    certificate: TensorCertificate


class ExactGraphNetwork:
    """Pairwise-bond network; site tuples are shared without conversion copies."""

    def __init__(self, sites: Mapping[str, GraphSite], *, topology: str = "graph") -> None:
        if not sites or any(not isinstance(k, str) or not k for k in sites):
            raise ValueError("network requires named sites")
        self._sites = dict(sites)
        owners: dict[str, list[tuple[str, int]]] = {}
        for name, site in self._sites.items():
            for bond, dim in zip(site.bonds, site.dimensions):
                owners.setdefault(bond, []).append((name, dim))
        if any(len(v) != 2 or v[0][1] != v[1][1] for v in owners.values()):
            raise ValueError("every virtual bond must join two sites with matching dimensions")
        adjacent = {name: set() for name in self._sites}
        for endpoints in owners.values():
            a, b = endpoints[0][0], endpoints[1][0]
            adjacent[a].add(b)
            adjacent[b].add(a)
        visited, pending = set(), [next(iter(self._sites))]
        while pending:
            site = pending.pop()
            if site not in visited:
                visited.add(site)
                pending.extend(adjacent[site] - visited)
        if len(visited) != len(sites):
            raise ValueError("network must be connected")
        if topology not in {"graph", "tree"}:
            raise ValueError("unknown network topology")
        if topology == "tree" and len(owners) != len(sites) - 1:
            raise ValueError("tree network must be acyclic")
        self.topology = topology
        self.dimensions = {b: endpoints[0][1] for b, endpoints in owners.items()}

    @classmethod
    def peps(cls, rows: int, cols: int, sites: Mapping[str, GraphSite]) -> "ExactGraphNetwork":
        """Admit a rectangular open-boundary PEPS with site names 'row,col'.

        Bond names are free, but each bond must join nearest neighbours and
        every nearest-neighbour pair must have exactly one bond.
        """
        if any(type(n) is not int or n < 1 for n in (rows, cols)):
            raise ValueError("PEPS dimensions must be positive integers")
        if rows * cols != len(sites):
            raise ValueError("PEPS sites must cover the rectangle")
        expected = {f"{r},{c}" for r in range(rows) for c in range(cols)}
        if set(sites) != expected:
            raise ValueError("PEPS sites must cover the rectangle")
        network = cls(sites)
        owners: dict[str, list[str]] = {}
        for name, site in sites.items():
            for b in site.bonds:
                owners.setdefault(b, []).append(name)
        pairs = [frozenset(v) for v in owners.values()]
        expected_pairs = {
            frozenset((f"{r},{c}", f"{nr},{nc}"))
            for r in range(rows)
            for c in range(cols)
            for nr, nc in ((r + 1, c), (r, c + 1))
            if nr < rows and nc < cols
        }
        if set(pairs) != expected_pairs or len(pairs) != len(expected_pairs):
            raise ValueError("PEPS requires precisely the rectangular nearest-neighbour bonds")
        network.topology = "peps"
        return network

    def amplitude(
        self,
        physical: Mapping[str, int],
        *,
        max_elements: int = 65536,
        max_scalar_products: int = 1000000,
    ) -> GraphContraction:
        """Contract a fixed physical assignment with no singular-value discard."""
        if any(type(b) is not int or b < 1 for b in (max_elements, max_scalar_products)):
            raise ValueError("contraction budgets must be positive integers")
        if set(physical) != set(self._sites):
            raise ValueError("one physical index per site required")
        factors = []
        peak, work = 1, 0
        for name, site in sorted(self._sites.items()):
            p = physical[name]
            if type(p) is not int or not 0 <= p < site.physical_dimension:
                raise ValueError("physical index outside site domain")
            size = prod(site.dimensions)
            if size > max_elements:
                raise MemoryError("site exceeds intermediate element budget")
            peak = max(peak, size)
            indices = product(*(range(d) for d in site.dimensions))
            factors.append((site.bonds, dict(zip(indices, site.data[p * size : (p + 1) * size]))))
        while len(factors) > 1:
            candidates = []
            for i, (a, _) in enumerate(factors):
                for j in range(i + 1, len(factors)):
                    b = factors[j][0]
                    shared = set(a) & set(b)
                    if not shared:
                        continue
                    outer = tuple(k for k in a + b if k not in shared)
                    size = prod(self.dimensions[k] for k in outer)
                    cost = size * prod(self.dimensions[k] for k in shared)
                    candidates.append((size, cost, i, j, outer, tuple(sorted(shared))))
            if not candidates:
                raise ValueError("disconnected intermediate network")
            size, cost, i, j, outer, shared = min(candidates)
            if size > max_elements or work + cost > max_scalar_products:
                raise MemoryError("exact contraction exceeds declared budget")
            a, av = factors[i]
            b, bv = factors[j]
            data = {}
            for out in product(*(range(self.dimensions[k]) for k in outer)):
                assignment = dict(zip(outer, out))
                total = ZERO8
                for inner in product(*(range(self.dimensions[k]) for k in shared)):
                    assignment.update(zip(shared, inner))
                    total = (
                        total
                        + av[tuple(assignment[k] for k in a)] * bv[tuple(assignment[k] for k in b)]
                    )
                data[out] = total
            work += cost
            peak = max(peak, size)
            factors.pop(j)
            factors.pop(i)
            factors.append((outer, data))
        amplitude = factors[0][1][()]
        identity = {
            name: {
                "physical_dimension": s.physical_dimension,
                "bonds": s.bonds,
                "dimensions": s.dimensions,
                "data": s.data,
            }
            for name, s in self._sites.items()
        }
        certificate = certify(
            "graph_amplitude",
            "Q(zeta8)",
            "kellogg.exact_graph/v1",
            cex_digest(identity),
            cex_digest(amplitude),
            parameters={
                "physical": dict(physical),
                "topology": self.topology,
                "max_elements": max_elements,
                "max_scalar_products": max_scalar_products,
            },
            invariants={"discarded_weight": 0, "peak_elements": peak, "scalar_products": work},
        )
        return GraphContraction(amplitude, peak, work, certificate)
