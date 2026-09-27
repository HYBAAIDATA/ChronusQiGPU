"""H4 / binary icosahedral action on the 600-cell frame.

Vertices of generate_600cell_vertices() are the unit icosians 2I.
A rotation is x |-> p x conj(q) with (p,q)~(-p,-q).
That permutes vertices and tetrahedral cells; it is an isometry of S^3,
not of the full 11D phi-metric.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

from igpu.h4_600 import cell_normals, generate_600cell_cells, generate_600cell_vertices, lift_fold_11d

Quat = Tuple[float, float, float, float]


def qmul(a: Quat, b: Quat) -> Quat:
    a0, a1, a2, a3 = a
    b0, b1, b2, b3 = b
    return (
        a0 * b0 - a1 * b1 - a2 * b2 - a3 * b3,
        a0 * b1 + a1 * b0 + a2 * b3 - a3 * b2,
        a0 * b2 - a1 * b3 + a2 * b0 + a3 * b1,
        a0 * b3 + a1 * b2 - a2 * b1 + a3 * b0,
    )


def qconj(a: Quat) -> Quat:
    return (a[0], -a[1], -a[2], -a[3])


def act(p: Quat, x: Quat, q: Quat) -> Quat:
    return qmul(p, qmul(x, qconj(q)))


class H4Frame:
    def __init__(self) -> None:
        self.vertices: Tuple[Quat, ...] = generate_600cell_vertices()
        self.cells: Tuple[Tuple[int, int, int, int], ...] = generate_600cell_cells(self.vertices)

    def nearest_vertex(self, x: Quat) -> int:
        best_i = 0
        best = 1e9
        for i, v in enumerate(self.vertices):
            d = sum((a - b) ** 2 for a, b in zip(x, v))
            if d < best:
                best = d
                best_i = i
        return best_i

    def permute_vertices(self, p: Quat, q: Quat) -> List[int]:
        return [self.nearest_vertex(act(p, v, q)) for v in self.vertices]

    def permute_cells(self, p: Quat, q: Quat) -> List[int]:
        sigma = self.permute_vertices(p, q)
        lookup: Dict[Tuple[int, int, int, int], int] = {
            tuple(sorted(c)): i for i, c in enumerate(self.cells)
        }
        out: List[int] = []
        for tet in self.cells:
            image = tuple(sorted(sigma[i] for i in tet))
            out.append(lookup[image])
        return out

    def is_permutation(self, sigma: Sequence[int]) -> bool:
        return sorted(sigma) == list(range(len(sigma)))

    def frames_11d_permuted(self, p: Quat, q: Quat) -> List[Tuple[float, ...]]:
        sigma = self.permute_cells(p, q)
        normals = cell_normals(self.vertices, self.cells)
        return [lift_fold_11d(normals[sigma[i]])[0] for i in range(len(normals))]


def rotation_pair_count() -> int:
    n = len(generate_600cell_vertices())
    return (n * n) // 2


def symmetry_report(p: Quat | None = None, q: Quat | None = None) -> dict:
    frame = H4Frame()
    p = p or (1.0, 0.0, 0.0, 0.0)
    q = q or (frame.vertices[1] if len(frame.vertices) > 1 else (1.0, 0.0, 0.0, 0.0))
    vperm = frame.permute_vertices(p, q)
    cperm = frame.permute_cells(p, q)
    ident = p == (1.0, 0.0, 0.0, 0.0) and q == (1.0, 0.0, 0.0, 0.0)
    return {
        "vertices": len(frame.vertices),
        "cells": len(frame.cells),
        "binary_icosahedral_order": len(frame.vertices),
        "rotation_group_order_expected": 7200,
        "full_h4_order_expected": 14400,
        "rotation_pairs_mod_sign": rotation_pair_count(),
        "vertex_perm_ok": frame.is_permutation(vperm),
        "cell_perm_ok": frame.is_permutation(cperm),
        "stabilizer_vertex": "H3 order 120",
        "stabilizer_cell": "S4 = W(A3) order 24",
        "metric_claim": "H4 isometry of S^3 skeleton; not of full 11D phi-metric",
        "identity_fixes_vertices": ident and vperm == list(range(len(vperm))),
    }
