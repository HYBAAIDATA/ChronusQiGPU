"""Property + invariant tests for the Cathedral of the Greats.

Every test is an invariant the honoree's proof would demand of the code.
"""

import math
import numpy as np

from quantum_compute_substrate.cathedral import (
    Great,
    GREATS,
    find,
    schrodinger,
    heisenberg,
    dirac,
    pauli,
    von_neumann,
    einstein,
    bell,
    feynman,
    turing,
    shannon,
    landauer,
    deutsch,
)


# ==================== Registry ====================
class TestRegistry:
    def test_at_least_twelve_greats(self):
        assert len(GREATS) >= 12

    def test_all_greats_have_modules(self):
        for g in GREATS:
            assert isinstance(g, Great)
            assert len(g.module) > 0

    def test_find_by_name_and_module(self):
        assert find("Alan Turing").module == "turing"
        assert find("turing").name == "Alan Turing"

    def test_find_unknown_raises(self):
        try:
            find("Xerxes")
            assert False
        except KeyError:
            pass


# ==================== Schrodinger ====================
class TestSchrodinger:
    def test_evolution_is_unitary(self):
        rng = np.random.default_rng(0)
        A = rng.standard_normal((4, 4)) + 1j * rng.standard_normal((4, 4))
        H = (A + A.conj().T) / 2
        psi = np.array([1, 0, 0, 0], dtype=complex)
        out = schrodinger.schrodinger_evolution(H, psi, t=0.7)
        assert abs(np.linalg.norm(out) - 1.0) < 1e-9

    def test_evolution_conserves_energy(self):
        rng = np.random.default_rng(1)
        A = rng.standard_normal((4, 4)) + 1j * rng.standard_normal((4, 4))
        H = (A + A.conj().T) / 2
        psi = rng.standard_normal(4) + 1j * rng.standard_normal(4)
        psi = psi / np.linalg.norm(psi)
        E0 = schrodinger.energy_expectation(H, psi)
        E1 = schrodinger.energy_expectation(H, schrodinger.schrodinger_evolution(H, psi, 1.3))
        assert abs(E0 - E1) < 1e-9

    def test_evolution_at_zero_time_is_identity(self):
        H = np.diag([1.0, 2.0, 3.0, 4.0]).astype(complex)
        psi = np.array([0.5, 0.5, 0.5, 0.5], dtype=complex)
        out = schrodinger.schrodinger_evolution(H, psi, 0.0)
        assert np.allclose(out, psi, atol=1e-12)

    def test_evolution_rejects_non_hermitian(self):
        H = np.array([[0, 1], [0, 0]], dtype=complex)
        try:
            schrodinger.schrodinger_evolution(H, np.array([1.0, 0]), 1.0)
            assert False
        except ValueError:
            pass

    def test_cat_state_normalized(self):
        c = schrodinger.cat_state(dim=20, alpha=1.5)
        assert abs(np.linalg.norm(c) - 1.0) < 1e-9

    def test_phi_cat_state_normalized(self):
        c = schrodinger.phi_cat_state(dim=30)
        assert abs(np.linalg.norm(c) - 1.0) < 1e-9


# ==================== Heisenberg ====================
class TestHeisenberg:
    def test_robertson_schrodinger_holds_random(self):
        rng = np.random.default_rng(2)
        A = pauli.X
        B = pauli.Y
        for _ in range(30):
            psi = rng.standard_normal(2) + 1j * rng.standard_normal(2)
            psi = psi / np.linalg.norm(psi)
            prod = heisenberg.uncertainty_product(A, B, psi)
            bound = heisenberg.robertson_schrodinger_bound(A, B, psi)
            assert prod + 1e-9 >= bound

    def test_pauli_uncertainty_at_z_eigenstate(self):
        # |0> is a Z eigenstate, so sigma_Z = 0 but sigma_X = sigma_Y = 1
        psi = np.array([1, 0], dtype=complex)
        sigmaZ = heisenberg.standard_deviation(pauli.Z, psi)
        sigmaX = heisenberg.standard_deviation(pauli.X, psi)
        assert sigmaZ < 1e-10
        assert abs(sigmaX - 1.0) < 1e-10

    def test_maassen_uffink_x_z(self):
        # For X and Z bases the max overlap is 1/sqrt(2), so bound = -log2(1/2) = 1.
        eig_X = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2)
        eig_Z = np.eye(2, dtype=complex)
        b = heisenberg.maassen_uffink_bound(eig_X, eig_Z)
        assert abs(b - 1.0) < 1e-10


# ==================== Dirac ====================
class TestDirac:
    def test_gamma_clifford_algebra(self):
        """{gamma^mu, gamma^nu} = 2 eta^{mu nu} I."""
        eta = dirac.MINKOWSKI
        I4 = np.eye(4, dtype=complex)
        for mu in range(4):
            for nu in range(4):
                anti = dirac.anticommutator(dirac.GAMMAS[mu], dirac.GAMMAS[nu])
                expected = 2 * eta[mu, nu] * I4
                assert np.allclose(anti, expected, atol=1e-12), f"{{gamma^{mu}, gamma^{nu}}}"

    def test_bra_ket_inner(self):
        assert abs(dirac.inner([1, 0], [1, 0]) - 1.0) < 1e-12
        assert abs(dirac.inner([1, 0], [0, 1])) < 1e-12

    def test_outer_product_is_projector_when_normalized(self):
        v = [1 / math.sqrt(2), 1 / math.sqrt(2)]
        P = dirac.outer(v, v)
        assert np.allclose(P @ P, P, atol=1e-10)

    def test_dirac_hamiltonian_hermitian(self):
        H = dirac.dirac_hamiltonian(mass=1.0, momentum=(0.3, 0.4, 0.5))
        assert np.allclose(H, H.conj().T, atol=1e-12)


# ==================== Pauli ====================
class TestPauli:
    def test_pauli_squared_is_identity(self):
        for M in (pauli.X, pauli.Y, pauli.Z):
            assert np.allclose(M @ M, np.eye(2, dtype=complex), atol=1e-12)

    def test_anticommutation_delta_ij(self):
        for i, A in enumerate((pauli.X, pauli.Y, pauli.Z)):
            for j, B in enumerate((pauli.X, pauli.Y, pauli.Z)):
                anti = pauli.anticommutator(A, B)
                expected = 2.0 * (1.0 if i == j else 0.0) * np.eye(2, dtype=complex)
                assert np.allclose(anti, expected, atol=1e-12)

    def test_commutation_epsilon(self):
        # [X, Y] = 2i Z, [Y, Z] = 2i X, [Z, X] = 2i Y
        assert np.allclose(pauli.commutator(pauli.X, pauli.Y), 2j * pauli.Z)
        assert np.allclose(pauli.commutator(pauli.Y, pauli.Z), 2j * pauli.X)
        assert np.allclose(pauli.commutator(pauli.Z, pauli.X), 2j * pauli.Y)

    def test_pauli_string(self):
        m = pauli.pauli_string("XZ")
        assert m.shape == (4, 4)
        assert np.allclose(m, np.kron(pauli.X, pauli.Z))

    def test_exclusion_projector_antisymmetrizes(self):
        A = pauli.exclusion_projector(2)
        # Singlet is antisymmetric: A |singlet> = |singlet>
        singlet = einstein.singlet_state()
        assert np.allclose(A @ singlet, singlet, atol=1e-10)
        # Symmetric triplet t_zero: A |t_zero> = 0
        _, t_zero, _ = einstein.triplet_states()
        t_zero_normed = t_zero / np.linalg.norm(t_zero)
        assert np.allclose(A @ t_zero_normed, np.zeros(4), atol=1e-10)


# ==================== von Neumann ====================
class TestVonNeumann:
    def test_pure_state_entropy_zero(self):
        psi = np.array([1, 0, 0, 0], dtype=complex)
        rho = von_neumann.density_matrix(psi)
        assert von_neumann.von_neumann_entropy(rho) < 1e-10

    def test_maximally_mixed_entropy_log_d(self):
        d = 4
        rho = np.eye(d, dtype=complex) / d
        assert abs(von_neumann.von_neumann_entropy(rho) - math.log2(d)) < 1e-10

    def test_density_matrix_trace_one(self):
        psi = np.array([0.6, 0.8], dtype=complex)
        rho = von_neumann.density_matrix(psi / np.linalg.norm(psi))
        assert abs(np.trace(rho).real - 1.0) < 1e-10

    def test_partial_trace_of_singlet_is_max_mixed(self):
        s = einstein.singlet_state()
        rho = von_neumann.density_matrix(s)
        rho_A = von_neumann.partial_trace(rho, keep=0, dims=(2, 2))
        expected = np.eye(2, dtype=complex) / 2.0
        assert np.allclose(rho_A, expected, atol=1e-10)

    def test_purity_bounds(self):
        # 1/d <= Tr(rho^2) <= 1
        d = 4
        mixed = np.eye(d, dtype=complex) / d
        assert abs(von_neumann.purity(mixed) - 1.0 / d) < 1e-10
        psi = np.array([1, 0, 0, 0], dtype=complex)
        assert abs(von_neumann.purity(von_neumann.density_matrix(psi)) - 1.0) < 1e-10


# ==================== Einstein ====================
class TestEinstein:
    def test_singlet_normalized(self):
        s = einstein.singlet_state()
        assert abs(np.linalg.norm(s) - 1.0) < 1e-12

    def test_epr_anticorrelation_all_axes(self):
        for axis in ("X", "Y", "Z"):
            assert abs(einstein.epr_anticorrelation(axis) - (-1.0)) < 1e-10

    def test_singlet_is_antisymmetric_under_swap(self):
        s = einstein.singlet_state()
        swap = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], dtype=complex)
        assert np.allclose(swap @ s, -s, atol=1e-12)


# ==================== Bell ====================
class TestBell:
    def test_tsirelson_saturated_on_singlet(self):
        S = bell.tsirelson_witness()
        assert abs(S - bell.TSIRELSON) < 1e-9, f"got {S}, expected {bell.TSIRELSON}"

    def test_chsh_classical_bound_from_product_state(self):
        # A separable state cannot exceed 2
        psi = np.array([1, 0, 0, 0], dtype=complex)  # |00>
        A0, A1, B0, B1 = bell.optimal_chsh_settings()
        S = bell.chsh_value(psi, A0, A1, B0, B1)
        assert abs(S) <= 2.0 + 1e-9

    def test_mermin_ghz_three_qubits(self):
        # |<M_3>| = 4 on |GHZ_3>
        v = bell.mermin_ghz_value(3)
        assert abs(abs(v) - 4.0) < 1e-9, f"got {v}"


# ==================== Feynman ====================
class TestFeynman:
    def test_path_integral_matches_schrodinger_evolution(self):
        rng = np.random.default_rng(3)
        A = rng.standard_normal((4, 4)) + 1j * rng.standard_normal((4, 4))
        H = (A + A.conj().T) / 2
        psi = rng.standard_normal(4) + 1j * rng.standard_normal(4)
        psi = psi / np.linalg.norm(psi)
        err = feynman.path_integral_matches_schrodinger(H, psi, t=0.8, num_slices=100)
        assert err < 1e-8

    def test_discretised_propagator_is_unitary(self):
        H = np.diag([1.0, 2.0, 3.0, 4.0]).astype(complex)
        K = feynman.discretised_propagator(H, t=0.5, num_slices=50)
        assert np.allclose(K @ K.conj().T, np.eye(4), atol=1e-9)


# ==================== Turing ====================
class TestTuring:
    def test_universal_gate_set_size(self):
        assert set(turing.universal_gate_set().keys()) == {"H", "T", "CNOT"}

    def test_h_and_t_are_unitary(self):
        for g in (turing.H_GATE, turing.T_GATE, turing.CNOT_GATE):
            d = g.shape[0]
            assert np.allclose(g @ g.conj().T, np.eye(d), atol=1e-10)

    def test_bqp_witness_advantage(self):
        w = turing.bqp_witness_deutsch_query_count(10)
        assert w["quantum_queries"] == 1
        assert w["classical_worst_case_queries"] == 513
        assert w["advantage"] == 512

    def test_solovay_kitaev_bound_positive(self):
        assert turing.solovay_kitaev_bound(0.001) > 0


# ==================== Shannon ====================
class TestShannon:
    def test_uniform_entropy(self):
        for n in (2, 4, 8):
            H = shannon.shannon_entropy([1.0 / n] * n)
            assert abs(H - math.log2(n)) < 1e-10

    def test_point_mass_entropy_zero(self):
        H = shannon.shannon_entropy([1.0, 0.0, 0.0])
        assert H < 1e-12

    def test_mutual_information_independent(self):
        # Independent joint: p(x,y) = p(x) p(y) => I = 0
        joint = np.outer([0.5, 0.5], [0.25, 0.75])
        assert shannon.mutual_information(joint) < 1e-10

    def test_holevo_orthogonal_states_saturates(self):
        # For orthogonal states with uniform probabilities,
        # chi = S(rho_avg) = log2(n).
        states = [np.array([1, 0], dtype=complex), np.array([0, 1], dtype=complex)]
        chi = shannon.holevo_bound([0.5, 0.5], states)
        assert abs(chi - 1.0) < 1e-10

    def test_bsc_capacity(self):
        assert abs(shannon.channel_capacity_binary_symmetric(0.5) - 0.0) < 1e-10
        assert abs(shannon.channel_capacity_binary_symmetric(0.0) - 1.0) < 1e-10


# ==================== Landauer ====================
class TestLandauer:
    def test_landauer_cost_room_temp(self):
        # kT ln 2 at 300 K ~ 2.87e-21 J per bit.
        cost = landauer.landauer_cost(temperature_kelvin=300, bits_erased=1)
        assert 2.5e-21 < cost < 3.5e-21

    def test_zero_bits_zero_cost(self):
        assert landauer.landauer_cost(300, 0) == 0.0

    def test_fredkin_reversible(self):
        F = landauer.fredkin_gate()
        assert landauer.is_reversible(F)
        # Fredkin is its own inverse
        assert np.allclose(F @ F, np.eye(8), atol=1e-12)

    def test_toffoli_reversible(self):
        T = landauer.toffoli_gate()
        assert landauer.is_reversible(T)
        assert np.allclose(T @ T, np.eye(8), atol=1e-12)

    def test_reversible_computation_costs_zero(self):
        assert landauer.reversible_computation_cost(300, 10**9) == 0.0


# ==================== Deutsch ====================
class TestDeutsch:
    def test_deutsch_constant_zero(self):
        assert deutsch.deutsch_algorithm(lambda x: 0) == "constant"

    def test_deutsch_constant_one(self):
        assert deutsch.deutsch_algorithm(lambda x: 1) == "constant"

    def test_deutsch_balanced_identity(self):
        assert deutsch.deutsch_algorithm(lambda x: x) == "balanced"

    def test_deutsch_balanced_negation(self):
        assert deutsch.deutsch_algorithm(lambda x: 1 - x) == "balanced"

    def test_deutsch_jozsa_constant(self):
        assert deutsch.deutsch_jozsa(lambda x: 0, num_bits=3) == "constant"

    def test_deutsch_jozsa_balanced(self):
        # f(x) = x % 2: half zero, half one -> balanced
        assert deutsch.deutsch_jozsa(lambda x: x & 1, num_bits=3) == "balanced"

    def test_advantage_grows_exponentially(self):
        w = deutsch.deutsch_query_advantage(20)
        assert w["speedup"] == 2**19
