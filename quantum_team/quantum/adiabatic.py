"""Allocation in the exact one-hot subspace (C^A)^{tensor T}.

Validity is enforced STRUCTURALLY by the basis: an invalid assignment
is not a penalized state, it is not a state. Dimension is A^T, not
2^{T·A} — for T=4, A=6 that is 1,296 amplitudes instead of 16,777,216.

Problem Hamiltonian (diagonal in the assignment basis):
  E(b) = sum_t cost[t, agent_t(b)]
       + conflict_pen · sum_{(t1,t2) coupled} [agent_t1 == agent_t2]
       + load_pen · sum_a max(0, n_a - load_limit)^2

SEMANTICS: a coupled pair (t1, t2) is two tasks that must NOT share
an agent (e.g. both rewrite the same module and would serialize one
agent). Co-location is the penalized event.

Driver: per-register complete-graph mixer K_A = |s_A><s_A| - I_A,
ground state = uniform, and because exp(-i·ang·K_A) factors in closed
form, the driver step is EXACT (no Trotter error within the step):
  exp(-i·ang·K_A) psi = psi + (e^{i·ang} - 1)·mean_t(psi)
(the K_A eigendirection |s_A> has eigenvalue 0, so there is no global
prefactor). Different registers commute, so the product over t is exact.

Time stepping: 2nd-order Strang splitting
  e^{-i H_p dt/2} e^{-i H_d dt} e^{-i H_p dt/2}
with error O(dt^3) per step. The linear schedule s: 0 -> 1 is the
adiabatic theorem's own interpolation; step count is bounded by the
theorem via ||H|| dt << 1 and the spectral gap, and is certified
against brute force in the tests.

Honest scaling: A^T amplitudes. T=8, A=6 -> 1,679,616, comfortable.
Beyond ~A^T = 10^7, hand the diagonal to an annealer/tensor-network
backend behind the same tool interface.
"""

from __future__ import annotations

import numpy as np


def problem_diagonal(T: int, A: int, cost: np.ndarray,
                     coupled: list,
                     load_limit: int,
                     conflict_pen: float = 8.0,
                     load_pen: float = 6.0) -> np.ndarray:
    """Vectorized diagonal of H_problem over all A^T valid basis states.
    Basis index b decodes task-major: agent of task t is
    (b // A^(T-1-t)) % A."""
    N = A ** T
    powers = A ** np.arange(T - 1, -1, -1)
    states = (np.arange(N)[:, None] // powers[None, :]) % A      # (N, T)

    diag = cost[np.arange(T)[None, :], states].sum(axis=1).astype(float)

    for t1, t2 in coupled:                                        # co-location penalized
        diag += conflict_pen * (states[:, t1] == states[:, t2])

    counts = np.stack([(states == a).sum(axis=1) for a in range(A)], axis=1)
    over = np.maximum(0, counts - load_limit).astype(float)
    diag += load_pen * (over ** 2).sum(axis=1)                    # sum over agents a
    return diag


def evolve(diag_p: np.ndarray, T: int, A: int,
           total_time: float, steps: int) -> np.ndarray:
    """Exact Schrödinger evolution under H(s), Strang-split."""
    N = A ** T
    dt = total_time / steps
    psi = np.full(N, 1.0 / np.sqrt(N), dtype=complex)   # ground state of H_driver

    for k in range(steps):
        s = (k + 0.5) / steps
        half = np.exp(-0.5j * s * diag_p * dt)          # exact: H_p diagonal
        psi = psi * half
        ang = (1.0 - s) * dt                            # exact: closed-form mixer
        coeff = np.exp(1j * ang) - 1.0
        tensor = psi.reshape((A,) * T)
        for t in range(T):                              # registers commute
            tensor = tensor + coeff * tensor.mean(axis=t, keepdims=True)
        psi = tensor.reshape(N) * half                  # second half-step

    return psi / np.linalg.norm(psi)


def encode(assignment: dict, T: int, A: int) -> int:
    b = 0
    for t in range(T):
        b = b * A + assignment[t]
    return b


def decode_allocation(probabilities: np.ndarray, T: int, A: int) -> dict:
    """Per-task marginal Born mass, argmax over agents."""
    tensor = probabilities.reshape((A,) * T)
    out = {}
    for t in range(T):
        axes = tuple(i for i in range(T) if i != t)
        out[t] = int(np.argmax(tensor.sum(axis=axes)))
    return out


def brute_force_optimum(T: int, A: int, cost: np.ndarray,
                        coupled: list, load_limit: int,
                        conflict_pen: float = 8.0,
                        load_pen: float = 6.0):
    """Ground truth = argmin of the SAME diagonal the Hamiltonian uses."""
    diag = problem_diagonal(T, A, cost, coupled, load_limit,
                            conflict_pen, load_pen)
    b = int(np.argmin(diag))
    powers = A ** np.arange(T - 1, -1, -1)
    return float(diag[b]), {t: int((b // powers[t]) % A) for t in range(T)}
