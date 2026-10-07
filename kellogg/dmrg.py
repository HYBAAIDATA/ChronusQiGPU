"""Two-site DMRG on MPO Hamiltonians — float plane.

Variational ground-state search on the MPS manifold: sweep two-site blocks,
solve each local eigenproblem by Lanczos with full reorthogonalization,
split by SVD and keep at most ``chi_max`` singular values. This is the
float64 plane: SVD truncation and eigen-solves leave every exact field, so
energies are measured numbers with a reported truncation weight, and
convergence is checked against dense diagonalization where that fits.

Chemistry: DMRG accepts any MPO, so a molecular Hamiltonian runs once its
one- and two-electron integrals are Jordan-Wigner mapped into an MPO. Kellogg
ships no integral source; active spaces of FeMoco size need bond dimensions
in the thousands and give variational upper bounds, not exact energies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

import numpy as np

from .tensor_network import MatrixProductOperator, TensorNetworkError


@dataclass(frozen=True)
class DMRGResult:
    energy: float
    energies: tuple
    bonds: tuple
    max_truncation_weight: float
    sweeps: int
    converged: bool
    plane: str = "float64"


def _lanczos(matvec, guess: np.ndarray, iterations: int = 60, tol: float = 1e-13):
    v = guess / np.linalg.norm(guess)
    basis = [v]
    alphas: List[float] = []
    betas: List[float] = []
    w = matvec(v)
    for it in range(iterations):
        alpha = float(np.vdot(basis[-1], w).real)
        alphas.append(alpha)
        w = w - alpha * basis[-1] - (betas[-1] * basis[-2] if betas else 0)
        for b in basis:
            w = w - np.vdot(b, w) * b
        beta = float(np.linalg.norm(w))
        if beta < tol or it == iterations - 1 or len(basis) >= guess.size:
            break
        betas.append(beta)
        basis.append(w / beta)
        w = matvec(basis[-1])
    k = len(alphas)
    t = np.diag(alphas) + np.diag(betas[: k - 1], 1) + np.diag(betas[: k - 1], -1)
    vals, vecs = np.linalg.eigh(t)
    ground = sum(vecs[i, 0] * basis[i] for i in range(k))
    return float(vals[0]), ground / np.linalg.norm(ground)


def dmrg(
    mpo: MatrixProductOperator,
    chi_max: int = 32,
    sweeps: int = 8,
    tol: float = 1e-10,
    seed: int = 0,
) -> DMRGResult:
    w = [np.asarray(c, dtype=complex) for c in mpo.cores]
    n = len(w)
    d = w[0].shape[1]
    if n < 2:
        raise TensorNetworkError("two-site DMRG needs at least two sites")
    rng = np.random.default_rng(seed)
    mps = []
    left = 1
    for i in range(n):
        right = 1 if i == n - 1 else min(chi_max, d ** (i + 1), d ** (n - i - 1))
        mps.append(rng.standard_normal((left, d, right)) + 0j)
        left = right
    # right-canonicalize
    for i in range(n - 1, 0, -1):
        l_, d_, r_ = mps[i].shape
        q, r = np.linalg.qr(mps[i].reshape(l_, d_ * r_).T)
        k = q.shape[1]
        mps[i] = q.T.reshape(k, d_, r_)
        mps[i - 1] = np.tensordot(mps[i - 1], r.T, axes=([2], [0]))
    mps[0] /= np.linalg.norm(mps[0])

    def left_env(env, a, wi):
        t = np.tensordot(env, a, axes=([2], [0]))
        t = np.tensordot(t, wi, axes=([1, 2], [0, 2]))
        return np.tensordot(a.conj(), t, axes=([0, 1], [0, 2])).transpose(0, 2, 1)

    def right_env(env, a, wi):
        t = np.tensordot(a, env, axes=([2], [2]))
        t = np.tensordot(wi, t, axes=([2, 3], [1, 3]))
        return np.tensordot(a.conj(), t, axes=([1, 2], [1, 3]))

    lenv = [None] * (n + 1)
    renv = [None] * (n + 1)
    lenv[0] = np.ones((1, 1, 1), dtype=complex)
    renv[n] = np.ones((1, 1, 1), dtype=complex)
    for i in range(n - 1, -1, -1):
        renv[i] = right_env(renv[i + 1], mps[i], w[i])

    energies: List[float] = []
    max_trunc = 0.0
    energy = 0.0

    def optimize(i: int, direction: str) -> float:
        nonlocal max_trunc
        le, re = lenv[i], renv[i + 2]
        theta = np.tensordot(mps[i], mps[i + 1], axes=([2], [0]))
        shape = theta.shape

        def matvec(x: np.ndarray) -> np.ndarray:
            t = x.reshape(shape)
            t = np.tensordot(le, t, axes=([2], [0]))
            t = np.tensordot(t, w[i], axes=([1, 2], [0, 2]))
            t = np.tensordot(t, w[i + 1], axes=([1, 4], [2, 0]))
            t = np.tensordot(t, re, axes=([1, 4], [2, 1]))
            return t.reshape(-1)

        e, vec = _lanczos(matvec, theta.reshape(-1))
        theta = vec.reshape(shape[0] * shape[1], shape[2] * shape[3])
        u, s, vh = np.linalg.svd(theta, full_matrices=False)
        keep = min(chi_max, int(np.count_nonzero(s > 1e-14 * s[0])) or 1)
        max_trunc = max(max_trunc, float(np.sum(s[keep:] ** 2)))
        u, s, vh = u[:, :keep], s[:keep] / np.linalg.norm(s[:keep]), vh[:keep]
        if direction == "right":
            mps[i] = u.reshape(shape[0], shape[1], keep)
            mps[i + 1] = (np.diag(s) @ vh).reshape(keep, shape[2], shape[3])
            lenv[i + 1] = left_env(lenv[i], mps[i], w[i])
        else:
            mps[i] = (u @ np.diag(s)).reshape(shape[0], shape[1], keep)
            mps[i + 1] = vh.reshape(keep, shape[2], shape[3])
            renv[i + 1] = right_env(renv[i + 2], mps[i + 1], w[i + 1])
        return e

    converged = False
    done = 0
    for sweep in range(sweeps):
        for i in range(n - 1):
            energy = optimize(i, "right")
        for i in range(n - 2, -1, -1):
            energy = optimize(i, "left")
        done = sweep + 1
        if energies and abs(energies[-1] - energy) < tol:
            energies.append(energy)
            converged = True
            break
        energies.append(energy)
    bonds = tuple([1] + [m.shape[2] for m in mps])
    return DMRGResult(
        energy=float(energy),
        energies=tuple(energies),
        bonds=bonds,
        max_truncation_weight=max_trunc,
        sweeps=done,
        converged=converged,
    )


def dense_ground_energy(mpo: MatrixProductOperator) -> float:
    """Reference ground energy by dense diagonalization (small systems only)."""
    matrix = mpo.to_full_matrix()
    return float(np.linalg.eigvalsh(0.5 * (matrix + matrix.conj().T))[0])


def chain_mpo(kind: str, n: int, **params: float) -> MatrixProductOperator:
    from .tensor_network import HeisenbergHamiltonianMPO, IsingHamiltonianMPO

    if kind == "ising":
        return IsingHamiltonianMPO(n, **params)
    if kind == "heisenberg":
        return HeisenbergHamiltonianMPO(n, **params)
    raise TensorNetworkError(f"unknown chain {kind!r}")


__all__: Sequence[str] = ["DMRGResult", "chain_mpo", "dense_ground_energy", "dmrg"]
