#!/usr/bin/env python3
"""
Exact mathematical objects not already frozen in core/golden_transform.

Rotations via closed-form exp(-i θ σ/2).
Partial trace, completeness, MPS (full SVD = exact).
Quantum Fisher metric, braided category, phase-from-spectrum.
No Gram-Schmidt patching. No Trotter. No sampling.
"""
from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

import numpy as np


def _normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v if n <= 0 else v / n


# ----- Hilbert space -----
class HilbertSpace:
    def __init__(self, dimension: int):
        if dimension < 1:
            raise ValueError("dimension >= 1")
        self.dim = int(dimension)

    def basis(self, i: int) -> np.ndarray:
        v = np.zeros(self.dim, dtype=complex)
        v[int(i)] = 1.0
        return v

    def inner(self, psi: np.ndarray, phi: np.ndarray) -> complex:
        return complex(np.vdot(psi, phi))

    def tensor(self, other: "HilbertSpace") -> "HilbertSpace":
        return HilbertSpace(self.dim * other.dim)


# ----- Exact Pauli rotations: R_n(θ) = cos(θ/2) I - i sin(θ/2) σ -----
def pauli(axis: str) -> np.ndarray:
    axis = axis.lower()
    if axis == "x":
        return np.array([[0, 1], [1, 0]], dtype=complex)
    if axis == "y":
        return np.array([[0, -1j], [1j, 0]], dtype=complex)
    if axis == "z":
        return np.array([[1, 0], [0, -1]], dtype=complex)
    raise ValueError("axis x|y|z")


def rotation(axis: str, theta: float) -> np.ndarray:
    th = float(theta)
    return math.cos(th / 2.0) * np.eye(2, dtype=complex) - 1j * math.sin(th / 2.0) * pauli(axis)


def phase_gate(phi: float) -> np.ndarray:
    return np.array([[1, 0], [0, np.exp(1j * float(phi))]], dtype=complex)


def is_unitary(U: np.ndarray, tol: float = 1e-10) -> bool:
    I = np.eye(U.shape[0], dtype=complex)
    return float(np.linalg.norm(U.conj().T @ U - I)) < tol


# ----- Partial trace (bipartite) -----
def partial_trace(rho: np.ndarray, dim_a: int, dim_b: int, keep: str = "A") -> np.ndarray:
    rho = np.asarray(rho, dtype=complex).reshape(dim_a, dim_b, dim_a, dim_b)
    if keep.upper() == "A":
        return np.trace(rho, axis1=1, axis2=3)
    return np.trace(rho, axis1=0, axis2=2)


def completeness(basis: Sequence[np.ndarray]) -> float:
    dim = basis[0].size
    s = np.zeros((dim, dim), dtype=complex)
    for v in basis:
        a = _normalize(np.asarray(v, dtype=complex)).reshape(-1, 1)
        s += a @ a.conj().T
    return float(np.linalg.norm(s - np.eye(dim)))


# ----- Exact MPS via successive SVD (no truncation ⇒ exact) -----
def mps_from_state(amplitudes: np.ndarray, bond_dim: int = None) -> List[np.ndarray]:
    psi = _normalize(np.asarray(amplitudes, dtype=complex).reshape(-1))
    n = int(round(math.log2(psi.size)))
    if 2 ** n != psi.size:
        raise ValueError("power-of-two dimension required")
    if bond_dim is None:
        bond_dim = psi.size
    tensors: List[np.ndarray] = []
    rest = psi.reshape(2, -1)
    left = 1
    for site in range(n - 1):
        rows = left * 2
        mat = rest.reshape(rows, -1)
        U, S, Vh = np.linalg.svd(mat, full_matrices=False)
        chi = min(bond_dim, S.size)
        U, S, Vh = U[:, :chi], S[:chi], Vh[:chi, :]
        tensors.append(U.reshape(left, 2, chi))
        rest = (S[:, None] * Vh).reshape(chi * 2, -1) if site < n - 2 else (S[:, None] * Vh)
        left = chi
    tensors.append(rest.reshape(left, 2, 1) if rest.ndim == 2 else rest.reshape(left, -1, 1))
    return tensors


def mps_contract(tensors: List[np.ndarray]) -> np.ndarray:
    cur = tensors[0]
    for t in tensors[1:]:
        cur = np.tensordot(cur, t, axes=([-1], [0]))
    return cur.reshape(-1)


# ----- Quantum Fisher metric on a parameterized family |ψ(θ)> -----
def quantum_fisher_metric(states: Sequence[np.ndarray], dtheta: float) -> np.ndarray:
    """
    Finite-difference QFI on a 1-parameter family given as neighboring states.
    For a single parameter: F = 4 (⟨∂ψ|∂ψ⟩ − |⟨ψ|∂ψ⟩|²).
    states[k] ≈ |ψ(θ0 + k dθ)>. Uses first two for the derivative.
    """
    if len(states) < 2:
        raise ValueError("need at least two neighboring states")
    psi = _normalize(states[0])
    dpsi = (_normalize(states[1]) - psi) / float(dtheta)
    return np.array([[4.0 * (np.vdot(dpsi, dpsi).real - abs(np.vdot(psi, dpsi)) ** 2)]], dtype=float)


def qfi_rotation_family(theta: float, axis: str = "y") -> float:
    """Exact QFI of R_axis(θ)|0⟩. Closed form: F_θ = 1 for a single-qubit rotation generator σ/2."""
    psi = rotation(axis, theta) @ np.array([1, 0], dtype=complex)
    # ∂_θ R = (-i σ / 2) R, so |∂ψ⟩ = (-i σ/2)|ψ⟩
    dpsi = (-1j / 2.0) * pauli(axis) @ psi
    return float(4.0 * (np.vdot(dpsi, dpsi).real - abs(np.vdot(psi, dpsi)) ** 2))


# ----- Braided monoidal: permutation braiding + Yang–Baxter -----
def braid_matrix(dim_a: int, dim_b: int) -> np.ndarray:
    n = dim_a * dim_b
    B = np.zeros((n, n), dtype=complex)
    for i in range(dim_a):
        for j in range(dim_b):
            B[j * dim_a + i, i * dim_b + j] = 1.0
    return B


def yang_baxter_error(da: int = 2, db: int = 2, dc: int = 2) -> float:
    bAB, bBC, bAC = braid_matrix(da, db), braid_matrix(db, dc), braid_matrix(da, dc)
    IA, IB, IC = np.eye(da), np.eye(db), np.eye(dc)
    lhs = np.kron(bBC, IA) @ np.kron(IB, bAC) @ np.kron(bAB, IC)
    rhs = np.kron(IC, bAB) @ np.kron(bAC, IB) @ np.kron(IA, bBC)
    return float(np.linalg.norm(lhs - rhs))


# ----- Exact spectrum phase -----
def spectral_phases(U: np.ndarray) -> np.ndarray:
    return np.angle(np.linalg.eigvals(U)) / (2.0 * math.pi)


# ----- Homology ranks already live in TQFT; Chern character from Betti -----
def bloch_geodesic(theta0: float, phi0: float, theta1: float, phi1: float, steps: int = 8) -> Dict:
    """
    Exact geodesic on the Bloch sphere (Fubini–Study for one qubit).
    Great-circle interpolation. Closed form, not a numerical ODE.
    """
    def nvec(th, ph):
        return np.array([
            math.sin(th) * math.cos(ph),
            math.sin(th) * math.sin(ph),
            math.cos(th),
        ], dtype=float)

    a, b = nvec(theta0, phi0), nvec(theta1, phi1)
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    cosom = float(np.clip(np.dot(a, b), -1.0, 1.0))
    omega = math.acos(cosom)
    pts = []
    if omega < 1e-15:
        pts = [a.copy() for _ in range(steps + 1)]
    else:
        for k in range(steps + 1):
            t = k / steps
            pts.append((math.sin((1 - t) * omega) * a + math.sin(t * omega) * b) / math.sin(omega))
    return {"omega": omega, "length": omega, "points": pts, "exact": True}


def bloch_christoffel(theta: float, phi: float) -> Dict[str, float]:
    """
    Exact Christoffel symbols of the Bloch / Fubini–Study metric
    ds² = (1/4)(dθ² + sin²θ dφ²). Only nonzero Γ^φ_{θφ}=Γ^φ_{φθ}=cotθ,
    Γ^θ_{φφ}=−sinθ cosθ.
    """
    th = float(theta)
    s, c = math.sin(th), math.cos(th)
    cot = c / s if abs(s) > 1e-15 else float("inf")
    return {
        "Gamma_phi_theta_phi": cot,
        "Gamma_theta_phi_phi": -s * c,
        "metric_g_theta_theta": 0.25,
        "metric_g_phi_phi": 0.25 * s * s,
    }


class BraidedCategory:
    """Permutation braiding on finite-dimensional objects. Morphisms = matrices."""

    def __init__(self):
        self.objects: Dict[str, int] = {}
        self.morphisms: Dict[str, np.ndarray] = {}

    def add_object(self, name: str, dim: int):
        self.objects[name] = int(dim)

    def add_morphism(self, name: str, matrix: np.ndarray):
        self.morphisms[name] = np.asarray(matrix, dtype=complex)

    def compose(self, g: str, f: str) -> np.ndarray:
        return self.morphisms[g] @ self.morphisms[f]

    def yang_baxter(self, da: int = 2, db: int = 2, dc: int = 2) -> float:
        return yang_baxter_error(da, db, dc)


def coined_walk_operator(adjacency: np.ndarray) -> np.ndarray:
    """U = S (2|s⟩⟨s| − I) on coin⊗position with Grover coin. Exact unitary."""
    A = np.asarray(adjacency, dtype=float)
    n = A.shape[0]
    deg = [int(np.sum(np.abs(A[i]) > 0)) for i in range(n)]
    chi = max(max(deg), 2)
    # Grover coin
    s = np.ones(chi, dtype=complex) / math.sqrt(chi)
    C = 2.0 * np.outer(s, s.conj()) - np.eye(chi, dtype=complex)
    # Shift: permutation along edges, reverse coin
    S = np.zeros((n * chi, n * chi), dtype=complex)
    nbrs = []
    for i in range(n):
        nbrs.append([j for j in range(n) if abs(A[i, j]) > 0])
        while len(nbrs[-1]) < chi:
            nbrs[-1].append(i)
    for i in range(n):
        for d, j in enumerate(nbrs[i][:chi]):
            drev = nbrs[j].index(i) if i in nbrs[j] else d
            S[j * chi + drev, i * chi + d] = 1.0
    # coin on each position
    Coin = np.zeros((n * chi, n * chi), dtype=complex)
    for i in range(n):
        Coin[i * chi:(i + 1) * chi, i * chi:(i + 1) * chi] = C
    return S @ Coin


def functor_compose(U: np.ndarray, V: np.ndarray) -> np.ndarray:
    """F(g ∘ f) = F(g) ∘ F(f) — matrix composition."""
    return np.asarray(U, dtype=complex) @ np.asarray(V, dtype=complex)


def vietoris_rips_betti(points: np.ndarray, radius: float) -> Dict[int, int]:
    """Exact Betti numbers of the VR flag complex via boundary ranks (ℝ coefficients).

    Includes tetrahedra and ∂₃, so H₂ = ker ∂₂ / im ∂₃ is exact — not just ker ∂₂.
    """
    X = np.asarray(points, dtype=float)
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    n = X.shape[0]
    D = np.sqrt(np.maximum(np.sum((X[:, None, :] - X[None, :, :]) ** 2, axis=-1), 0.0))

    edges = [(i, j) for i in range(n) for j in range(i + 1, n) if D[i, j] <= radius]
    eidx = {e: k for k, e in enumerate(edges)}

    def clique(a, b, *rest):
        return all(tuple(sorted(p)) in eidx for p in [(a, b)] + [(min(x, y), max(x, y)) for x in (a, b) for y in rest] + [(min(x, y), max(x, y)) for i, x in enumerate(rest) for y in rest[i + 1:]])

    tris = []
    for a in range(n):
        for b in range(a + 1, n):
            if (a, b) not in eidx:
                continue
            for c in range(b + 1, n):
                if (a, c) in eidx and (b, c) in eidx:
                    tris.append((a, b, c))
    tidx = {t: k for k, t in enumerate(tris)}

    tets = []
    for a in range(n):
        for b in range(a + 1, n):
            if (a, b) not in eidx:
                continue
            for c in range(b + 1, n):
                if (a, c) not in eidx or (b, c) not in eidx:
                    continue
                for d in range(c + 1, n):
                    if ((a, d) in eidx and (b, d) in eidx and (c, d) in eidx):
                        tets.append((a, b, c, d))

    d1 = np.zeros((n, len(edges)))
    for k, (i, j) in enumerate(edges):
        d1[i, k] = -1.0
        d1[j, k] = 1.0
    d2 = np.zeros((len(edges), len(tris)))
    for t, (a, b, c) in enumerate(tris):
        d2[eidx[(a, b)], t] = 1.0
        d2[eidx[(b, c)], t] = 1.0
        d2[eidx[(a, c)], t] = -1.0
    # 4-simplices (5-cliques) so H₃ = ker ∂₃ / im ∂₄ is exact, not just ker ∂₃
    pents = []
    for a in range(n):
        for b in range(a + 1, n):
            if (a, b) not in eidx:
                continue
            for c in range(b + 1, n):
                if (a, c) not in eidx or (b, c) not in eidx:
                    continue
                for d in range(c + 1, n):
                    if not ((a, d) in eidx and (b, d) in eidx and (c, d) in eidx):
                        continue
                    for e in range(d + 1, n):
                        if ((a, e) in eidx and (b, e) in eidx and (c, e) in eidx and (d, e) in eidx):
                            pents.append((a, b, c, d, e))
    tet_idx = {t: k for k, t in enumerate(tets)}

    d3 = np.zeros((len(tris), len(tets)))
    for t, (a, b, c, d) in enumerate(tets):
        d3[tidx[(b, c, d)], t] = 1.0
        d3[tidx[(a, c, d)], t] = -1.0
        d3[tidx[(a, b, d)], t] = 1.0
        d3[tidx[(a, b, c)], t] = -1.0
    d4 = np.zeros((len(tets), len(pents)))
    for t, (a, b, c, d, e) in enumerate(pents):
        d4[tet_idx[(b, c, d, e)], t] = 1.0
        d4[tet_idx[(a, c, d, e)], t] = -1.0
        d4[tet_idx[(a, b, d, e)], t] = 1.0
        d4[tet_idx[(a, b, c, e)], t] = -1.0
        d4[tet_idx[(a, b, c, d)], t] = 1.0

    def rank(A):
        if A.size == 0:
            return 0
        s = np.linalg.svd(A, compute_uv=False)
        return int(np.sum(s > 1e-10))

    r1, r2, r3, r4 = rank(d1), rank(d2), rank(d3), rank(d4)
    b0 = max(n - r1, 0)
    b1 = max((len(edges) - r1) - r2, 0)
    b2 = max((len(tris) - r2) - r3, 0)
    b3 = max((len(tets) - r3) - r4, 0)
    return {0: b0, 1: b1, 2: b2, 3: b3}


def chern_character(betti: Dict[int, int]) -> Dict[str, float]:
    vals = np.array([betti[k] for k in sorted(betti)], dtype=float)
    return {
        "rank": float(vals[0]) if vals.size else 0.0,
        "chern_character": float(np.sum(vals)),
        "todd_phi": float(np.prod([( (1 + math.sqrt(5)) / 2) ** k for k in betti])),
    }
