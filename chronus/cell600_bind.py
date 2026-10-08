"""Bind the H4 600-cell frame to a Chronus SKU, pathfinder and nonce partition.
NON-PRODUCTION FP64 REFERENCE.

Retained for tests, research lineage, and FP64 consumers only. It is NOT on
the canonical production route: production geometry, planning and execution
run through chronus/exact_geometry.py + chronus/mla1517/mining/resident_search.py, which computes in exact Q(phi) rational arithmetic.
Nothing here produces certificates, evidence, or mining decisions.
"""

from __future__ import annotations

from typing import Any, Dict

from Intelligence.search_crystal import partition_interval

from .h4_600 import build_600_frame
from .h4_coverage import coverage_certificate
from .h4_group import symmetry_report


def bind_600(sku=None, nonce_start: int = 0, nonce_size: int = 1_000_000) -> Dict[str, Any]:
    frame = build_600_frame()
    n = max(1, int(frame["n_faces"]))
    parts = partition_interval(nonce_start, nonce_size, n)
    ticket = None
    backend = "cpu"
    if sku is not None:
        ticket = sku.ingest("h4-600", n, payload="600cell")
        backend = ticket.backend
        if getattr(sku.ctx, "gpu_active", False) and sku.ctx.punch_host is not None:
            import numpy as np

            vecs = np.array(frame["frames_11d"], dtype=np.float32)
            sku.ctx.punch_host.run_punch_batch(0x15, n=len(vecs), in_float=vecs.reshape(-1))
            backend = sku.ctx.projection_backend
    cert = coverage_certificate(nonce_start, nonce_size)
    return {
        "vertices": frame["vertices"],
        "cells": frame["cells"],
        "n_faces": n,
        "shards": len(parts),
        "backend": backend,
        "ticket": None if ticket is None else ticket.as_dict(),
        "coverage": sum(p.size for p in parts) == nonce_size,
        "certificate": cert,
        "symmetry": symmetry_report(
            (1.0, 0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0, 0.0),
        ),
    }
