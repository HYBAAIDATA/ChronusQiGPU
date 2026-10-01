# l_hras/modules/control.py

import numpy as np
from dataclasses import dataclass
def solve_continuous_are(A, B, Q, R):
    n = A.shape[0]
    r_inv = np.linalg.inv(R)
    hamiltonian = np.block([[A, -(B @ r_inv @ B.T)], [-Q, -A.T]])
    values, vectors = np.linalg.eig(hamiltonian)
    stable = np.where(np.real(values) < 0)[0]
    if len(stable) != n:
        raise ValueError("CARE has no unique stable invariant subspace")
    basis = vectors[:, stable]
    upper, lower = basis[:n], basis[n:]
    result = np.real_if_close(lower @ np.linalg.inv(upper)).real
    return (result + result.T) / 2

@dataclass
class ControllerResult:
    riccati: np.ndarray
    gain: np.ndarray
    attestation: str

def real_time_control(A: np.ndarray, B: np.ndarray, Q: np.ndarray, R: np.ndarray) -> ControllerResult:
    """Algebraic + differential Riccati solver."""
    # Algebraic Riccati equation
    P = solve_continuous_are(A, B, Q, R)
    # Kalman gain
    K = np.linalg.inv(R) @ B.T @ P
    return ControllerResult(
        riccati=P,
        gain=K,
        attestation="controller",
    )
