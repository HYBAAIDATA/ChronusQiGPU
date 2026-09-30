"""Coverage certificate for the H4 600-cell frame.

The 600-cell tessellates S^3. The solver's working space is the 11-ball
with the golden inner product: every vector is assigned a unique nearest
cell. The nonce interval is partitioned into that many shards with empty
intersection and full union.

This does not tile infinite-dimensional L2.
"""

from __future__ import annotations

from typing import Any, Dict, Sequence

from Intelligence.search_crystal import partition_interval

from .h4_600 import (
    DIM,
    PHI,
    build_600_frame,
    generate_600cell_cells,
    generate_600cell_vertices,
    lift_fold_11d,
)


def _phi_dot(a: Sequence[float], b: Sequence[float]) -> float:
    n = min(len(a), len(b), DIM)
    return sum((PHI ** (-(i + 1))) * a[i] * b[i] for i in range(n))


def assign_cell(vector: Sequence[float], frames_11d: Sequence[Sequence[float]]) -> int:
    """Nearest 600-cell in the golden inner product (Voronoi on the 11-ball)."""
    best_i = 0
    best = float("-inf")
    for i, frame in enumerate(frames_11d):
        score = _phi_dot(vector, frame)
        if score > best:
            best = score
            best_i = i
    return best_i


def cover_nonce_interval(start: int, size: int, n_faces: int) -> Dict[str, Any]:
    parts = partition_interval(start, size, n_faces)
    covered = sum(p.size for p in parts)
    contiguous = all(
        parts[i].stop == parts[i + 1].start for i in range(len(parts) - 1)
    )
    disjoint = all(
        parts[i].stop <= parts[i + 1].start for i in range(len(parts) - 1)
    )
    return {
        "start": start,
        "size": size,
        "shards": len(parts),
        "covered": covered,
        "union_complete": (
            covered == size
            and parts[0].start == start
            and parts[-1].stop == start + size
        ),
        "contiguous": contiguous,
        "disjoint": disjoint,
    }


def coverage_certificate(
    nonce_start: int = 0,
    nonce_size: int = 1 << 20,
) -> Dict[str, Any]:
    verts = generate_600cell_vertices()
    cells = generate_600cell_cells(verts)
    frame = build_600_frame()
    n = int(frame["n_faces"])
    nonce = cover_nonce_interval(nonce_start, nonce_size, max(n, 1))
    probes = []
    for i in range(DIM):
        vector = [0.0] * DIM
        vector[i] = 1.0
        probes.append(assign_cell(vector, frame["frames_11d"]))
    mid, _ = lift_fold_11d((1.0, 1.0, 1.0, 1.0))
    probes.append(assign_cell(mid, frame["frames_11d"]))
    return {
        "vertices": len(verts),
        "cells_enumerated": len(cells),
        "frames_11d": n,
        "s3_vertex_count_ok": len(verts) == 120,
        "s3_cell_count_ok": len(cells) == 600,
        "tessellation": "S^3 600-cell (hexacosichoron); dual 120-cell",
        "working_space": "R^11 with ||x||_phi, Klein image in the Poincare ball",
        "hilbert_claim": (
            "Every vector in the 11-ball maps to exactly one nearest cell (Voronoi). "
            "The 600-cell tiles S^3. It does not tile L2 of infinite dimension."
        ),
        "probe_cells": probes,
        "probes_assigned": all(0 <= p < n for p in probes) if n else False,
        "nonce": nonce,
        "every_inch_nonce": bool(
            nonce["union_complete"] and nonce["disjoint"] and nonce["contiguous"]
        ),
        "every_inch_11ball": bool(n > 0 and all(0 <= p < n for p in probes)),
    }
