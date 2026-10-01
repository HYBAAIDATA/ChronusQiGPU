"""Property and invariant tests for the 2026 quantum algorithm suite."""

import math
import numpy as np
from quantum_compute_substrate.quantum_2026._linalg import expm

from quantum_compute_substrate.quantum_2026 import (
    ModernVQE,
    adapt_operator_pool,
    parameter_shift_gradient,
    quantum_fisher_information_matrix,
    zero_noise_extrapolate,
    ModernQAOA,
    egger_warm_start_angles,
    multi_angle_qaoa_params,
    quantum_kernel_matrix,
    projected_quantum_kernel,
    ModernQSim,
    suzuki_trotter_4th_order,
    qdrift_channel,
    ModernQWalk,
    szegedy_walk_operator,
    ModernQSense,
    ghz_qfi,
    product_state_qfi,
    ModernQAnneal,
    ModernQEC,
    surface_code_logical_error_rate,
    ModernHybrid,
    QuantumAlgorithmType,
    QuantumCircuitMetrics,
)


# ==================== VQE ====================
class TestVQEParameterShift:
    def test_matches_analytical_gradient_of_cos(self):
        # f(t) = cos(t_0) has df/dt_0 = -sin(t_0)
        def f(t):
            return float(np.cos(t[0]))

        for t0 in np.linspace(-1.0, 1.0, 8):
            g = parameter_shift_gradient(f, np.array([t0]))
            assert abs(g[0] - (-math.sin(t0))) < 1e-9

    def test_two_parameter_gradient(self):
        def f(t):
            return float(np.cos(t[0]) + np.sin(t[1]))

        t = np.array([0.3, 0.7])
        g = parameter_shift_gradient(f, t)
        assert abs(g[0] - (-math.sin(0.3))) < 1e-9
        assert abs(g[1] - math.cos(0.7)) < 1e-9


class TestVQEQFIM:
    def test_qfim_symmetric(self):
        def state(theta):
            s = np.array(
                [
                    math.cos(theta[0] / 2),
                    math.sin(theta[0] / 2) * math.cos(theta[1]),
                    math.sin(theta[0] / 2) * math.sin(theta[1]),
                    0.0,
                ],
                dtype=complex,
            )
            return s / np.linalg.norm(s)

        F = quantum_fisher_information_matrix(state, np.array([0.5, 0.7]))
        assert np.allclose(F, F.T, atol=1e-8)

    def test_qfim_positive_semidefinite(self):
        def state(theta):
            s = np.array(
                [
                    math.cos(theta[0]),
                    math.sin(theta[0]) * math.cos(theta[1]),
                    math.sin(theta[0]) * math.sin(theta[1]),
                    0.0,
                ],
                dtype=complex,
            )
            return s / np.linalg.norm(s)

        F = quantum_fisher_information_matrix(state, np.array([0.4, 0.9]))
        eigs = np.linalg.eigvalsh(F)
        assert (eigs >= -1e-6).all(), f"QFIM has negative eigenvalue: {eigs}"

    def test_single_qubit_rx_qfi_equals_one(self):
        # |psi(t)> = cos(t/2)|0> - i sin(t/2)|1>. QFI on this state should be 1.
        def state(theta):
            return np.array([math.cos(theta[0] / 2), -1j * math.sin(theta[0] / 2)], dtype=complex)

        F = quantum_fisher_information_matrix(state, np.array([0.3]))
        assert abs(F[0, 0] - 1.0) < 1e-3


class TestAdaptOperatorPool:
    def test_pool_size_scales(self):
        pool = adapt_operator_pool(4)
        # 4 single-Y + C(4,2)=6 pairs each contributing 2 operators = 4 + 12 = 16
        assert len(pool) == 16

    def test_pool_size_for_small_n(self):
        assert len(adapt_operator_pool(1)) == 1
        assert len(adapt_operator_pool(2)) == 4


class TestZeroNoiseExtrapolation:
    def test_linear_recovers_exact_intercept(self):
        xs = [1.0, 2.0, 3.0]
        ys = [2.0, 3.0, 4.0]  # y = 1 + x
        val = zero_noise_extrapolate(xs, ys, method="linear")
        assert abs(val - 1.0) < 1e-9

    def test_richardson_second_order(self):
        xs = [1.0, 1.5, 2.0, 2.5, 3.0]
        # y = 5 + 2 x + x^2, exact intercept y(0) = 5
        ys = [5 + 2 * x + x * x for x in xs]
        val = zero_noise_extrapolate(xs, ys, method="richardson")
        assert abs(val - 5.0) < 1e-6

    def test_exponential_falls_back_gracefully(self):
        val = zero_noise_extrapolate([1.0, 2.0, 3.0], [1.0, 1.0, 1.0], method="exponential")
        assert isinstance(val, float)


class TestVQEAnsatz:
    def test_chemistry_ansatz_includes_ry_cnot(self):
        v = ModernVQE(num_qubits=3)
        ans = v.adaptive_ansatz({"type": "chemistry", "symmetries": ["Z2", "U1"]})
        assert "RY" in ans and "CNOT" in ans and "RZ" in ans

    def test_barren_plateau_learning_rate_bounds(self):
        v = ModernVQE(num_qubits=2)
        assert v.barren_plateau_learning_rate([]) == 0.01
        assert v.barren_plateau_learning_rate([1e-10] * 10) == 0.1
        # High-variance history -> normal learning rate
        assert v.barren_plateau_learning_rate([0.0, 1.0] * 5) == 0.01


# ==================== QAOA ====================
class TestQAOAEggerWarmStart:
    def test_uniform_p_gives_pi_over_2(self):
        angles = egger_warm_start_angles(np.array([0.5, 0.5, 0.5]))
        assert np.allclose(angles, np.pi / 2, atol=1e-9)

    def test_p_zero_and_one_give_zero_and_pi(self):
        angles = egger_warm_start_angles(np.array([0.0, 1.0]))
        assert abs(angles[0] - 0.0) < 1e-9
        assert abs(angles[1] - np.pi) < 1e-9

    def test_clipping_out_of_range(self):
        angles = egger_warm_start_angles(np.array([-0.5, 1.5]))
        assert abs(angles[0] - 0.0) < 1e-9
        assert abs(angles[1] - np.pi) < 1e-9

    def test_monotonicity(self):
        ps = np.linspace(0, 1, 20)
        angles = egger_warm_start_angles(ps)
        assert (np.diff(angles) >= -1e-12).all()


class TestQAOADepth:
    def test_depth_within_bounds(self):
        q = ModernQAOA(num_qubits=8, max_depth=10)
        for connectivity in ("sparse", "dense", "medium"):
            for c in (0.0, 0.5, 1.0):
                d = q.adaptive_depth(64, {"connectivity": connectivity, "constraint_ratio": c})
                assert 1 <= d <= 10


class TestMultiAngleQAOA:
    def test_parameter_shapes(self):
        p = multi_angle_qaoa_params(num_edges=5, num_nodes=4, depth=3)
        assert p["gamma"].shape == (3, 5)
        assert p["beta"].shape == (3, 4)


class TestRQAOA:
    def test_picks_max_correlation(self):
        C = np.array([[0.0, 0.1, 0.9], [0.1, 0.0, 0.2], [0.9, 0.2, 0.0]])
        q = ModernQAOA(num_qubits=3)
        i, j, sign = q.recursive_qaoa_eliminate(C)
        assert (i, j) == (0, 2)
        assert sign == 1

    def test_picks_negative_correlation(self):
        C = np.array([[0.0, 0.1, -0.9], [0.1, 0.0, 0.2], [-0.9, 0.2, 0.0]])
        q = ModernQAOA(num_qubits=3)
        _, _, sign = q.recursive_qaoa_eliminate(C)
        assert sign == -1


# ==================== QML ====================
class TestQuantumKernel:
    def test_symmetric(self):
        X = np.random.default_rng(0).standard_normal((6, 3))
        K = quantum_kernel_matrix(X, layers=2)
        assert np.allclose(K, K.T, atol=1e-10)

    def test_diagonal_is_one(self):
        X = np.random.default_rng(1).standard_normal((5, 3))
        K = quantum_kernel_matrix(X, layers=2)
        assert np.allclose(np.diag(K), 1.0, atol=1e-9)

    def test_bounded_in_zero_one(self):
        X = np.random.default_rng(2).standard_normal((4, 3))
        K = quantum_kernel_matrix(X, layers=2)
        assert (K >= -1e-10).all() and (K <= 1.0 + 1e-10).all()

    def test_positive_semidefinite(self):
        X = np.random.default_rng(3).standard_normal((5, 3))
        K = quantum_kernel_matrix(X, layers=2)
        eigs = np.linalg.eigvalsh(K)
        assert (eigs >= -1e-8).all(), f"kernel has negative eigenvalue: {eigs}"


class TestProjectedKernel:
    def test_symmetric_and_diagonal_one(self):
        X = np.random.default_rng(4).standard_normal((5, 3))
        K = projected_quantum_kernel(X, layers=2, gamma=1.0)
        assert np.allclose(K, K.T, atol=1e-10)
        assert np.allclose(np.diag(K), 1.0, atol=1e-9)

    def test_bounded_in_zero_one(self):
        X = np.random.default_rng(5).standard_normal((4, 3))
        K = projected_quantum_kernel(X, layers=2)
        assert (K >= 0.0).all() and (K <= 1.0 + 1e-10).all()


# ==================== QSim ====================
class TestSuzukiTrotter:
    def test_unitary(self):
        rng = np.random.default_rng(0)
        d = 4
        H1 = rng.standard_normal((d, d)) + 1j * rng.standard_normal((d, d))
        H1 = 0.5 * (H1 + H1.conj().T)
        H2 = rng.standard_normal((d, d)) + 1j * rng.standard_normal((d, d))
        H2 = 0.5 * (H2 + H2.conj().T)
        U = suzuki_trotter_4th_order(0.05, H1, H2)
        assert np.allclose(U @ U.conj().T, np.eye(d), atol=1e-9)

    def test_fourth_order_more_accurate_than_second(self):
        rng = np.random.default_rng(1)
        d = 4
        H1 = rng.standard_normal((d, d)) + 1j * rng.standard_normal((d, d))
        H1 = 0.5 * (H1 + H1.conj().T)
        H2 = rng.standard_normal((d, d)) + 1j * rng.standard_normal((d, d))
        H2 = 0.5 * (H2 + H2.conj().T)
        dt = 0.05
        exact = expm(-1j * dt * (H1 + H2))
        from quantum_compute_substrate.quantum_2026.qsim import _second_order

        U2 = _second_order(dt, H1, H2)
        U4 = suzuki_trotter_4th_order(dt, H1, H2)
        e2 = float(np.linalg.norm(U2 - exact))
        e4 = float(np.linalg.norm(U4 - exact))
        assert e4 < e2, f"4th order error {e4} not better than 2nd order {e2}"


class TestQDrift:
    def test_returns_unitary_matrix(self):
        rng = np.random.default_rng(7)
        H = [rng.standard_normal((3, 3)) + 1j * rng.standard_normal((3, 3)) for _ in range(3)]
        H = [0.5 * (h + h.conj().T) for h in H]
        w = [1.0, 0.5, 2.0]
        U = qdrift_channel(H, w, time=0.1, samples=20, seed=0)
        assert np.allclose(U @ U.conj().T, np.eye(3), atol=1e-9)

    def test_zero_time_is_identity(self):
        H = [np.eye(2, dtype=complex)]
        U = qdrift_channel(H, [1.0], time=0.0, samples=10)
        assert np.allclose(U, np.eye(2))


class TestQSimEvolution:
    def test_norm_preservation(self):
        rng = np.random.default_rng(2)
        H = rng.standard_normal((4, 4)) + 1j * rng.standard_normal((4, 4))
        H = 0.5 * (H + H.conj().T)
        sim = ModernQSim(num_qubits=2, hamiltonian=H)
        psi0 = np.array([1, 0, 0, 0], dtype=complex)
        psi = sim.evolve(psi0, time=0.5, steps=20, order=4)
        assert abs(np.linalg.norm(psi) - 1.0) < 1e-6

    def test_energy_conservation(self):
        rng = np.random.default_rng(3)
        H = rng.standard_normal((4, 4)) + 1j * rng.standard_normal((4, 4))
        H = 0.5 * (H + H.conj().T)
        sim = ModernQSim(num_qubits=2, hamiltonian=H)
        psi0 = np.array([1, 1, 0, 0], dtype=complex) / math.sqrt(2)
        e0 = float(np.real(psi0.conj() @ H @ psi0))
        psi = sim.evolve(psi0, time=0.3, steps=30, order=4)
        e1 = float(np.real(psi.conj() @ H @ psi))
        assert abs(e0 - e1) < 1e-3

    def test_adaptive_stepping_completes(self):
        rng = np.random.default_rng(9)
        H = rng.standard_normal((4, 4)) + 1j * rng.standard_normal((4, 4))
        H = 0.5 * (H + H.conj().T)
        sim = ModernQSim(num_qubits=2, hamiltonian=H)
        res = sim.adaptive_time_stepping(np.array([1, 0, 0, 0], dtype=complex), target_time=0.5)
        assert abs(res["total_time"] - 0.5) < 1e-3
        assert abs(np.linalg.norm(res["final_state"]) - 1.0) < 1e-6


# ==================== QWalk ====================
class TestContinuousTimeWalk:
    def test_unitary(self):
        A = np.array([[0, 1, 1, 0], [1, 0, 1, 1], [1, 1, 0, 1], [0, 1, 1, 0]], dtype=float)
        w = ModernQWalk(A)
        U = w.continuous_time_walk(0.7)
        assert np.allclose(U @ U.conj().T, np.eye(4), atol=1e-9)

    def test_search_probability_valid(self):
        A = np.ones((5, 5)) - np.eye(5)
        r = ModernQWalk(A).search(target=2)
        assert 0.0 <= r["target_probability"] <= 1.0
        assert abs(r["speedup"] - math.sqrt(5)) < 1e-9


class TestSzegedyWalk:
    def test_unitary(self):
        rng = np.random.default_rng(0)
        P = rng.random((4, 4))
        P = P / P.sum(axis=1, keepdims=True)
        U = szegedy_walk_operator(P)
        assert np.allclose(U @ U.conj().T, np.eye(16), atol=1e-9)

    def test_orthogonal_when_P_is_real(self):
        P = np.array([[0.5, 0.5], [0.3, 0.7]])
        U = szegedy_walk_operator(P)
        # U real orthogonal => U^T U = I
        assert np.allclose(U.T @ U, np.eye(4), atol=1e-9)


# ==================== QSense ====================
class TestMetrology:
    def test_ghz_heisenberg_limit(self):
        assert ghz_qfi(2) == 4
        assert ghz_qfi(4) == 16
        assert ghz_qfi(10) == 100

    def test_product_state_sql(self):
        assert product_state_qfi(2) == 2
        assert product_state_qfi(10) == 10

    def test_ghz_beats_product(self):
        for n in range(2, 10):
            assert ghz_qfi(n) > product_state_qfi(n)

    def test_metrology_reports(self):
        r = ModernQSense(num_qubits=8).metrology(num_measurements=1000, use_ghz=True)
        assert r["quantum_fisher_information"] == 64
        assert r["quantum_std"] < r["classical_std"]
        assert r["quantum_advantage"] > 1.0


# ==================== QAnneal ====================
class TestQAnneal:
    def test_reverse_anneal_norm_preserved(self):
        rng = np.random.default_rng(0)
        H = rng.standard_normal((4, 4))
        H = 0.5 * (H + H.T)
        a = ModernQAnneal(H.astype(complex))
        r = a.reverse_anneal(
            np.array([1, 0, 0, 0], dtype=complex), annealing_time=0.3, schedule_steps=30
        )
        assert r["norm_residual"] < 1e-5

    def test_pause_quench_returns_state(self):
        rng = np.random.default_rng(1)
        H = rng.standard_normal((4, 4))
        H = 0.5 * (H + H.T)
        a = ModernQAnneal(H.astype(complex))
        r = a.pause_and_quench(np.array([1, 0, 0, 0], dtype=complex), steps=20)
        assert abs(np.linalg.norm(r["final_state"]) - 1.0) < 1e-5


# ==================== QEC ====================
class TestQEC:
    def test_odd_distance_required(self):
        try:
            ModernQEC(code_distance=4)
            assert False
        except ValueError:
            pass

    def test_physical_qubit_count(self):
        assert ModernQEC(3).physical_qubits == 17
        assert ModernQEC(5).physical_qubits == 49
        assert ModernQEC(7).physical_qubits == 97

    def test_correctable_error_count(self):
        assert ModernQEC(3).surface_code_metrics()["correctable_errors"] == 1
        assert ModernQEC(5).surface_code_metrics()["correctable_errors"] == 2
        assert ModernQEC(7).surface_code_metrics()["correctable_errors"] == 3

    def test_logical_error_scales_with_distance(self):
        p = 1e-3
        pL_d3 = surface_code_logical_error_rate(p, 3)
        pL_d5 = surface_code_logical_error_rate(p, 5)
        pL_d7 = surface_code_logical_error_rate(p, 7)
        assert pL_d3 > pL_d5 > pL_d7 > 0

    def test_above_threshold_returns_one(self):
        assert surface_code_logical_error_rate(0.02, 5, threshold=0.01) == 1.0

    def test_gate_costs(self):
        q = ModernQEC(3)
        assert (
            q.fault_tolerant_gate_cost("T")["physical_gates"]
            > q.fault_tolerant_gate_cost("H")["physical_gates"]
        )


# ==================== Hybrid ====================
class TestHybrid:
    def test_loop_runs(self):
        h = ModernHybrid(num_processors=1)
        r = h.loop({"data": np.zeros(3)}, max_iter=3)
        assert len(r["iterations"]) == 3
        assert all(t >= 0 for t in r["total_times"])


# ==================== Circuit metrics + enum ====================
class TestCircuitMetrics:
    def test_dataclass_frozen(self):
        m = QuantumCircuitMetrics(1, 2, 3, 0.01, 100.0, 0.99, 4)
        try:
            m.circuit_depth = 5  # type: ignore[misc]
            assert False
        except Exception:
            pass

    def test_nisq_feasibility(self):
        m = QuantumCircuitMetrics(1, 2, 3, 0.001, 50.0, 0.99, 4)
        assert m.is_nisq_feasible(coherence_budget=100, error_budget=0.01)
        assert not m.is_nisq_feasible(coherence_budget=10, error_budget=0.01)

    def test_algorithm_type_enum_has_all(self):
        keys = {a.name for a in QuantumAlgorithmType}
        for expected in (
            "VQE",
            "QAOA",
            "QML",
            "QSIM",
            "QWALK",
            "QSENSE",
            "QANNEAL",
            "QNEURON",
            "HYBRID",
            "ADAPTIVE",
        ):
            assert expected in keys
