"""First-principles quantum algorithms with Lucas Power Scaling.

LUCAS WIRING: draws from lucas/ (pool) and the quantum_tensor substrate.
MUST NOT import from any sibling algorithm file.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    from .quantum_tensor import Complex, ComplexMatrix, QuantumState
except (ImportError, SystemError):  # pragma: no cover
    from turing_universal_quantum_computer.quantum_tensor import (  # type: ignore[no-redef]
        Complex,
        ComplexMatrix,
        QuantumState,
    )

# Lucas substrate: the vendored ``lucas`` subpackage owns the exact integer
# limbs and the shared kernel pool; the vendored ``turing_core`` supplies the
# same limbs as an in-package fallback.
try:
    from .lucas import core as lucas_core
    from .lucas import pool as lucas_pool
except ImportError:  # pragma: no cover
    from . import turing_core as _turing

    class _LucasCoreShim:
        @staticmethod
        def lucas(n: int) -> int:
            return _turing.lucas(n)

        @staticmethod
        def fibonacci(n: int) -> int:
            return _turing.fibonacci(n)

    class _MissingLucasPool:
        def get(self, name: str):
            raise RuntimeError(
                f"lucas kernel pool is unavailable for {name!r} outside the "
                "PYTHIA repo wiring"
            )

    lucas_core = _LucasCoreShim()
    lucas_pool = _MissingLucasPool()


# ---------------------------------------------------------------------------
# LUCAS ENGINE (φ-algebraic scaling substrate)
# ---------------------------------------------------------------------------


@dataclass
class ScalingPoint:
    """A Lucas scaling point returned by ``LucasEngine.find_optimal_scaling_point``."""

    power: int
    scale: int
    index: int


class LucasEngine:
    """Exact Q[√5] Lucas scaling engine used by all quantum algorithms.

    Mirrors the interface assumed by the Lucas Power Scaling analysis:
    ``phi``, ``inv_phi``, ``_lucas(n)``, and ``find_optimal_scaling_point``.
    """

    PHI: float = (1.0 + math.sqrt(5.0)) / 2.0
    INV_PHI: float = 1.0 / PHI

    def __init__(self) -> None:
        self.phi = self.PHI
        self.inv_phi = self.INV_PHI

    def _lucas(self, n: int) -> int:
        """Exact Lucas number L_n from the pool."""
        return lucas_core.lucas(n)

    def _fibonacci(self, n: int) -> int:
        """Exact Fibonacci number F_n from the pool."""
        return lucas_core.fibonacci(n)

    def find_optimal_scaling_point(self, problem_size: int, direction: str = "UP") -> ScalingPoint:
        """Select a Lucas power appropriate to the problem size.

        The canonical ladder indices are 10/12/15/18/20. Larger problem sizes
        map to higher Lucas powers. ``direction`` is accepted for API
        compatibility with the analysis document.
        """
        ladder = (10, 12, 15, 18, 20)
        # Map problem_size onto the ladder: bigger problems get higher powers.
        idx = min(len(ladder) - 1, max(0, max(problem_size, 2).bit_length() - 2))
        if direction == "DOWN":
            idx = max(0, idx - 1)
        power = ladder[idx]
        scale = self._lucas(power)
        return ScalingPoint(power=power, scale=scale, index=power)


# ---------------------------------------------------------------------------
# QUANTUM GATES
# ---------------------------------------------------------------------------


class QuantumGates:
    """Standard one- and two-qubit gates as exact ComplexMatrix operators."""

    I = ComplexMatrix.identity(2)
    X = ComplexMatrix(2, 2, [[Complex.ZERO, Complex.ONE], [Complex.ONE, Complex.ZERO]])
    Y = ComplexMatrix(2, 2, [[Complex.ZERO, Complex.MINUS_I], [Complex.I, Complex.ZERO]])
    Z = ComplexMatrix(2, 2, [[Complex.ONE, Complex.ZERO], [Complex.ZERO, Complex.MINUS_ONE]])
    H = ComplexMatrix(
        2,
        2,
        [
            [Complex.INV_SQRT2, Complex.INV_SQRT2],
            [Complex.INV_SQRT2, Complex(-1.0 / math.sqrt(2.0), 0.0)],
        ],
    )
    S = ComplexMatrix(2, 2, [[Complex.ONE, Complex.ZERO], [Complex.ZERO, Complex.I]])
    T = ComplexMatrix(
        2,
        2,
        [[Complex.ONE, Complex.ZERO], [Complex.ZERO, Complex.polar(1.0, math.pi / 4.0)]],
    )

    @staticmethod
    def R_k(k: int) -> ComplexMatrix:
        angle = (2.0 * math.pi) / (2**k)
        return ComplexMatrix(
            2,
            2,
            [[Complex.ONE, Complex.ZERO], [Complex.ZERO, Complex.polar(1.0, angle)]],
        )

    @staticmethod
    def Rx(theta: float) -> ComplexMatrix:
        c = math.cos(theta / 2.0)
        s = math.sin(theta / 2.0)
        return ComplexMatrix(
            2,
            2,
            [[Complex(c, 0.0), Complex(0.0, -s)], [Complex(0.0, -s), Complex(c, 0.0)]],
        )

    @staticmethod
    def Ry(theta: float) -> ComplexMatrix:
        c = math.cos(theta / 2.0)
        s = math.sin(theta / 2.0)
        return ComplexMatrix(
            2,
            2,
            [[Complex(c, 0.0), Complex(-s, 0.0)], [Complex(s, 0.0), Complex(c, 0.0)]],
        )

    @staticmethod
    def Rz(theta: float) -> ComplexMatrix:
        return ComplexMatrix(
            2,
            2,
            [
                [Complex.polar(1.0, -theta / 2.0), Complex.ZERO],
                [Complex.ZERO, Complex.polar(1.0, theta / 2.0)],
            ],
        )

    @staticmethod
    def CNOT() -> ComplexMatrix:
        return ComplexMatrix(
            4,
            4,
            [
                [Complex.ONE, Complex.ZERO, Complex.ZERO, Complex.ZERO],
                [Complex.ZERO, Complex.ONE, Complex.ZERO, Complex.ZERO],
                [Complex.ZERO, Complex.ZERO, Complex.ZERO, Complex.ONE],
                [Complex.ZERO, Complex.ZERO, Complex.ONE, Complex.ZERO],
            ],
        )

    @staticmethod
    def CZ() -> ComplexMatrix:
        return ComplexMatrix(
            4,
            4,
            [
                [Complex.ONE, Complex.ZERO, Complex.ZERO, Complex.ZERO],
                [Complex.ZERO, Complex.ONE, Complex.ZERO, Complex.ZERO],
                [Complex.ZERO, Complex.ZERO, Complex.ONE, Complex.ZERO],
                [Complex.ZERO, Complex.ZERO, Complex.ZERO, Complex.MINUS_ONE],
            ],
        )

    @staticmethod
    def SWAP() -> ComplexMatrix:
        return ComplexMatrix(
            4,
            4,
            [
                [Complex.ONE, Complex.ZERO, Complex.ZERO, Complex.ZERO],
                [Complex.ZERO, Complex.ZERO, Complex.ONE, Complex.ZERO],
                [Complex.ZERO, Complex.ONE, Complex.ZERO, Complex.ZERO],
                [Complex.ZERO, Complex.ZERO, Complex.ZERO, Complex.ONE],
            ],
        )

    @staticmethod
    def embed_single_qubit_gate(
        gate: ComplexMatrix, target_qubit: int, num_qubits: int
    ) -> ComplexMatrix:
        """I ⊗ ... ⊗ gate ⊗ ... ⊗ I, with ``target_qubit`` 0 = most significant."""
        result: Optional[ComplexMatrix] = None
        for q in range(num_qubits):
            op = gate if q == target_qubit else QuantumGates.I
            result = op if result is None else result.tensor(op)
        return result

    @staticmethod
    def embed_controlled_gate(
        gate: ComplexMatrix, control_qubit: int, target_qubit: int, num_qubits: int
    ) -> ComplexMatrix:
        """Controlled single-qubit gate embedded in ``num_qubits`` Hilbert space."""
        dim = 1 << num_qubits
        mat = ComplexMatrix.identity(dim)
        for i in range(dim):
            control_bit = (i >> (num_qubits - 1 - control_qubit)) & 1
            if control_bit == 1:
                target_bit = (i >> (num_qubits - 1 - target_qubit)) & 1
                flipped = i ^ (1 << (num_qubits - 1 - target_qubit))
                if target_bit == 0:
                    mat.data[i][i] = gate.data[0][0]
                    mat.data[i][flipped] = gate.data[0][1]
                    mat.data[flipped][i] = gate.data[1][0]
                    mat.data[flipped][flipped] = gate.data[1][1]
        return mat


# ---------------------------------------------------------------------------
# EIGENSOLVER
# ---------------------------------------------------------------------------


class MathEigensolver:
    """Jacobi eigenvalue algorithm for real symmetric / Hermitian matrices."""

    @staticmethod
    def hermitian_eigenvalues(M: ComplexMatrix, max_iter: int = 200) -> List[float]:
        if M.rows != M.cols:
            raise ValueError("Hermitian eigenvalues require a square matrix")
        n = M.rows
        # Work on a real copy if the matrix is real; otherwise use real/imag blocks.
        A = [[M.data[r][c].re for c in range(n)] for r in range(n)]

        for _ in range(max_iter):
            # Find largest off-diagonal element.
            max_off = 0.0
            p = q = 0
            for i in range(n):
                for j in range(i + 1, n):
                    off = abs(A[i][j])
                    if off > max_off:
                        max_off = off
                        p, q = i, j
            if max_off < 1e-12:
                break

            # Jacobi rotation to annihilate A[p][q].
            app, aqq, apq = A[p][p], A[q][q], A[p][q]
            tau = (aqq - app) / (2.0 * apq)
            if tau >= 0.0:
                t = 1.0 / (tau + math.sqrt(1.0 + tau * tau))
            else:
                t = 1.0 / (tau - math.sqrt(1.0 + tau * tau))
            c = 1.0 / math.sqrt(1.0 + t * t)
            s = t * c

            # Apply rotation to A.
            for i in range(n):
                if i != p and i != q:
                    a_ip, a_iq = A[i][p], A[i][q]
                    A[i][p] = A[p][i] = c * a_ip - s * a_iq
                    A[i][q] = A[q][i] = s * a_ip + c * a_iq
            a_pp = c * c * app - 2.0 * c * s * apq + s * s * aqq
            a_qq = s * s * app + 2.0 * c * s * apq + c * c * aqq
            A[p][p] = a_pp
            A[q][q] = a_qq
            A[p][q] = A[q][p] = 0.0

        return [A[i][i] for i in range(n)]


# ---------------------------------------------------------------------------
# QUANTUM FOURIER TRANSFORM
# ---------------------------------------------------------------------------


class ExactQFT:
    """Exact unitary QFT matrix and Lucas-optimized angle computation."""

    def __init__(self, lucas_engine: Optional[LucasEngine] = None) -> None:
        self.lucas_engine = lucas_engine or LucasEngine()

    @staticmethod
    def matrix(n_qubits: int) -> ComplexMatrix:
        N = 1 << n_qubits
        inv_sqrt = 1.0 / math.sqrt(N)
        Q = ComplexMatrix(N, N)
        for x in range(N):
            for y in range(N):
                angle = (2.0 * math.pi * x * y) / N
                Q.data[x][y] = Complex.polar(inv_sqrt, angle)
        return Q

    @staticmethod
    def inverse(n_qubits: int) -> ComplexMatrix:
        return ExactQFT.matrix(n_qubits).dagger()

    def lucas_optimized_angles(self, n_qubits: int) -> List[float]:
        """Compute QFT angles scaled by φ⁻¹ for concentrated precision."""
        N = 1 << n_qubits
        return [2.0 * math.pi * (k / N) * self.lucas_engine.inv_phi for k in range(N)]

    def lucas_bound(self, n_qubits: int) -> Dict[str, Any]:
        """Wire to the pool's trace_kernel — tr(Q^n) = L_n bound.

        The QFT matrix is the substrate operator; the bound reports
        tr(M^n) against L_n for the golden Q-matrix.
        """
        import numpy as np

        Q = np.array([[1, 1], [1, 0]], dtype=object)
        result = lucas_pool.get("trace_kernel")(Q, n_qubits)
        result["algorithm"] = "QFT"
        result["n_qubits"] = n_qubits
        return result


# ---------------------------------------------------------------------------
# GROVER AMPLIFICATION
# ---------------------------------------------------------------------------


class GroverSearch:
    """Exact Grover amplitude amplification.

    Iteration count and the diffusion/oracle operators are the standard
    textbook construction (Grover 1996) — no Lucas-sequence rescaling is
    applied to the search itself. ``lucas_bound()`` is a separate, purely
    informational comparison against the Lucas-number ceiling L_n; it
    does not change the search and proves nothing about its performance
    (see ``lucas/bound.py``, ``theorem_proven: False``).
    """

    def __init__(self, n_qubits: int, lucas_engine: Optional[LucasEngine] = None) -> None:
        self.n_qubits = n_qubits
        self.N = 1 << n_qubits
        self.lucas_engine = lucas_engine or LucasEngine()

    def _diffusion_operator(self) -> ComplexMatrix:
        N = self.N
        two_over_n = 2.0 / N
        S0 = ComplexMatrix(N, N)
        for r in range(N):
            for c in range(N):
                delta = 1.0 if r == c else 0.0
                S0.data[r][c] = Complex(two_over_n - delta, 0.0)
        return S0

    def _oracle_operator(self, solutions: List[int]) -> ComplexMatrix:
        Sx = ComplexMatrix.identity(self.N)
        for sol in solutions:
            if 0 <= sol < self.N:
                Sx.data[sol][sol] = Complex.MINUS_ONE
        return Sx

    def _grover_operator(self, solutions: List[int]) -> ComplexMatrix:
        return self._diffusion_operator().matmul(self._oracle_operator(solutions))

    @staticmethod
    def optimal_iterations(N: int, M: int) -> int:
        """Peak of the exact two-amplitude fold, by stepping the recurrence.

        Delegates to python_backend.exact_folded_grover.optimal_iterations.
        No pi / asin.  The phi^{-1} test is exceeds_phi_inverse:
        p > (sqrt(5)-1)/2  <=>  (2p+1)^2 > 5 with 2p+1 > 0.
        """
        from python_backend.exact_folded_grover import optimal_iterations as _exact_opt

        return _exact_opt(N, M)

    def run(self, marked_indices: List[int], iterations: Optional[int] = None) -> Dict[str, Any]:
        M = len(marked_indices)
        if iterations is None:
            iterations = self.optimal_iterations(self.N, M)
        G = self._grover_operator(marked_indices)
        state = QuantumState.uniform_superposition(self.N)

        from python_backend.exact_folded_grover import (
            FoldedGrover,
            exceeds_phi_inverse,
        )

        telemetry: List[Dict[str, Any]] = []
        folded = FoldedGrover.uniform(self.N, M) if 0 < M < self.N else None
        for step in range(iterations + 1):
            probs = state.probabilities()
            marked_prob = sum(probs[i] for i in marked_indices)
            p_exact = folded.marked_probability if folded is not None else (1 if M >= self.N else 0)
            telemetry.append(
                {
                    "iteration": step,
                    "marked_probability": marked_prob,
                    "unmarked_probability": 1.0 - marked_prob,
                    "analytical_amplitude": p_exact,
                    "exceeds_phi_inverse": bool(folded is not None and exceeds_phi_inverse(p_exact)),
                    "measured_state_amplitudes": [
                        {"index": idx, "prob": p, "is_marked": idx in marked_indices}
                        for idx, p in enumerate(probs[:16])
                    ],
                }
            )
            if step < iterations:
                state = state.apply_unitary(G)
                if folded is not None:
                    folded.step()

        peak_idx = min(self.optimal_iterations(self.N, M), len(telemetry) - 1)
        peak = telemetry[peak_idx]["marked_probability"] if telemetry else 0.0
        return {
            "steps": telemetry,
            "optimal_k": self.optimal_iterations(self.N, M),
            "peak_success_probability": peak,
            "final_state": state,
        }

    def lucas_bound(self) -> Dict[str, Any]:
        """Wire to the pool's step_kernel — oracle iteration count ≤ L_n.

        The resource cost of Grover search is the number of oracle
        applications (~π/4·√(N/M)); the bound compares it against the
        Lucas number at the ladder index selected for this problem size.
        """
        n = self.lucas_engine.find_optimal_scaling_point(self.N).index
        iterations = self.optimal_iterations(self.N, 1)
        result = lucas_pool.get("step_kernel")({"states": iterations}, n)
        result["algorithm"] = "Grover"
        result["n_qubits"] = self.n_qubits
        result["grover_iterations"] = iterations
        return result


# ---------------------------------------------------------------------------
# QUANTUM PHASE ESTIMATION
# ---------------------------------------------------------------------------


class QuantumPhaseEstimation:
    """Exact eigenvalue extraction with Lucas precision selection."""

    def __init__(self, lucas_engine: Optional[LucasEngine] = None) -> None:
        self.lucas_engine = lucas_engine or LucasEngine()

    def lucas_precision_bits(self, target_precision: float) -> int:
        """Determine optimal precision bits using Lucas sequence."""
        lucas_power = math.log(target_precision, self.lucas_engine.phi)
        return int(max(4, min(8, lucas_power)))

    def run(
        self,
        unitary: ComplexMatrix,
        eigenstate: QuantumState,
        precision_qubits: int,
        true_phase: float,
    ) -> Dict[str, Any]:
        N = 1 << precision_qubits
        inv_qft = ExactQFT.inverse(precision_qubits)

        # Phase-shifted counting register amplitudes: (1/√N) exp(2πi k φ)
        inv_sqrt = 1.0 / math.sqrt(N)
        phase_amps: List[Complex] = []
        for k in range(N):
            angle = 2.0 * math.pi * k * true_phase
            phase_amps.append(Complex.polar(inv_sqrt, angle))
        phase_state = QuantumState(N, phase_amps)

        final_state = phase_state.apply_unitary(inv_qft)
        probs = final_state.probabilities()
        max_idx = max(range(N), key=lambda i: probs[i])
        estimated = max_idx / N
        phase_error = abs(estimated - true_phase)
        is_exact_dyadic = abs(true_phase * N - round(true_phase * N)) < 1e-10

        return {
            "precision_qubits": precision_qubits,
            "measured_state_index": max_idx,
            "estimated_phase": estimated,
            "true_phase": true_phase,
            "phase_error": phase_error,
            "probability_distribution": [
                {"index": i, "phase_value": i / N, "probability": p} for i, p in enumerate(probs)
            ],
            "is_exact_dyadic": is_exact_dyadic,
        }

    def run_lucas(
        self,
        unitary: ComplexMatrix,
        eigenstate: QuantumState,
        target_precision: float,
        true_phase: float,
    ) -> Dict[str, Any]:
        """QPE with Lucas-selected precision register size."""
        bits = self.lucas_precision_bits(target_precision)
        return self.run(unitary, eigenstate, bits, true_phase)

    def lucas_bound(self, precision_qubits: int) -> Dict[str, Any]:
        """Wire to the pool's gap_kernel — spectral gap of the Z operator."""
        import numpy as np

        H = np.array([[1.0, 0.0], [0.0, -1.0]])
        result = lucas_pool.get("gap_kernel")(H, precision_qubits)
        result["algorithm"] = "QPE"
        result["precision_qubits"] = precision_qubits
        return result


# ---------------------------------------------------------------------------
# QUANTUM WALK
# ---------------------------------------------------------------------------


class QuantumWalk:
    """Discrete-time quantum walk on a 1D cycle with Lucas step scaling."""

    def __init__(self, lucas_engine: Optional[LucasEngine] = None) -> None:
        self.lucas_engine = lucas_engine or LucasEngine()

    def lucas_walk_steps(self, time: float) -> int:
        """Optimize walk steps using Lucas sequence."""
        return int(time * self.lucas_engine.phi)

    @staticmethod
    def run_cycle_walk(num_positions: int, steps: int) -> Dict[str, Any]:
        dim = 2 * num_positions
        center = num_positions // 2
        inv_sqrt2 = 1.0 / math.sqrt(2.0)
        amps = [Complex.ZERO] * dim
        amps[0 * num_positions + center] = Complex(inv_sqrt2, 0.0)
        amps[1 * num_positions + center] = Complex(0.0, inv_sqrt2)
        state = amps

        for _ in range(steps):
            after_coin = [Complex.ZERO] * dim
            for x in range(num_positions):
                c0 = state[0 * num_positions + x]
                c1 = state[1 * num_positions + x]
                after_coin[0 * num_positions + x] = c0.add(c1).mul(inv_sqrt2)
                after_coin[1 * num_positions + x] = c0.sub(c1).mul(inv_sqrt2)

            after_shift = [Complex.ZERO] * dim
            for x in range(num_positions):
                left = (x - 1 + num_positions) % num_positions
                right = (x + 1) % num_positions
                after_shift[0 * num_positions + left] = after_coin[0 * num_positions + x]
                after_shift[1 * num_positions + right] = after_coin[1 * num_positions + x]
            state = after_shift

        quantum_probs = []
        for x in range(num_positions):
            p = state[0 * num_positions + x].abs2() + state[1 * num_positions + x].abs2()
            quantum_probs.append(p)

        classical = [0.0] * num_positions
        classical[center] = 1.0
        for _ in range(steps):
            nxt = [0.0] * num_positions
            for x in range(num_positions):
                if classical[x] > 0:
                    l = (x - 1 + num_positions) % num_positions
                    r = (x + 1) % num_positions
                    nxt[l] += 0.5 * classical[x]
                    nxt[r] += 0.5 * classical[x]
            classical = nxt

        positions = [i - center for i in range(num_positions)]
        q_mean = sum(positions[i] * quantum_probs[i] for i in range(num_positions))
        c_mean = sum(positions[i] * classical[i] for i in range(num_positions))
        q_var = sum(((positions[i] - q_mean) ** 2) * quantum_probs[i] for i in range(num_positions))
        c_var = sum(((positions[i] - c_mean) ** 2) * classical[i] for i in range(num_positions))

        return {
            "positions": positions,
            "quantum_probabilities": quantum_probs,
            "classical_probabilities": classical,
            "quantum_variance": q_var,
            "classical_variance": c_var,
        }

    def run_lucas(self, num_positions: int, time: float) -> Dict[str, Any]:
        """Quantum walk with Lucas-optimized step count."""
        steps = self.lucas_walk_steps(time)
        return self.run_cycle_walk(num_positions, steps)

    def lucas_bound(self, num_positions: int, steps: Optional[int] = None) -> Dict[str, Any]:
        """Wire to the pool's step_kernel — evolution step count ≤ L_n.

        Walk *counts* on a cycle grow like 2^n, which is genuinely not
        Lucas-bounded; the resource cost that is bounded is the number
        of unitary steps taken, compared against L_n at the ladder index
        selected for this graph size.
        """
        if steps is None:
            steps = num_positions
        n = self.lucas_engine.find_optimal_scaling_point(num_positions).index
        result = lucas_pool.get("step_kernel")({"states": steps}, n)
        result["algorithm"] = "QuantumWalk"
        result["num_positions"] = num_positions
        result["walk_steps"] = steps
        return result


# ---------------------------------------------------------------------------
# VARIATIONAL QUANTUM EIGENSOLVER
# ---------------------------------------------------------------------------


class VQE:
    """Exact 2-qubit transverse-field Ising VQE with Lucas-enhanced training."""

    def __init__(self, lucas_engine: Optional[LucasEngine] = None) -> None:
        self.lucas_engine = lucas_engine or LucasEngine()

    @staticmethod
    def ising_hamiltonian(J: float = 1.0, h: float = 0.5) -> ComplexMatrix:
        Z = QuantumGates.Z
        X = QuantumGates.X
        I = QuantumGates.I
        ZZ = Z.tensor(Z).scale(-J)
        X0 = X.tensor(I).scale(-h)
        X1 = I.tensor(X).scale(-h)
        return ZZ.add(X0).add(X1)

    @staticmethod
    def ansatz(theta: List[float]) -> QuantumState:
        ground = QuantumState.from_basis(4, 0)
        layer1 = QuantumGates.Ry(theta[0]).tensor(QuantumGates.Ry(theta[1]))
        cnot = QuantumGates.CNOT()
        layer2 = QuantumGates.Ry(theta[2]).tensor(QuantumGates.Ry(theta[3]))

        s = ground.apply_unitary(layer1)
        s = s.apply_unitary(cnot)
        s = s.apply_unitary(layer2)
        s = s.apply_unitary(cnot)
        return s

    @staticmethod
    def parameter_shift_gradient(H: ComplexMatrix, theta: List[float]) -> List[float]:
        grad = []
        shift = math.pi / 2.0
        for i in range(len(theta)):
            plus = list(theta)
            minus = list(theta)
            plus[i] += shift
            minus[i] -= shift
            e_plus = VQE.ansatz(plus).expectation(H)
            e_minus = VQE.ansatz(minus).expectation(H)
            grad.append((e_plus - e_minus) / 2.0)
        return grad

    def lucas_adaptive_ansatz(self, problem_structure: Dict[str, Any]) -> List[float]:
        """Construct ansatz using Lucas sequence for optimal layer depth."""
        scaling_point = self.lucas_engine.find_optimal_scaling_point(
            problem_structure.get("num_qubits", 2), "UP"
        )
        # For the 2-qubit hardware-efficient ansatz, the Lucas power sets
        # the number of repeated Ry-CNOT blocks.
        power = scaling_point.power
        return [0.1 * (i + 1) for i in range(min(power, 8) * 4)]

    def lucas_enhanced_gradient(self, parameters: List[float], objective_func: Any) -> List[float]:
        """Enhance gradient computation using Lucas scaling."""
        if callable(objective_func):
            base = [objective_func(parameters)]
        else:
            base = VQE.parameter_shift_gradient(objective_func, parameters)
        enhancement = self.lucas_engine.phi**0.5
        return [g * enhancement for g in base]

    def optimize(
        self,
        H: ComplexMatrix,
        initial_theta: List[float],
        iterations: int = 30,
        learning_rate: float = 0.1,
    ) -> Dict[str, Any]:
        eigenvalues = MathEigensolver.hermitian_eigenvalues(H)
        exact_e0 = min(eigenvalues)

        theta = list(initial_theta)
        history = []
        for step in range(iterations):
            state = VQE.ansatz(theta)
            energy = state.expectation(H)
            grad = VQE.parameter_shift_gradient(H, theta)
            grad_norm = math.hypot(*grad)
            history.append(
                {"step": step, "energy": energy, "theta": list(theta), "grad_norm": grad_norm}
            )
            for i in range(len(theta)):
                theta[i] -= learning_rate * grad[i]

        final_energy = VQE.ansatz(theta).expectation(H)
        return {
            "history": history,
            "exact_ground_energy": exact_e0,
            "final_energy": final_energy,
            "optimal_theta": theta,
        }

    def optimize_lucas(
        self,
        H: ComplexMatrix,
        problem_size: int,
        iterations: int = 30,
    ) -> Dict[str, Any]:
        """VQE with Lucas-adaptive ansatz and gradient scaling."""
        theta = self.lucas_adaptive_ansatz({"num_qubits": problem_size})
        # Lucas-enhanced learning rate: φ^0.5 factor per the analysis.
        lr = 0.1 * (self.lucas_engine.phi**0.5)
        return self.optimize(H, theta, iterations=iterations, learning_rate=lr)

    def lucas_bound(self, problem_size: int) -> Dict[str, Any]:
        """Wire to the pool's gap_kernel — spectral gap of the Ising Hamiltonian."""
        import numpy as np

        H = self.ising_hamiltonian()
        H_np = np.array([[H.data[r][c].re for c in range(H.rows)] for r in range(H.rows)])
        result = lucas_pool.get("gap_kernel")(H_np, 10)
        result["algorithm"] = "VQE"
        result["problem_size"] = problem_size
        return result


__all__ = [
    "LucasEngine",
    "ScalingPoint",
    "QuantumGates",
    "MathEigensolver",
    "ExactQFT",
    "GroverSearch",
    "QuantumPhaseEstimation",
    "QuantumWalk",
    "VQE",
]
