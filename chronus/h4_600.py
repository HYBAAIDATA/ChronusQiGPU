"""H4 600-cell frame for the iGPU solver.

120 vertices of the hexacosichoron; 600 tetrahedral cells from the
first-neighbor graph (degree 12). Each cell centroid is lifted into R^11
and folded with the same phi-norm Klein map as search_crystal.

NON-PRODUCTION FP64 REFERENCE.

Retained for tests, research lineage, and FP64 consumers only. It is NOT on
the canonical production route: production geometry, planning and execution
run through chronus/exact_geometry.py (exact Q(phi) H4/600-cell via chronos_one_igpu.family_algebra), which computes in exact Q(phi) rational arithmetic.
Nothing here produces certificates, evidence, or mining decisions.
"""

from __future__ import annotations

from chronos_one_igpu.reference_contract import require_reference, reference_only, require_production_context
import itertools
import math
from typing import List, Sequence, Tuple

PHI = (1.0 + math.sqrt(5.0)) / 2.0
INV_PHI = PHI - 1.0
DIM = 11


def _norm4(v: Sequence[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def _unit4(v: Sequence[float]) -> Tuple[float, float, float, float]:
    n = _norm4(v)
    if n == 0:
        return (0.0, 0.0, 0.0, 0.0)
    return (v[0] / n, v[1] / n, v[2] / n, v[3] / n)


def _parity(perm: Sequence[int]) -> int:
    return sum(1 for i in range(4) for j in range(i + 1, 4) if perm[i] > perm[j]) % 2


def generate_600cell_vertices() -> Tuple[Tuple[float, float, float, float], ...]:
    require_reference('chronus.h4_600')
    pts: List[Tuple[float, float, float, float]] = []
    for i in range(4):
        for s in (1.0, -1.0):
            v = [0.0, 0.0, 0.0, 0.0]
            v[i] = s
            pts.append(tuple(v))
    for signs in itertools.product((-0.5, 0.5), repeat=4):
        pts.append(signs)
    base = (PHI, 1.0, INV_PHI, 0.0)
    for perm in itertools.permutations(range(4)):
        if _parity(perm):
            continue
        coords = tuple(base[i] for i in perm)
        for signs in itertools.product((-1.0, 1.0), repeat=4):
            pts.append(tuple(signs[k] * coords[k] / 2.0 for k in range(4)))
    uniq: List[Tuple[float, float, float, float]] = []
    for p in pts:
        if any(sum((a - b) ** 2 for a, b in zip(p, q)) < 1e-12 for q in uniq):
            continue
        uniq.append(p)
    return tuple(uniq)


def _neighbor_distance(verts: Sequence[Sequence[float]]) -> float:
    best = 1e9
    a = verts[0]
    for b in verts[1:]:
        d = _norm4((a[0] - b[0], a[1] - b[1], a[2] - b[2], a[3] - b[3]))
        if 1e-9 < d < best:
            best = d
    return best


def generate_600cell_cells(
    verts: Sequence[Sequence[float]] | None = None,
) -> Tuple[Tuple[int, int, int, int], ...]:
    require_reference('chronus.h4_600')
    verts = list(verts or generate_600cell_vertices())
    n = len(verts)
    edge = _neighbor_distance(verts)
    tol = edge * 1.05
    nbrs = [[] for _ in range(n)]
    for i in range(n):
        vi = verts[i]
        for j in range(i + 1, n):
            vj = verts[j]
            d = _norm4((vi[0] - vj[0], vi[1] - vj[1], vi[2] - vj[2], vi[3] - vj[3]))
            if d <= tol:
                nbrs[i].append(j)
                nbrs[j].append(i)
    nset = [set(nbrs[k]) for k in range(n)]
    cells = set()
    for i in range(n):
        for a, b, c in itertools.combinations(nbrs[i], 3):
            if b in nset[a] and c in nset[a] and c in nset[b]:
                cells.add(tuple(sorted((i, a, b, c))))
    return tuple(sorted(cells))


def cell_normals(
    verts: Sequence[Sequence[float]] | None = None,
    cells: Sequence[Sequence[int]] | None = None,
) -> Tuple[Tuple[float, float, float, float], ...]:
    require_reference('chronus.h4_600')
    verts = list(verts or generate_600cell_vertices())
    cells = list(cells or generate_600cell_cells(verts))
    out = []
    for tet in cells:
        cx = sum(verts[i][0] for i in tet) / 4.0
        cy = sum(verts[i][1] for i in tet) / 4.0
        cz = sum(verts[i][2] for i in tet) / 4.0
        cw = sum(verts[i][3] for i in tet) / 4.0
        out.append(_unit4((cx, cy, cz, cw)))
    return tuple(out)


def _weighted_norm_sq(vector: Sequence[float]) -> float:
    return sum((PHI ** (-(i + 1))) * value * value for i, value in enumerate(vector))


def lift_fold_11d(normal4: Sequence[float]) -> Tuple[Tuple[float, ...], float]:
    require_reference('chronus.h4_600')
    lifted = tuple(float(normal4[index % 4]) * (PHI ** (-(index // 4))) for index in range(DIM))
    scale = 1.0 / math.sqrt(1.0 + _weighted_norm_sq(lifted))
    folded = tuple(value * scale for value in lifted)
    return folded, _weighted_norm_sq(folded)


def build_600_frame():
    require_reference('chronus.h4_600')
    verts = generate_600cell_vertices()
    cells = generate_600cell_cells(verts)
    normals = cell_normals(verts, cells)
    frames = [lift_fold_11d(n)[0] for n in normals]
    return {
        "vertices": len(verts),
        "cells": len(cells),
        "frames_11d": frames,
        "n_faces": len(frames),
    }
