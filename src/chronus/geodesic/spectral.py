"""Certified integer H4 graph Laplacian, separate from smooth Laplace-Beltrami.

The primary exact object is L=D-A over Z, on the 120 vertices of the
600-cell graph. Its real symmetric spectrum exists, but numerical
eigenvectors from scipy/numpy are explicitly APPROXIMATE, not exact
cyclotomic eigenvectors. For an exact spectral decomposition an algebraic
minimal polynomial and certified projectors must be supplied separately.
"""
from __future__ import annotations

from dataclasses import dataclass

from chronus.ns_dec import build_h4_600_cell_polytope


@dataclass(frozen=True)
class H4GraphLaplacian:
    adjacency: tuple[tuple[int, ...], ...]

    @classmethod
    def canonical(cls) -> "H4GraphLaplacian":
        topo = build_h4_600_cell_polytope()
        n = topo["vertices"]
        neighbors: list[set[int]] = [set() for _ in range(n)]
        for a, b in topo["edge_index_pairs"]:
            neighbors[a].add(b)
            neighbors[b].add(a)
        graph = cls(tuple(tuple(sorted(v)) for v in neighbors))
        if (graph.vertex_count, graph.edge_count, graph.degree) != (120, 720, 12):
            raise AssertionError("not the canonical H4 600-cell graph")
        return graph

    @property
    def vertex_count(self) -> int:
        return len(self.adjacency)

    @property
    def edge_count(self) -> int:
        return sum(map(len, self.adjacency)) // 2

    @property
    def degree(self) -> int:
        degrees = {len(row) for row in self.adjacency}
        if len(degrees) != 1:
            raise ValueError("graph is not regular")
        return next(iter(degrees))

    def laplacian_matrix(self) -> tuple[tuple[int, ...], ...]:
        d = self.degree
        return tuple(tuple(
            (d if i == j else (-1 if j in self.adjacency[i] else 0))
            for j in range(self.vertex_count))
            for i in range(self.vertex_count))

    def apply(self, x: tuple[int, ...]) -> tuple[int, ...]:
        """Exact integer Lx, with no floating point."""
        if len(x) != self.vertex_count or any(type(v) is not int for v in x):
            raise ValueError("expected 120 integer stalk values")
        return tuple(
            self.degree * x[i] - sum(x[j] for j in self.adjacency[i])
            for i in range(self.vertex_count)
        )

    def quadratic_form(self, x: tuple[int, ...]) -> int:
        """Certificate: x^T L x = sum_{edges}(x_i-x_j)^2 >= 0."""
        if len(x) != self.vertex_count or any(type(v) is not int for v in x):
            raise ValueError("expected 120 integer stalk values")
        energy = sum(
            (x[i] - x[j]) ** 2
            for i, neighbors in enumerate(self.adjacency)
            for j in neighbors if i < j
        )
        if energy != sum(x[i] * v for i, v in enumerate(self.apply(x))):
            raise ArithmeticError("H4 Laplacian energy identity failed")
        return energy

    def exact_invariants(self) -> dict[str, int | bool]:
        n = self.vertex_count
        d = self.degree
        # Tr(L)=nd; Tr(L^2)=n(d^2+d) for a simple d-regular graph.
        ones = (1,) * n
        return {
            "dimension": n,
            "edges": self.edge_count,
            "degree": d,
            "trace": n * d,
            "trace_square": n * (d * d + d),
            "constant_kernel_verified": self.apply(ones) == (0,) * n,
            "positive_semidefinite_identity": True,
        }

    def numerical_spectrum(self) -> dict[str, object]:
        """Optional approximate diagnostic, NEVER an exact-eigenvalue proof."""
        import numpy as np

        matrix = np.asarray(self.laplacian_matrix(), dtype=np.float64)
        eigenvalues, eigenvectors = np.linalg.eigh(matrix)
        residual = np.max(np.abs(matrix @ eigenvectors -
                                  eigenvectors * eigenvalues[None, :]))
        return {
            "classification": "APPROXIMATE_FLOAT64_DIAGNOSTIC",
            "eigenvalues": eigenvalues,
            "eigenvectors": eigenvectors,
            "max_residual": float(residual),
            "certifies_exact_eigenvalues": False,
            "yang_mills_mass_gap_proven": False,
        }
