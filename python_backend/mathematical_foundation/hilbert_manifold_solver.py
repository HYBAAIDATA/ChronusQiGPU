"""M_32 manifold geometry -- the search surface the warriors solve on.

Exact mathematical geometry: 32 face normals (12 dodecahedral + 20
icosahedral), Laplacian, geodesic distances, curvature action table, and the
phi-resonance scorer / Voronoi assignment. This is the manifold, not a mock.
"""

from __future__ import annotations

import math
from typing import List, Tuple

import numpy as np

PHI: float = (1.0 + math.sqrt(5.0)) / 2.0
INV_PHI: float = PHI - 1.0
SPECTRAL_GAP_THRESHOLD: float = 3.0 - PHI
LUCAS_15: int = 1364
PHI_15: float = PHI**15

ALPHA: float = PHI**-2
BETA: float = PHI**-3
GAMMA: float = PHI**-4
NORM_WEIGHTS: float = ALPHA + BETA + GAMMA


def _normalize_vec(v):
    mag = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if mag < 1e-12:
        return (1.0, 0.0, 0.0)
    return (v[0] / mag, v[1] / mag, v[2] / mag)


def build_m32_normals() -> List[Tuple[float, float, float]]:
    normals = []
    p = PHI
    for s1 in [1.0, -1.0]:
        for s2 in [1.0, -1.0]:
            normals.append(_normalize_vec((0.0, s1 / p, s2 * p)))
            normals.append(_normalize_vec((s2 * p, 0.0, s1 / p)))
            normals.append(_normalize_vec((s1 / p, s2 * p, 0.0)))
    for sx in [1.0, -1.0]:
        for sy in [1.0, -1.0]:
            for sz in [1.0, -1.0]:
                normals.append(_normalize_vec((sx, sy, sz)))
    for s1 in [1.0, -1.0]:
        for s2 in [1.0, -1.0]:
            normals.append(_normalize_vec((0.0, s1, s2 * p)))
            normals.append(_normalize_vec((s2 * p, 0.0, s1)))
            normals.append(_normalize_vec((s1, s2 * p, 0.0)))
    return normals[:32]


M32_NORMALS_LIST = build_m32_normals()
M32_NORMALS_NP = np.array(M32_NORMALS_LIST, dtype=np.float64)


def build_adjacency(dim=32, threshold=0.75):
    A = np.zeros((dim, dim), dtype=np.float64)
    for i in range(dim):
        for offset in [1, 2, 5, 8]:
            j = (i + offset) % dim
            A[i, j] = 1.0
            A[j, i] = 1.0
    gram = M32_NORMALS_NP @ M32_NORMALS_NP.T
    for i in range(dim):
        for j in range(dim):
            if i != j and gram[i, j] > threshold:
                A[i, j] = 1.0
                A[j, i] = 1.0
    return A


class ManifoldPrecomputationEngine:
    _instance = None

    def __init__(self):
        self.dim = 32
        self.normals = M32_NORMALS_NP
        self.adjacency_matrix = build_adjacency(self.dim)
        self.gram_matrix = self.normals @ self.normals.T
        self.degrees = np.sum(self.adjacency_matrix, axis=1)
        self.laplacian = np.diag(self.degrees) - self.adjacency_matrix
        self.curvature_scale = (2.0 * math.pi / PHI) / 255.0
        self.curvature_table = self._build_curvature_table()
        self.geodesic_distance = np.arccos(np.clip(self.gram_matrix, -1.0, 1.0))

    def _build_curvature_table(self):
        table = np.zeros((256, 256), dtype=np.float64)
        for i in range(256):
            ai = i * self.curvature_scale
            for j in range(256):
                aj = j * self.curvature_scale
                table[i, j] = (ai - aj) ** 2 + (ai * aj) ** 2
        return table

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def compute_curvature_action_score(self, nonce):
        b0 = (nonce >> 0) & 0xFF
        b1 = (nonce >> 8) & 0xFF
        b2 = (nonce >> 16) & 0xFF
        b3 = (nonce >> 24) & 0xFF
        return float(
            self.curvature_table[b0, b1]
            + self.curvature_table[b0, b2]
            + self.curvature_table[b0, b3]
            + self.curvature_table[b1, b2]
            + self.curvature_table[b1, b3]
            + self.curvature_table[b2, b3]
        )

    def embed_nonce_to_s2(self, nonce):
        bits = np.array([(nonce >> k) & 1 for k in range(32)], dtype=np.float64)
        vec = bits @ self.normals
        norm = np.linalg.norm(vec)
        if norm < 1e-12:
            return self.normals[0]
        return vec / norm

    def assign_voronoi_face(self, nonce):
        s2_point = self.embed_nonce_to_s2(nonce)
        overlaps = self.normals @ s2_point
        return int(np.argmax(overlaps))

    def compute_phi_resonance(self, nonce):
        if nonce == 0:
            return 0.0
        s2_point = self.embed_nonce_to_s2(nonce)
        overlaps = np.abs(self.normals @ s2_point)
        c1 = float(min(np.max(overlaps) / INV_PHI, 1.0))
        c2 = float(1.0 - 2.0 * abs((nonce * PHI) % 1.0 - 0.5))
        c3 = float(math.exp(-self.compute_curvature_action_score(nonce) / SPECTRAL_GAP_THRESHOLD))
        raw = (ALPHA * c1 + BETA * c2 + GAMMA * c3) / NORM_WEIGHTS
        return float(1.0 / (1.0 + math.exp(-8.0 * (raw - INV_PHI))))
