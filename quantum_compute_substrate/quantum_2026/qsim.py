"""Modern quantum simulation: 4th-order Suzuki-Trotter and qDRIFT.

Suzuki 4th-order formula:
    S_4(dt) = S_2(s * dt)^2 . S_2((1 - 4s) * dt) . S_2(s * dt)^2
    s = 1 / (4 - 4^{1/3})
Achieves O(dt^5) local error per step, vs O(dt^3) for standard second-order.
"""
from __future__ import annotations
import numpy as np
from typing import Sequence, List
from ._linalg import expm


def _second_order(dt: float, H1: np.ndarray, H2: np.ndarray) -> np.ndarray:
    a = expm(-1j * dt / 2.0 * H1)
    b = expm(-1j * dt * H2)
    return a @ b @ a


def suzuki_trotter_4th_order(dt: float, H1: np.ndarray, H2: np.ndarray) -> np.ndarray:
    """Fourth-order Suzuki decomposition of exp(-i (H1 + H2) dt)."""
    s = 1.0 / (4.0 - 4.0 ** (1.0 / 3.0))
    U = _second_order(s * dt, H1, H2)
    U = U @ _second_order(s * dt, H1, H2)
    U = U @ _second_order((1.0 - 4.0 * s) * dt, H1, H2)
    U = U @ _second_order(s * dt, H1, H2)
    U = U @ _second_order(s * dt, H1, H2)
    return U


def qdrift_channel(terms: Sequence[np.ndarray], weights: Sequence[float],
                   time: float, samples: int, seed: int = 0) -> np.ndarray:
    """qDRIFT (Campbell 2019): random-sample importance from sum-of-terms Hamiltonian.

    U_qDRIFT(t) = product over N samples of exp(-i * h_i * lambda * t / N * sign_i)
    where lambda = sum_i |h_i| and terms are sampled with probability |h_i| / lambda.
    """
    rng = np.random.default_rng(seed)
    weights = np.asarray(weights, dtype=float)
    lam = float(np.sum(np.abs(weights)))
    if lam == 0.0 or samples == 0:
        dim = terms[0].shape[0]
        return np.eye(dim, dtype=complex)
    probs = np.abs(weights) / lam
    signs = np.sign(weights)
    dim = terms[0].shape[0]
    U = np.eye(dim, dtype=complex)
    tau = lam * time / samples
    for _ in range(samples):
        i = int(rng.choice(len(terms), p=probs))
        U = expm(-1j * signs[i] * tau * terms[i]) @ U
    return U


class ModernQSim:
    def __init__(self, num_qubits: int, hamiltonian: np.ndarray) -> None:
        self.num_qubits = num_qubits
        self.hamiltonian = np.asarray(hamiltonian, dtype=complex)
        # Split H = H1 + H2 (block-diagonal halves for demo purposes).
        d = self.hamiltonian.shape[0]
        half = d // 2
        self.H1 = np.zeros_like(self.hamiltonian)
        self.H2 = np.zeros_like(self.hamiltonian)
        self.H1[:half, :half] = self.hamiltonian[:half, :half]
        self.H2[half:, half:] = self.hamiltonian[half:, half:]
        self.H1[half:, half:] = 0
        self.H2[:half, :half] = 0
        # Off-diagonals split evenly
        off = self.hamiltonian - (self.H1 + self.H2)
        self.H1 = self.H1 + 0.5 * off
        self.H2 = self.H2 + 0.5 * off

    def evolve(self, state: np.ndarray, time: float, steps: int = 10,
               order: int = 4) -> np.ndarray:
        dt = time / max(1, steps)
        psi = np.asarray(state, dtype=complex)
        for _ in range(steps):
            if order == 4:
                U = suzuki_trotter_4th_order(dt, self.H1, self.H2)
            elif order == 2:
                U = _second_order(dt, self.H1, self.H2)
            else:
                U = expm(-1j * dt * self.hamiltonian)
            psi = U @ psi
        return psi

    def adaptive_time_stepping(self, initial_state: np.ndarray, target_time: float,
                               error_threshold: float = 1e-6) -> dict:
        state = np.asarray(initial_state, dtype=complex)
        t = 0.0
        dt = min(0.1, target_time)
        steps: List[float] = []
        while t < target_time - 1e-12:
            dt = min(dt, target_time - t)
            U1 = suzuki_trotter_4th_order(dt, self.H1, self.H2)
            U2 = _second_order(dt, self.H1, self.H2)
            state_next = U1 @ state
            err = float(np.linalg.norm(state_next - U2 @ state))
            if err > error_threshold * 10 and dt > 1e-6:
                dt *= 0.5
                continue
            state = state_next
            t += dt
            steps.append(dt)
            if err < error_threshold and dt < 0.5:
                dt *= 1.5
        return {"final_state": state, "time_steps": steps, "total_time": t}
