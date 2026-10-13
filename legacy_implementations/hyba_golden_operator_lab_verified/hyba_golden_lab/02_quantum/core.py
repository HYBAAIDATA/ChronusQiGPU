"""
02_quantum — exact quantum operators. No sampling. No hardware.
"""
from __future__ import annotations

import math
from typing import Dict, Sequence

import numpy as np


def _normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v if n <= 0 else v / n


def _herm(H: np.ndarray) -> np.ndarray:
    H = np.asarray(H, dtype=complex)
    return 0.5 * (H + H.conj().T)


def _expm_h(H: np.ndarray, t: complex) -> np.ndarray:
    ev, U = np.linalg.eigh(_herm(H))
    return (U * np.exp(t * ev)) @ U.conj().T


def superposition(n: int) -> np.ndarray:
    return np.ones(n, dtype=complex) / math.sqrt(n)


def born(psi: np.ndarray) -> np.ndarray:
    p = np.abs(_normalize(np.asarray(psi, dtype=complex))) ** 2
    return p / p.sum()


def measure_exact(psi: np.ndarray) -> Dict:
    p = born(psi)
    idx = int(np.argmax(p))
    return {"index": idx, "probability": float(p[idx]), "distribution": p, "exact": True}


def entanglement_spectrum(psi: np.ndarray, cut: int) -> Dict:
    psi = _normalize(np.asarray(psi, dtype=complex).reshape(-1))
    n = int(round(math.log2(psi.size)))
    if 2 ** n != psi.size:
        raise ValueError("state dimension must be a power of 2")
    if not (0 < cut < n):
        raise ValueError("cut must split the register")
    left, right = 2 ** cut, 2 ** (n - cut)
    M = psi.reshape(left, right)
    s = np.linalg.svd(M, compute_uv=False)
    lam = s ** 2
    lam = lam[lam > 1e-15]
    ent = float(-np.sum(lam * np.log(lam))) if lam.size else 0.0
    return {"schmidt": s, "entropy": ent, "purity": float(np.sum((s ** 2) ** 2))}


def interfere(psi: np.ndarray, phases: np.ndarray) -> np.ndarray:
    psi = _normalize(np.asarray(psi, dtype=complex).reshape(-1))
    ph = np.asarray(phases, dtype=float).reshape(-1)
    if ph.size != psi.size:
        raise ValueError("phase vector length mismatch")
    return _normalize(psi * np.exp(1j * ph))


def grover(n_qubits: int, marked: Sequence[int], iterations: int = None) -> Dict:
    N = 2 ** n_qubits
    marked = list(marked)
    if iterations is None:
        theta = math.asin(math.sqrt(len(marked) / N))
        iterations = max(1, int(round(math.pi / (4.0 * theta) - 0.5))) if theta > 1e-15 else 0
    psi = superposition(N)
    O = np.eye(N, dtype=complex)
    for i in marked:
        O[i, i] = -1.0
    s = superposition(N)
    D = 2.0 * np.outer(s, s.conj()) - np.eye(N, dtype=complex)
    for _ in range(iterations):
        psi = _normalize(D @ (O @ psi))
    p = born(psi)
    found = int(np.argmax(p))
    return {
        "state": psi,
        "distribution": p,
        "iterations": iterations,
        "found": found,
        "success": found in marked,
        "marked_probability": float(sum(p[i] for i in marked)),
        "exact": True,
    }


def qft_matrix(n_qubits: int) -> np.ndarray:
    n = 2 ** n_qubits
    j = np.arange(n).reshape(-1, 1)
    k = np.arange(n).reshape(1, -1)
    return np.exp(2j * np.pi * j * k / n) / math.sqrt(n)


def qft(psi: np.ndarray) -> np.ndarray:
    psi = _normalize(np.asarray(psi, dtype=complex).reshape(-1))
    nq = int(round(math.log2(psi.size)))
    if 2 ** nq != psi.size:
        raise ValueError("QFT requires power-of-two dimension")
    return qft_matrix(nq) @ psi


def pauli_z(n: int, q: int) -> np.ndarray:
    I, Z = np.eye(2, dtype=complex), np.array([[1, 0], [0, -1]], dtype=complex)
    parts = [Z if i == q else I for i in range(n)]
    out = parts[0]
    for p in parts[1:]:
        out = np.kron(out, p)
    return out


def pauli_x(n: int, q: int) -> np.ndarray:
    I, X = np.eye(2, dtype=complex), np.array([[0, 1], [1, 0]], dtype=complex)
    parts = [X if i == q else I for i in range(n)]
    out = parts[0]
    for p in parts[1:]:
        out = np.kron(out, p)
    return out


def qaoa_ising(n: int, J: np.ndarray, beta: np.ndarray, gamma: np.ndarray) -> Dict:
    dim = 2 ** n
    Hc = np.zeros((dim, dim), dtype=complex)
    for i in range(n):
        for j in range(i + 1, n):
            if abs(J[i, j]) > 0:
                Hc += float(J[i, j]) * (pauli_z(n, i) @ pauli_z(n, j))
    Hb = np.zeros((dim, dim), dtype=complex)
    for q in range(n):
        Hb -= pauli_x(n, q)
    psi = superposition(dim)
    p = min(len(beta), len(gamma))
    for k in range(p):
        psi = _expm_h(Hc, -1j * float(gamma[k])) @ psi
        psi = _expm_h(Hb, -1j * float(beta[k])) @ psi
    psi = _normalize(psi)
    energy = float(np.real(np.vdot(psi, Hc @ psi)))
    ev = np.linalg.eigvalsh(_herm(Hc))
    return {
        "state": psi,
        "distribution": born(psi),
        "energy": energy,
        "exact_min": float(ev[0]),
        "gap": energy - float(ev[0]),
        "exact": True,
    }
