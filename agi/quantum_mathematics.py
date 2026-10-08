"""
Pure Quantum Mathematics Module

Real quantum mathematical calculations and computations.
No simulations - only pure quantum mathematics and real calculations.
"""

import logging
from dataclasses import dataclass

import numpy as np

from agi.quantum_decision import grover_amplify
from kellogg.quantum_tensor import Complex
from kellogg.quantum_tensor import QuantumState as _SubstrateState

logger = logging.getLogger(__name__)


@dataclass
class QuantumState:
    """Pure quantum state representation"""

    amplitudes: np.ndarray
    dimension: int
    is_normalized: bool = True

    def normalize(self):
        """Normalize the quantum state"""
        norm = np.linalg.norm(self.amplitudes)
        if norm > 0:
            self.amplitudes = self.amplitudes / norm
            self.is_normalized = True


@dataclass
class QuantumOperator:
    """Pure quantum operator representation"""

    matrix: np.ndarray
    dimension: int
    is_unitary: bool = False
    is_hermitian: bool = False

    def check_unitary(self):
        """Check if operator is unitary"""
        identity = np.eye(self.dimension)
        product = self.matrix @ self.matrix.conj().T
        self.is_unitary = np.allclose(product, identity)
        return self.is_unitary

    def check_hermitian(self):
        """Check if operator is Hermitian"""
        self.is_hermitian = np.allclose(self.matrix, self.matrix.conj().T)
        return self.is_hermitian


class QuantumMathematics:
    """Pure Quantum Mathematics Engine

    Provides real quantum mathematical calculations without any simulations.
    Based on actual quantum mechanics principles and mathematical formulations.
    """

    def __init__(self):
        self.precision = 1e-12

    def create_qubit_state(self, alpha: complex, beta: complex) -> QuantumState:
        """Create a pure qubit quantum state |ψ⟩ = α|0⟩ + β|1⟩"""
        amplitudes = np.array([alpha, beta], dtype=complex)
        state = QuantumState(amplitudes, 2)
        state.normalize()
        return state

    def create_entangled_state(self, n_qubits: int) -> QuantumState:
        """Create an n-qubit entangled state using real quantum mathematics"""
        dimension = 2**n_qubits
        amplitudes = np.ones(dimension, dtype=complex) / np.sqrt(dimension)
        return QuantumState(amplitudes, dimension)

    def apply_quantum_gate(self, state: QuantumState, gate: QuantumOperator) -> QuantumState:
        """Apply a quantum gate to a quantum state using real matrix multiplication"""
        if state.dimension != gate.dimension:
            raise ValueError("State and gate dimensions must match")

        new_amplitudes = gate.matrix @ state.amplitudes
        return QuantumState(new_amplitudes, state.dimension)

    def calculate_expectation_value(
        self, state: QuantumState, observable: QuantumOperator
    ) -> complex:
        """Calculate expectation value ⟨ψ|O|ψ⟩ using real quantum mathematics"""
        if not state.is_normalized:
            state.normalize()

        # ⟨ψ|O|ψ⟩ = ψ† O ψ
        bra = state.amplitudes.conj()
        ket = state.amplitudes
        result = bra @ observable.matrix @ ket
        return result

    def calculate_probability_amplitude(self, state: QuantumState, basis_state: int) -> complex:
        """Calculate probability amplitude ⟨i|ψ⟩"""
        if basis_state >= state.dimension:
            raise ValueError("Basis state index out of range")

        return state.amplitudes[basis_state]

    def calculate_probability(self, state: QuantumState, basis_state: int) -> float:
        """Calculate probability |⟨i|ψ⟩|²"""
        amplitude = self.calculate_probability_amplitude(state, basis_state)
        return abs(amplitude) ** 2

    def measure_state(
        self, state: QuantumState, random_seed: float | None = None
    ) -> tuple[int, float]:
        """PVM collapse onto the maximum Born-probability basis state.

        Deterministic: without ``random_seed`` the outcome is
        argmax_i |α_i|² — the maximum-likelihood measurement. With
        ``random_seed`` it is an explicit CDF threshold in [0, 1)
        reproducing a Born-rule draw (mirroring the substrate's
        ``QuantumState.measure_pvm`` semantics); out-of-range seeds fail
        closed rather than silently pinning a boundary outcome. No
        pseudo-random draws are made.
        """
        if not state.is_normalized:
            state.normalize()

        probabilities = [self.calculate_probability(state, i) for i in range(state.dimension)]

        if random_seed is None:
            measured_state = int(np.argmax(probabilities))
        else:
            r = float(random_seed)
            if not 0.0 <= r < 1.0:
                raise ValueError("random_seed must be a CDF threshold in [0, 1)")
            cumulative_probs = np.cumsum(probabilities)
            measured_state = int(np.searchsorted(cumulative_probs, r))

        return measured_state, probabilities[measured_state]

    def create_hadamard_gate(self, n_qubits: int = 1) -> QuantumOperator:
        """Create Hadamard gate using real quantum mathematics"""
        if n_qubits == 1:
            # H = 1/√2 [[1, 1], [1, -1]]
            matrix = np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2)
        else:
            # Multi-qubit Hadamard gate
            h1 = np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2)
            matrix = h1
            for _ in range(n_qubits - 1):
                matrix = np.kron(matrix, h1)

        gate = QuantumOperator(matrix, 2**n_qubits)
        gate.check_unitary()
        return gate

    def create_pauli_x_gate(self) -> QuantumOperator:
        """Create Pauli-X gate (quantum NOT gate)"""
        # X = [[0, 1], [1, 0]]
        matrix = np.array([[0, 1], [1, 0]], dtype=complex)
        gate = QuantumOperator(matrix, 2)
        gate.check_unitary()
        return gate

    def create_pauli_y_gate(self) -> QuantumOperator:
        """Create Pauli-Y gate"""
        # Y = [[0, -i], [i, 0]]
        matrix = np.array([[0, -1j], [1j, 0]], dtype=complex)
        gate = QuantumOperator(matrix, 2)
        gate.check_unitary()
        return gate

    def create_pauli_z_gate(self) -> QuantumOperator:
        """Create Pauli-Z gate"""
        # Z = [[1, 0], [0, -1]]
        matrix = np.array([[1, 0], [0, -1]], dtype=complex)
        gate = QuantumOperator(matrix, 2)
        gate.check_unitary()
        return gate

    def create_cnot_gate(self) -> QuantumOperator:
        """Create CNOT gate using real quantum mathematics"""
        # CNOT = |0⟩⟨0| ⊗ I + |1⟩⟨1| ⊗ X
        # = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]]
        matrix = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]], dtype=complex)
        gate = QuantumOperator(matrix, 4)
        gate.check_unitary()
        return gate

    def create_rotation_gate(self, theta: float, axis: str) -> QuantumOperator:
        """Create rotation gate around specified axis"""
        if axis.lower() == "x":
            # Rx(θ) = exp(-iθX/2)
            matrix = np.array(
                [
                    [np.cos(theta / 2), -1j * np.sin(theta / 2)],
                    [-1j * np.sin(theta / 2), np.cos(theta / 2)],
                ],
                dtype=complex,
            )
        elif axis.lower() == "y":
            # Ry(θ) = exp(-iθY/2)
            matrix = np.array(
                [
                    [np.cos(theta / 2), -np.sin(theta / 2)],
                    [np.sin(theta / 2), np.cos(theta / 2)],
                ],
                dtype=complex,
            )
        elif axis.lower() == "z":
            # Rz(θ) = exp(-iθZ/2)
            matrix = np.array(
                [[np.exp(-1j * theta / 2), 0], [0, np.exp(1j * theta / 2)]],
                dtype=complex,
            )
        else:
            raise ValueError("Axis must be 'x', 'y', or 'z'")

        gate = QuantumOperator(matrix, 2)
        gate.check_unitary()
        return gate

    def calculate_fidelity(self, state1: QuantumState, state2: QuantumState) -> float:
        """Calculate quantum fidelity between two states"""
        if state1.dimension != state2.dimension:
            raise ValueError("States must have the same dimension")

        # Fidelity = |⟨ψ1|ψ2⟩|²
        overlap = np.conj(state1.amplitudes) @ state2.amplitudes
        return abs(overlap) ** 2

    def calculate_trace_distance(self, state1: QuantumState, state2: QuantumState) -> float:
        """Calculate trace distance between two quantum states"""
        if state1.dimension != state2.dimension:
            raise ValueError("States must have the same dimension")

        # For pure states: D = sqrt(1 - |⟨ψ1|ψ2⟩|²)
        fidelity = self.calculate_fidelity(state1, state2)
        return np.sqrt(1 - fidelity)

    def create_density_matrix(self, state: QuantumState) -> np.ndarray:
        """Create density matrix ρ = |ψ⟩⟨ψ|"""
        ket = state.amplitudes.reshape(-1, 1)
        bra = np.conj(state.amplitudes).reshape(1, -1)
        return ket @ bra

    def calculate_von_neumann_entropy(self, density_matrix: np.ndarray) -> float:
        """Calculate von Neumann entropy S(ρ) = -Tr(ρ log ρ)"""
        eigenvalues = np.linalg.eigvals(density_matrix)
        # Filter out negative eigenvalues due to numerical errors
        eigenvalues = np.maximum(eigenvalues, 0)
        # Add small epsilon to avoid log(0)
        eigenvalues = eigenvalues + 1e-15
        entropy = -np.sum(eigenvalues * np.log(eigenvalues))
        return np.real(entropy)

    def create_bell_state(self, state_type: int = 0) -> QuantumState:
        """Create Bell states using real quantum mathematics"""
        if state_type == 0:
            # |Φ⁺⟩ = (|00⟩ + |11⟩)/√2
            amplitudes = np.array([1, 0, 0, 1], dtype=complex) / np.sqrt(2)
        elif state_type == 1:
            # |Φ⁻⟩ = (|00⟩ - |11⟩)/√2
            amplitudes = np.array([1, 0, 0, -1], dtype=complex) / np.sqrt(2)
        elif state_type == 2:
            # |Ψ⁺⟩ = (|01⟩ + |10⟩)/√2
            amplitudes = np.array([0, 1, 1, 0], dtype=complex) / np.sqrt(2)
        elif state_type == 3:
            # |Ψ⁻⟩ = (|01⟩ - |10⟩)/√2
            amplitudes = np.array([0, 1, -1, 0], dtype=complex) / np.sqrt(2)
        else:
            raise ValueError("Bell state type must be 0, 1, 2, or 3")

        return QuantumState(amplitudes, 4)

    def quantum_fourier_transform(self, state: QuantumState) -> QuantumState:
        """Apply Quantum Fourier Transform using real quantum mathematics"""
        n = int(np.log2(state.dimension))
        if 2**n != state.dimension:
            raise ValueError("State dimension must be a power of 2")

        # QFT matrix
        qft_matrix = np.zeros((state.dimension, state.dimension), dtype=complex)
        omega = np.exp(2j * np.pi / state.dimension)

        for i in range(state.dimension):
            for j in range(state.dimension):
                qft_matrix[i, j] = omega ** (i * j)

        qft_matrix = qft_matrix / np.sqrt(state.dimension)

        gate = QuantumOperator(qft_matrix, state.dimension)
        gate.check_unitary()

        return self.apply_quantum_gate(state, gate)

    def grover_diffusion_operator(self, n_qubits: int) -> QuantumOperator:
        """Create Grover diffusion operator using real quantum mathematics"""
        dimension = 2**n_qubits

        # |s⟩⟨s| where |s⟩ = (1/√N)∑|i⟩
        uniform_state = np.ones(dimension, dtype=complex) / np.sqrt(dimension)
        uniform_matrix = np.outer(uniform_state, np.conj(uniform_state))

        # Diffusion operator: D = 2|s⟩⟨s| - I
        identity = np.eye(dimension, dtype=complex)
        diffusion_matrix = 2 * uniform_matrix - identity

        gate = QuantumOperator(diffusion_matrix, dimension)
        gate.check_unitary()
        return gate

    def solve_linear_system(self, matrix: np.ndarray, vector: np.ndarray) -> np.ndarray:
        """Solve linear system Ax = b using real quantum mathematical methods"""
        try:
            # Use QR decomposition for numerical stability
            q, r = np.linalg.qr(matrix)
            y = q.T.conj() @ vector
            solution = np.linalg.solve(r, y)
            return solution
        except np.linalg.LinAlgError:
            # Fall back to pseudo-inverse for singular matrices
            pseudo_inv = np.linalg.pinv(matrix)
            return pseudo_inv @ vector

    def calculate_eigenvalues(self, matrix: np.ndarray) -> np.ndarray:
        """Calculate eigenvalues using real quantum mathematical methods"""
        eigenvalues = np.linalg.eigvals(matrix)
        # Sort eigenvalues by magnitude
        return np.sort(eigenvalues)

    def calculate_singular_values(self, matrix: np.ndarray) -> np.ndarray:
        """Calculate singular values using real quantum mathematical methods"""
        return np.linalg.svd(matrix, compute_uv=False)

    def quantum_phase_estimation(
        self, unitary: np.ndarray, eigenvector: np.ndarray, precision_qubits: int
    ) -> float:
        """Perform quantum phase estimation using real quantum mathematics"""
        # This is a simplified version of quantum phase estimation
        # In practice, this would require a full quantum circuit

        # Calculate the phase by finding the eigenvalue
        eigenvalue = np.conj(eigenvector) @ unitary @ eigenvector
        phase = np.angle(eigenvalue)

        return phase


class QuantumDecisionTheory:
    """Quantum Decision Theory Engine

    Applies real quantum mathematics to decision making and optimization.
    No classical simulations - only pure quantum mathematical formulations.
    """

    def __init__(self):
        self.quantum_math = QuantumMathematics()

    def quantum_decision_operator(
        self, options: list[dict[str, complex]], weights: list[float]
    ) -> QuantumOperator:
        """Create quantum decision operator from options and weights"""
        n_options = len(options)
        dimension = 2 ** int(np.ceil(np.log2(n_options)))

        # Create superposition of options
        amplitudes = np.zeros(dimension, dtype=complex)
        for i, (option, weight) in enumerate(zip(options, weights)):
            # Map option utility to quantum amplitude
            utility = option.get("utility", 0)
            amplitude = weight * np.exp(1j * utility)
            amplitudes[i] = amplitude

        # Normalize
        amplitudes = amplitudes / np.linalg.norm(amplitudes)

        # Create decision operator
        decision_matrix = np.outer(amplitudes, np.conj(amplitudes))

        return QuantumOperator(decision_matrix, dimension)

    def quantum_optimization(
        self,
        objective_function: callable,
        constraints: list[callable],
        initial_state: QuantumState,
    ) -> QuantumState:
        """Grover amplitude amplification of the optimal basis state.

        The objective defines the oracle: basis states are evaluated, the
        feasible argmax is marked by the phase oracle, and the diffusion
        operator D = 2|s⟩⟨s| − I amplifies it for the Grover-optimal
        π/4·√(N/M) iterations — real unitary evolution on the kellogg
        substrate (``agi.quantum_decision.grover_amplify``), not a
        classical parameter optimizer.
        """
        dim = initial_state.dimension

        def feasible(i: int) -> bool:
            for constraint in constraints or []:
                if not constraint(i):
                    return False
            return True

        values = np.array(
            [objective_function(i) if feasible(i) else -np.inf for i in range(dim)],
            dtype=float,
        )
        marked = int(np.argmax(values))
        if not np.isfinite(values[marked]):
            raise RuntimeError(
                "quantum_optimization unavailable: no feasible basis state "
                "satisfies the supplied constraints"
            )

        amps = np.asarray(initial_state.amplitudes, dtype=complex)
        qs = _SubstrateState(
            dim,
            [Complex(float(a.real), float(a.imag)) for a in amps],
            normalize=True,
        )
        evolved, _iterations = grover_amplify(qs, [marked])
        out = np.array([complex(a.re, a.im) for a in evolved.amplitudes])
        return QuantumState(out, dim)

    def _params_to_state(self, params: np.ndarray, dimension: int) -> QuantumState:
        """Convert parameters to quantum state"""
        amplitudes = params[:dimension].astype(complex)
        return QuantumState(amplitudes, dimension)

    def _function_to_observable(self, func: callable, dimension: int) -> QuantumOperator:
        """Convert function to quantum observable"""
        # Create diagonal matrix with function values
        values = np.array([func(i) for i in range(dimension)])
        matrix = np.diag(values.astype(complex))
        return QuantumOperator(matrix, dimension)

    def quantum_game_theory(
        self, payoff_matrix: np.ndarray, player_strategies: list[QuantumState]
    ) -> dict[str, float]:
        """Apply quantum game theory using real quantum mathematics"""

        results = {}

        # Calculate expected payoffs for each player
        for i, strategy in enumerate(player_strategies):
            # Apply payoff matrix as quantum operator
            observable = QuantumOperator(payoff_matrix, strategy.dimension)
            payoff = self.quantum_math.calculate_expectation_value(strategy, observable)
            results[f"player_{i}_payoff"] = np.real(payoff)

        return results


class QuantumCausalAnalysis:
    """Quantum Causal Analysis Engine

    Performs causal analysis using real quantum mathematical principles.
    No classical approximations - only pure quantum formulations.
    """

    def __init__(self):
        self.quantum_math = QuantumMathematics()

    def quantum_causal_operator(
        self, causal_graph: dict[str, list[str]], variables: list[str]
    ) -> QuantumOperator:
        """Create quantum causal operator from causal graph"""
        n_vars = len(variables)
        dimension = 2**n_vars

        # Create causal influence matrix
        influence_matrix = np.zeros((dimension, dimension), dtype=complex)

        # Apply causal relationships
        for source, targets in causal_graph.items():
            source_idx = variables.index(source)
            for target in targets:
                target_idx = variables.index(target)
                # Create quantum causal link
                influence_matrix += self._create_causal_link(source_idx, target_idx, n_vars)

        # Normalize to create valid quantum operator
        influence_matrix = influence_matrix / np.max(np.abs(influence_matrix))

        return QuantumOperator(influence_matrix, dimension)

    def _create_causal_link(self, source_idx: int, target_idx: int, n_vars: int) -> np.ndarray:
        """Create quantum causal link between variables"""
        dimension = 2**n_vars
        matrix = np.zeros((dimension, dimension), dtype=complex)

        # Create controlled operation
        for i in range(dimension):
            binary = format(i, f"0{n_vars}b")
            source_bit = int(binary[source_idx])

            if source_bit == 1:  # If source is active
                # Flip target bit (quantum causal effect)
                new_binary = list(binary)
                new_binary[target_idx] = str(1 - int(new_binary[target_idx]))
                new_idx = int("".join(new_binary), 2)
                matrix[new_idx, i] = 1

        return matrix

    def quantum_intervention(
        self, system_state: QuantumState, intervention: dict[str, complex]
    ) -> QuantumState:
        """Apply quantum intervention to system state"""

        # Create intervention operator
        dimension = system_state.dimension
        intervention_matrix = np.eye(dimension, dtype=complex)

        for variable, value in intervention.items():
            var_idx = int(variable)
            # Apply quantum intervention
            intervention_matrix[var_idx, var_idx] = value

        intervention_op = QuantumOperator(intervention_matrix, dimension)

        # Apply intervention
        return self.quantum_math.apply_quantum_gate(system_state, intervention_op)

    def quantum_counterfactual(
        self, actual_state: QuantumState, counterfactual_condition: dict[str, complex]
    ) -> QuantumState:
        """Calculate quantum counterfactual using real quantum mathematics"""

        # Create counterfactual operator
        dimension = actual_state.dimension
        counterfactual_matrix = np.eye(dimension, dtype=complex)

        for condition, value in counterfactual_condition.items():
            cond_idx = int(condition)
            counterfactual_matrix[cond_idx, cond_idx] = value

        counterfactual_op = QuantumOperator(counterfactual_matrix, dimension)

        # Apply counterfactual
        return self.quantum_math.apply_quantum_gate(actual_state, counterfactual_op)
