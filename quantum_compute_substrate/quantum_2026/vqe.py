"""Modern variational quantum eigensolver.

Corrections vs the 2025 draft:
  - QFIM computed from state overlaps (Stokes-Killoran metric), the physically
    correct quantum Fisher information matrix, not 4*g_i*g_j.
  - Parameter-shift rule uses the standard shift = pi/2 with denominator 2
    (Mitarai et al.), not 2*sin(shift) which is numerically identical only
    at shift = pi/2 but was misleadingly written.
  - ZNE with Richardson polynomial AND exponential extrapolators
    (Endo-Benjamin-Li 2018).
"""
from __future__ import annotations
import numpy as np
from typing import Callable, List, Dict, Any, Sequence


def parameter_shift_gradient(f: Callable[[np.ndarray], float],
                             theta: np.ndarray) -> np.ndarray:
    """Standard parameter-shift rule: df/dtheta_i = (f(t+pi/2) - f(t-pi/2)) / 2."""
    grad = np.zeros_like(theta, dtype=float)
    for i in range(len(theta)):
        e = np.zeros_like(theta)
        e[i] = np.pi / 2.0
        grad[i] = (f(theta + e) - f(theta - e)) / 2.0
    return grad


def quantum_fisher_information_matrix(state_fn: Callable[[np.ndarray], np.ndarray],
                                      theta: np.ndarray,
                                      eps: float = 1e-4) -> np.ndarray:
    """QFIM_{ij} = 4 * Re( <d_i psi | d_j psi> - <d_i psi | psi><psi | d_j psi> ).

    This IS the true quantum Fisher information for pure states. Finite-difference
    the state to get partial derivatives; in production, use parameter-shift.
    """
    n = len(theta)
    psi = state_fn(theta)
    dpsi = np.empty((n, psi.shape[0]), dtype=complex)
    for i in range(n):
        e = np.zeros_like(theta)
        e[i] = eps
        dpsi[i] = (state_fn(theta + e) - state_fn(theta - e)) / (2 * eps)
    F = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            overlap = np.vdot(dpsi[i], dpsi[j]) - np.vdot(dpsi[i], psi) * np.vdot(psi, dpsi[j])
            F[i, j] = 4.0 * np.real(overlap)
    # Symmetrize to eliminate numerical asymmetry.
    return 0.5 * (F + F.T)


def adapt_operator_pool(num_qubits: int) -> List[str]:
    """ADAPT-VQE operator pool: single- and paired-excitation generators."""
    pool = []
    for i in range(num_qubits):
        pool.append(f"Y{i}")
    for i in range(num_qubits):
        for j in range(i + 1, num_qubits):
            pool.append(f"Y{i}Y{j}")
            pool.append(f"X{i}Y{j}-Y{i}X{j}")
    return pool


def zero_noise_extrapolate(noise_factors: Sequence[float],
                           results: Sequence[float],
                           method: str = "richardson") -> float:
    """Zero-noise extrapolation. method in {richardson, exponential, linear}."""
    xs = np.asarray(noise_factors, dtype=float)
    ys = np.asarray(results, dtype=float)
    if method == "linear":
        m, b = np.polyfit(xs, ys, 1)
        return float(b)
    if method == "richardson":
        deg = min(len(xs) - 1, 2)
        coeffs = np.polyfit(xs, ys, deg)
        return float(coeffs[-1])
    if method == "exponential":
        # Fit y = a * exp(-b x) + c using log residuals; fall back to linear if invalid.
        try:
            c_guess = float(np.min(ys) - 1e-6)
            log_arg = ys - c_guess
            if np.any(log_arg <= 0):
                return zero_noise_extrapolate(xs, ys, method="linear")
            b_fit, log_a = np.polyfit(xs, np.log(log_arg), 1)
            b_fit = -b_fit
            a_fit = float(np.exp(log_a))
            return float(a_fit + c_guess)
        except Exception:
            return zero_noise_extrapolate(xs, ys, method="linear")
    raise ValueError(f"unknown method: {method}")


class ModernVQE:
    """Substrate-agnostic 2026 VQE."""

    def __init__(self, num_qubits: int, num_layers: int = 3) -> None:
        self.num_qubits = num_qubits
        self.num_layers = num_layers

    def adaptive_ansatz(self, problem_structure: Dict[str, Any]) -> List[str]:
        gates: List[str] = []
        problem_type = problem_structure.get("type", "general")
        symmetries = problem_structure.get("symmetries", [])
        if problem_type == "chemistry":
            gates.extend(["RY", "CNOT"] * self.num_qubits)
        elif problem_type == "optimization":
            gates.extend(["RZ", "RY"] * self.num_qubits)
        else:
            gates.extend(["H"] * self.num_qubits)
        for _ in range(self.num_qubits - 1):
            gates.append("CNOT")
        gates.extend(["RY", "RZ"] * self.num_qubits)
        if "Z2" in symmetries:
            gates.extend(["RZ"] * self.num_qubits)
        if "U1" in symmetries:
            gates.extend(["RY"] * self.num_qubits)
        return gates

    def barren_plateau_learning_rate(self, gradient_history: Sequence[float]) -> float:
        if len(gradient_history) < 10:
            return 0.01
        var = float(np.var(gradient_history[-10:]))
        if var < 1e-6:
            return 0.1
        if var < 1e-4:
            return 0.05
        return 0.01

    def optimize(self, objective: Callable[[np.ndarray], float],
                 state_fn: Callable[[np.ndarray], np.ndarray],
                 theta0: np.ndarray,
                 max_iterations: int = 60,
                 tol: float = 1e-5) -> Dict[str, Any]:
        theta = theta0.astype(float).copy()
        e_hist: List[float] = []
        g_hist: List[float] = []
        for k in range(max_iterations):
            energy = float(objective(theta))
            e_hist.append(energy)
            grad = parameter_shift_gradient(objective, theta)
            g_hist.append(float(np.linalg.norm(grad)))
            if g_hist[-1] < tol:
                break
            # Natural gradient step
            F = quantum_fisher_information_matrix(state_fn, theta)
            F_reg = F + 1e-6 * np.eye(len(theta))
            try:
                nat = np.linalg.solve(F_reg, grad)
            except np.linalg.LinAlgError:
                nat = grad
            lr = self.barren_plateau_learning_rate(g_hist)
            theta = theta - lr * nat
        return {
            "theta": theta,
            "final_energy": e_hist[-1],
            "energy_history": e_hist,
            "gradient_history": g_hist,
            "converged": g_hist[-1] < tol,
        }
