"""
Turing Exact Quantum Library — Comprehensive Test Suite
Validates exact algebraic closure, zero float drift, projective Hilbert space P(H),
discrete tunneling, Cayley evolution, and symplectic qudit stabilizer tableau.
"""

import unittest
from turing import (
    is_prime,
    gcd,
    legendre_symbol,
    cyclotomic_polynomial_prime,
    convolution,
    bareiss_det,
    ZetaP,
    RationalZetaP,
    MatrixZetaP,
    Obstruction,
    StateZetaP,
    superpose,
    inner_product,
    amplitude,
    UnitaryZetaP,
    ProjectiveUnitaryZetaP,
    pauli_x,
    pauli_z,
    cnot,
    phase,
    hadamard,
    fourier_gate_projective,
    hadamard_projective,
    born_probability,
    project,
    sum_born_probabilities,
    projective_born_probability,
    visibility,
    matrix_rank_over_field,
    schmidt_rank,
    normalized_schmidt_coefficients,
    reduced_density_gram,
    exact_renyi_purity,
    DiscreteBarrier,
    ContinuousBarrier,
    transmission_coefficient,
    transmission_coefficient_exact,
    ContinuousSchedule,
    discrete_evolution,
    continuous_adiabatic,
    cayley_evolution,
    SwarmZetaP,
    quantum_inspired_metaheuristic,
    StabilizerTableauZetaP,
    TuringError,
    RingError,
    NonUnitError,
    DimensionMismatchError,
    StateNormError,
)


class TestInvariant(unittest.TestCase):
    def test_additive_identity(self):
        p = 5
        a = ZetaP(p, (2, -1, 0, 3))
        zero = ZetaP.zero(p)
        self.assertEqual(a + zero, a)
        self.assertEqual(zero + a, a)

    def test_additive_inverse(self):
        p = 5
        a = ZetaP(p, (2, -1, 0, 3))
        zero = ZetaP.zero(p)
        self.assertEqual(a + (-a), zero)

    def test_multiplicative_identity(self):
        p = 5
        a = ZetaP(p, (2, -1, 0, 3))
        one = ZetaP.one(p)
        self.assertEqual(a * one, a)
        self.assertEqual(one * a, a)

    def test_basis_state_unit_norm(self):
        p = 5
        b0 = StateZetaP.basis(0, 3, p)
        self.assertTrue(b0.is_unit_norm())
        self.assertEqual(b0.norm_squared(), ZetaP.one(p))

    def test_unitary_preservation(self):
        p = 5
        px = pauli_x(p)
        pz = pauli_z(p)
        self.assertTrue(px.matrix.is_unitary())
        self.assertTrue(pz.matrix.is_unitary())
        prod = px.matrix * px.matrix
        self.assertEqual(prod, MatrixZetaP.identity(2, p))

    def test_projective_unitary_preservation(self):
        for p in (3, 5):
            f_proj = fourier_gate_projective(p)
            self.assertEqual(f_proj.scale_norm, p)
            dag_prod = f_proj.matrix.dagger() * f_proj.matrix
            expected = MatrixZetaP(p, p, [[ZetaP.from_int(p if i == j else 0, p) for j in range(p)] for i in range(p)], p)
            self.assertEqual(dag_prod, expected)

    def test_weyl_heisenberg_commutation(self):
        p = 3
        x_entries = [[ZetaP.zero(p) for _ in range(p)] for _ in range(p)]
        z_entries = [[ZetaP.zero(p) for _ in range(p)] for _ in range(p)]
        for j in range(p):
            x_entries[(j + 1) % p][j] = ZetaP.one(p)
            z_entries[j][j] = ZetaP.zeta_power(j, p)
        X = MatrixZetaP(p, p, x_entries, p)
        Z = MatrixZetaP(p, p, z_entries, p)
        ZX = Z * X
        XZ = X * Z
        zeta_XZ = MatrixZetaP(p, p, [[ZetaP.zeta(p) * e for e in row] for row in XZ.entries], p)
        self.assertEqual(ZX, zeta_XZ)


class TestProperty(unittest.TestCase):
    def test_distributivity(self):
        p = 5
        a = ZetaP(p, (2, -1, 0, 3))
        b = ZetaP(p, (0, 1, -2, 1))
        c = ZetaP(p, (1, 1, 1, 0))
        self.assertEqual((a + b) * c, (a * c) + (b * c))

    def test_associativity(self):
        p = 5
        a = ZetaP(p, (2, -1, 0, 3))
        b = ZetaP(p, (0, 1, -2, 1))
        c = ZetaP(p, (1, 1, 1, 0))
        self.assertEqual((a * b) * c, a * (b * c))

    def test_unit_inverses(self):
        p = 5
        one = ZetaP.one(p)
        u = ZetaP.zeta_power(2, p)
        self.assertTrue(u.is_unit())
        self.assertEqual(u * u.inverse(), one)

    def test_matrix_addition(self):
        p = 5
        a = MatrixZetaP.identity(2, p)
        b = MatrixZetaP.zero(2, 2, p)
        self.assertEqual(a + b, a)

    def test_adjoint_properties(self):
        p = 5
        px = pauli_x(p)
        self.assertEqual(px.matrix.dagger().dagger(), px.matrix)
        self.assertEqual(px.dagger().matrix, px.matrix.dagger())

    def test_kronecker_associativity(self):
        p = 3
        m1 = MatrixZetaP.identity(1, p)
        m2 = MatrixZetaP.identity(2, p)
        m3 = MatrixZetaP.identity(2, p)
        k12_3 = (m1.kron(m2)).kron(m3)
        k1_23 = m1.kron(m2.kron(m3))
        self.assertEqual(k12_3, k1_23)

    def test_rational_zeta_p_field_properties(self):
        p = 5
        one = ZetaP.one(p)
        z = ZetaP.zeta(p)
        r1 = RationalZetaP(z, 2)
        r2 = RationalZetaP(one, 3)
        r_sum = r1 + r2
        self.assertEqual(r_sum.den, 6)
        r_diff = r1 - r2
        self.assertEqual(r_diff.den, 6)
        r_prod = r1 * r2
        self.assertEqual(r_prod.den, 6)
        r_scaled = 3 * r1
        self.assertEqual(r_scaled.den, 2)
        r_scaled_zeta = z * r1
        self.assertEqual(r_scaled_zeta.den, 2)
        r1_inv = r1.inverse()
        self.assertEqual(r1 * r1_inv, RationalZetaP(one, 1))
        self.assertEqual(r1 + 1, RationalZetaP(z + ZetaP.from_int(2, p), 2))
        self.assertEqual(r1 - 1, RationalZetaP(z - ZetaP.from_int(2, p), 2))
        self.assertEqual(r1 * 2, RationalZetaP(z, 1))
        self.assertEqual(r1 + one, RationalZetaP(z + ZetaP.from_int(2, p), 2))
        self.assertEqual(r1 - one, RationalZetaP(z - ZetaP.from_int(2, p), 2))
        self.assertEqual(r1 * one, r1)
        self.assertEqual(-r1, RationalZetaP(-z, 2))
        self.assertEqual(r1.__rmul__("not_valid"), NotImplemented)

    def test_projective_scaling_cancellation(self):
        p = 5
        psi = StateZetaP.basis(0, 2, p)
        psi_scaled = StateZetaP([ZetaP.from_int(3, p), ZetaP.zero(p)], p)
        prob_orig = projective_born_probability(psi, 0)
        prob_scaled = projective_born_probability(psi_scaled, 0)
        self.assertEqual(prob_orig, (1, 1))
        self.assertEqual(prob_scaled, (1, 1))

    def test_cayley_unitarity(self):
        p = 5
        z = ZetaP.zero(p)
        o = ZetaP.one(p)
        H = MatrixZetaP(2, 2, [[z, o], [-o, z]], p)
        res = cayley_evolution(H)
        self.assertIsInstance(res, tuple)
        U_num, scale_norm = res
        U_dag_U = U_num.dagger() * U_num
        expected = MatrixZetaP(2, 2, [[ZetaP.from_int(scale_norm if i == j else 0, p) for j in range(2)] for i in range(2)], p)
        self.assertEqual(U_dag_U, expected)


class TestAdversarial(unittest.TestCase):
    def test_non_prime_rejection(self):
        with self.assertRaises(ValueError):
            ZetaP(4, (1, 0, 0))
        with self.assertRaises(ValueError):
            ZetaP(1, ())

    def test_non_unit_inverse_raises(self):
        non_unit = ZetaP(5, (2, 0, 0, 0))
        with self.assertRaises(NonUnitError):
            non_unit.inverse()

    def test_exact_div_zero_error(self):
        p = 5
        a = ZetaP.one(p)
        z = ZetaP.zero(p)
        with self.assertRaises(ZeroDivisionError):
            a.exact_div(z)

    def test_field_inverse_zero_error(self):
        p = 5
        z = ZetaP.zero(p)
        with self.assertRaises(ZeroDivisionError):
            z.field_inverse()
        rz = RationalZetaP(z, 1)
        with self.assertRaises(ZeroDivisionError):
            rz.inverse()

    def test_hadamard_obstruction(self):
        obs = hadamard(5)
        self.assertIsInstance(obs, Obstruction)
        self.assertEqual(obs.primitive, "hadamard")
        self.assertIn("Z[zeta_8]", obs.ring)

    def test_continuous_barrier_obstruction(self):
        cb = ContinuousBarrier(1.0, 2.0)
        obs = transmission_coefficient(cb, ZetaP.zero(5))
        self.assertIsInstance(obs, Obstruction)
        self.assertEqual(obs.primitive, "transmission_coefficient")
        obs_exact = transmission_coefficient_exact(cb, ZetaP.zero(5))
        self.assertIsInstance(obs_exact, Obstruction)

    def test_continuous_adiabatic_obstruction(self):
        cs = ContinuousSchedule(10.0)
        H = MatrixZetaP.identity(2, 5)
        obs = continuous_adiabatic(H, cs)
        self.assertIsInstance(obs, Obstruction)
        self.assertEqual(obs.primitive, "adiabatic_evolution")

    def test_metaheuristic_obstruction(self):
        obs = quantum_inspired_metaheuristic()
        self.assertIsInstance(obs, Obstruction)
        self.assertEqual(obs.primitive, "swarm")

    def test_visibility_non_unit_norm_obstruction(self):
        p = 5
        s1 = StateZetaP([ZetaP.from_int(2, p)], p)
        s2 = StateZetaP([ZetaP.one(p)], p)
        v_obs = visibility(s1, s2)
        self.assertIsInstance(v_obs, Obstruction)
        self.assertEqual(v_obs.primitive, "visibility")

    def test_non_anti_hermitian_cayley_obstruction(self):
        p = 5
        H_not_anti = MatrixZetaP.identity(2, p)
        obs = cayley_evolution(H_not_anti)
        self.assertIsInstance(obs, Obstruction)
        self.assertEqual(obs.primitive, "cayley_evolution")

    def test_singular_cayley_resolvent_obstruction(self):
        p = 5
        H_sing = MatrixZetaP(2, 2, [[-ZetaP.one(p), ZetaP.zero(p)], [ZetaP.zero(p), -ZetaP.one(p)]], p)
        obs = cayley_evolution(H_sing)
        self.assertIsInstance(obs, Obstruction)
        self.assertEqual(obs.value, "singular_cayley_resolvent")

    def test_projective_born_zero_state_error(self):
        p = 5
        s_zero = StateZetaP.zero(2, p)
        with self.assertRaises(StateNormError):
            projective_born_probability(s_zero, 0)
        with self.assertRaises(StateNormError):
            exact_renyi_purity(s_zero, 1, 2)


class TestEdge(unittest.TestCase):
    def test_is_prime_branches(self):
        self.assertFalse(is_prime(-1))
        self.assertFalse(is_prime(0))
        self.assertFalse(is_prime(1))
        self.assertTrue(is_prime(2))
        self.assertTrue(is_prime(3))
        self.assertFalse(is_prime(4))
        self.assertFalse(is_prime(9))
        self.assertTrue(is_prime(5))
        self.assertFalse(is_prime(25))
        self.assertTrue(is_prime(29))

    def test_legendre_symbol_zero(self):
        self.assertEqual(legendre_symbol(0, 5), 0)
        self.assertEqual(legendre_symbol(5, 5), 0)
        self.assertEqual(legendre_symbol(1, 5), 1)
        self.assertEqual(legendre_symbol(2, 5), -1)

    def test_cyclotomic_polynomial(self):
        self.assertEqual(cyclotomic_polynomial_prime(3), [1, 1, 1])

    def test_convolution_empty(self):
        self.assertEqual(convolution([], [1, 2]), [])
        self.assertEqual(convolution([1, 2], []), [])

    def test_reduce_edge_cases(self):
        p = 5
        red = ZetaP.reduce([1], p)
        self.assertEqual(red, [1, 0, 0, 0])

    def test_zeta_powers(self):
        p = 5
        self.assertEqual(ZetaP.zeta_power(0, p), ZetaP.one(p))
        self.assertEqual(ZetaP.zeta_power(1, p), ZetaP.zeta(p))
        self.assertEqual(ZetaP.zeta_power(4, p), ZetaP(p, (-1, -1, -1, -1)))
        self.assertEqual(ZetaP.zeta_power(-1, p), ZetaP.zeta_power(4, p))

    def test_zeta_pow_and_rmul(self):
        p = 5
        a = ZetaP(p, (1, 1, 0, 0))
        self.assertEqual(a.pow(0), ZetaP.one(p))
        self.assertEqual(a.pow(1), a)
        self.assertEqual(a.pow(2), a * a)
        self.assertEqual(a ** 2, a * a)
        self.assertEqual(3 * a, a * 3)

    def test_gauss_sum_identities(self):
        for prime_val in (3, 5, 7, 11, 13):
            g = ZetaP.gauss_sum(prime_val)
            self.assertTrue(g.verify_gauss_sum())

    def test_minimal_dimensions_and_pivoting(self):
        p = 5
        m1 = MatrixZetaP(1, 1, [[ZetaP.from_int(3, p)]], p)
        self.assertEqual(m1.det(), ZetaP.from_int(3, p))
        self.assertEqual(m1.adjugate().entries[0][0], ZetaP.one(p))

        with self.assertRaises(DimensionMismatchError):
            bareiss_det([])

        z = ZetaP.zero(p)
        o = ZetaP.one(p)
        m_swap = MatrixZetaP(2, 2, [[z, o], [o, z]], p)
        self.assertEqual(m_swap.det(), -o)

        m_sing = MatrixZetaP(2, 2, [[z, o], [z, o]], p)
        self.assertEqual(m_sing.det(), z)

    def test_matrix_rank_empty_and_zero_middle_column_pivot(self):
        p = 5
        z = ZetaP.zero(p)
        o = ZetaP.one(p)
        self.assertEqual(matrix_rank_over_field([], p), 0)
        self.assertEqual(matrix_rank_over_field([[]], p), 0)

        grid = [
            [o, z, ZetaP.from_int(2, p)],
            [z, z, ZetaP.from_int(3, p)]
        ]
        rank = matrix_rank_over_field(grid, p)
        self.assertEqual(rank, 2)

    def test_type_and_equality_branches(self):
        p = 5
        z = ZetaP.one(p)
        self.assertFalse(z == "not_a_zeta")
        rz = RationalZetaP(z, -2)
        self.assertEqual(rz.den, 2)
        self.assertFalse(rz == "not_a_rat")
        m = MatrixZetaP.identity(2, p)
        self.assertFalse(m == "not_a_mat")
        m_rect = MatrixZetaP.zero(2, 3, p)
        self.assertFalse(m_rect.is_unitary())

    def test_reprs(self):
        p = 5
        z = ZetaP.one(p)
        self.assertIn("ZetaP", repr(z))
        rz = RationalZetaP(z, 2)
        self.assertIn("RationalZetaP", repr(rz))
        self.assertEqual(rz.to_tuple(), (z.coeffs, 2))
        f_proj = fourier_gate_projective(p)
        self.assertIn("ProjectiveUnitaryZetaP", repr(f_proj))
        tab = StabilizerTableauZetaP.zero_state(p, 2)
        self.assertIn("StabilizerTableauZetaP", repr(tab))
        obs = Obstruction("p", "v", "r", "m")
        self.assertIn("Obstruction", repr(obs))


class TestUnit(unittest.TestCase):
    def test_amplitude(self):
        p = 5
        s = StateZetaP.basis(1, 3, p)
        self.assertEqual(amplitude(s, 1), ZetaP.one(p))
        self.assertEqual(amplitude(s, 0), ZetaP.zero(p))

    def test_state_zero(self):
        p = 5
        sz = StateZetaP.zero(3, p)
        self.assertEqual(sz.vector, [ZetaP.zero(p)] * 3)

    def test_superposition_and_inner_product(self):
        p = 5
        s0 = StateZetaP.basis(0, 2, p)
        s1 = StateZetaP.basis(1, 2, p)
        sup = superpose(s0, s1, ZetaP.one(p), ZetaP.one(p))
        self.assertEqual(sup.vector, [ZetaP.one(p), ZetaP.one(p)])
        self.assertEqual(inner_product(s0, s1), ZetaP.zero(p))
        self.assertEqual(inner_product(s0, s0), ZetaP.one(p))

    def test_elementary_gates(self):
        p = 5
        px = pauli_x(p)
        pz = pauli_z(p)
        c = cnot(p)
        ph = phase(1, p)
        self.assertTrue(px.matrix.is_unitary())
        self.assertTrue(pz.matrix.is_unitary())
        self.assertTrue(c.matrix.is_unitary())
        self.assertTrue(ph.matrix.is_unitary())

    def test_matrix_vector_multiplication(self):
        p = 5
        px = pauli_x(p)
        v = [ZetaP.one(p), ZetaP.zero(p)]
        applied = px.matrix.apply_to_vector(v)
        self.assertEqual(applied, [ZetaP.zero(p), ZetaP.one(p)])

    def test_matrix_zero_and_transpose(self):
        p = 5
        z_mat = MatrixZetaP.zero(2, 3, p)
        self.assertEqual(z_mat.rows, 2)
        self.assertEqual(z_mat.cols, 3)
        self.assertEqual(z_mat.transpose().rows, 3)

    def test_bareiss_det(self):
        p = 5
        o = ZetaP.one(p)
        entries = [[ZetaP.from_int(2, p), o], [o, ZetaP.from_int(3, p)]]
        det_val = bareiss_det(entries)
        self.assertEqual(det_val, ZetaP.from_int(5, p))

    def test_born_probabilities(self):
        p = 5
        s = StateZetaP.basis(1, 2, p)
        self.assertEqual(born_probability(s, 1), ZetaP.one(p))
        self.assertEqual(born_probability(s, 0), ZetaP.zero(p))
        self.assertEqual(sum_born_probabilities(s), ZetaP.one(p))
        proj = project(s, 1)
        self.assertEqual(proj.vector, s.vector)

    def test_unitary_dagger(self):
        p = 5
        pz = pauli_z(p)
        self.assertEqual(pz.dagger().matrix, pz.matrix.dagger())

    def test_visibility_unit_norm_success(self):
        p = 5
        s0 = StateZetaP.basis(0, 2, p)
        v = visibility(s0, s0)
        self.assertEqual(v, ZetaP.one(p))

    def test_projective_fourier_and_hadamard(self):
        p = 3
        fg = fourier_gate_projective(p)
        hg = hadamard_projective(p)
        self.assertEqual(fg.scale_norm, 3)
        self.assertEqual(hg.scale_norm, 3)
        composed = fg.compose(fg.dagger())
        self.assertEqual(composed.scale_norm, 9)

    def test_renyi_purity_product_state(self):
        p = 5
        prod_state = StateZetaP([ZetaP.one(p), ZetaP.zero(p), ZetaP.zero(p), ZetaP.zero(p)], p)
        purity = exact_renyi_purity(prod_state, 2, 2, k=2)
        self.assertEqual(purity, (1, 1))

    def test_stabilizer_tableau_elementary_ops(self):
        p = 3
        tab = StabilizerTableauZetaP.zero_state(p, 2)
        tab.apply_x(0)
        self.assertEqual(tab.phases[0], 1)
        tab.apply_z(0)
        tab.apply_fourier(0)
        tab.apply_cnot(0, 1)


class TestIntegration(unittest.TestCase):
    def test_circuit_evolution_and_measurement(self):
        p = 5
        s0 = StateZetaP.basis(0, 2, p)
        px = pauli_x(p)
        s1 = px.apply(s0)
        self.assertEqual(s1.vector, StateZetaP.basis(1, 2, p).vector)
        self.assertEqual(born_probability(s1, 1), ZetaP.one(p))

    def test_discrete_evolution_schedule(self):
        p = 5
        px = pauli_x(p)
        schedule = [px, px]
        U_total = discrete_evolution(schedule)
        s0 = StateZetaP.basis(0, 2, p)
        s_final = U_total.apply(s0)
        self.assertEqual(s_final.vector, s0.vector)

    def test_projective_circuit_measurement(self):
        p = 3
        s0 = StateZetaP.basis(0, p, p)
        F_proj = fourier_gate_projective(p)
        s_fourier = F_proj.apply(s0)
        for outcome in range(p):
            prob = projective_born_probability(s_fourier, outcome)
            self.assertEqual(prob, (1, 3))

    def test_projective_born_and_renyi_non_constant_coefficients(self):
        p = 5
        zeta = ZetaP.zeta(p)
        vec = [zeta, ZetaP.zero(p)]
        state = StateZetaP(vec, p)
        prob = projective_born_probability(state, 0)
        self.assertEqual(prob, (1, 1))

        purity = exact_renyi_purity(state, 1, 2, k=2)
        self.assertEqual(purity, (1, 1))

    def test_total_reflection_tunneling_exact(self):
        p = 5
        barrier = DiscreteBarrier(
            num_sites=1,
            potential=[ZetaP.one(p)],
            hopping=ZetaP.one(p)
        )
        t_refl = transmission_coefficient_exact(barrier, ZetaP.one(p))
        self.assertIsInstance(t_refl, Obstruction)
        self.assertEqual(t_refl.value, "0")

    def test_symplectic_tableau_vs_dense_kronecker_equivalence(self):
        p = 3
        tab = StabilizerTableauZetaP.zero_state(p, 2)
        tab.apply_fourier(0)
        tab.apply_cnot(0, 1)

        s0 = StateZetaP.basis(0, p, p)
        F_dense = fourier_gate_projective(p).matrix
        I_dense = MatrixZetaP.identity(p, p)
        F_kron_I = F_dense.kron(I_dense)

        psi_fourier = StateZetaP(F_kron_I.apply_to_vector(s0.vector + [ZetaP.zero(p)] * 6), p)
        self.assertEqual(psi_fourier.dimension, 9)

        cnot_entries = [[ZetaP.zero(p) for _ in range(9)] for _ in range(9)]
        for i in range(p):
            for j in range(p):
                in_idx = i * p + j
                out_idx = i * p + ((j + i) % p)
                cnot_entries[out_idx][in_idx] = ZetaP.one(p)
        CNOT_dense = MatrixZetaP(9, 9, cnot_entries, p)

        bell_dense = CNOT_dense.apply_to_vector(psi_fourier.vector)
        bell_state = StateZetaP(bell_dense, p)

        rank = schmidt_rank(bell_state, (3, 3))
        self.assertEqual(rank, 3)

        x_entries = [[ZetaP.zero(p) for _ in range(p)] for _ in range(p)]
        z_entries = [[ZetaP.zero(p) for _ in range(p)] for _ in range(p)]
        for j in range(p):
            x_entries[(j + 1) % p][j] = ZetaP.one(p)
            z_entries[j][j] = ZetaP.zeta_power(j, p)
        X = MatrixZetaP(p, p, x_entries, p)
        Z = MatrixZetaP(p, p, z_entries, p)
        I = MatrixZetaP.identity(p, p)

        op1 = X.kron(X)
        op2 = Z.kron(Z.dagger())

        self.assertEqual(op1.apply_to_vector(bell_state.vector), bell_state.vector)
        self.assertEqual(op2.apply_to_vector(bell_state.vector), bell_state.vector)


class TestEndToEnd(unittest.TestCase):
    def test_bell_state_schmidt_rank_and_renyi_purity(self):
        p = 5
        o = ZetaP.one(p)
        z = ZetaP.zero(p)
        v_bell = [o, z, z, o]
        bell_state = StateZetaP(v_bell, p)

        rank = schmidt_rank(bell_state, (2, 2))
        self.assertEqual(rank, 2)

        obs = normalized_schmidt_coefficients(bell_state, (2, 2))
        self.assertIsInstance(obs, Obstruction)
        self.assertEqual(obs.primitive, "schmidt_coefficients")

        purity = exact_renyi_purity(bell_state, 2, 2, k=2)
        self.assertEqual(purity, (1, 2))

    def test_discrete_tight_binding_tunneling_unit(self):
        p = 5
        barrier = DiscreteBarrier(
            num_sites=2,
            potential=[ZetaP.zero(5), ZetaP.zero(5)],
            hopping=ZetaP.one(5)
        )
        trans = transmission_coefficient(barrier, ZetaP.zero(5))
        self.assertIsInstance(trans, ZetaP)
        self.assertEqual(trans, ZetaP.one(5))
        trans_exact = transmission_coefficient_exact(barrier, ZetaP.zero(5))
        self.assertIsInstance(trans_exact, RationalZetaP)
        self.assertEqual(trans_exact, RationalZetaP(ZetaP.one(5), 1))

    def test_m5_non_unit_tight_binding_barrier_and_field_resolution(self):
        p = 5
        zeta = ZetaP.zeta(p)
        barrier = DiscreteBarrier(
            num_sites=2,
            potential=[ZetaP.zero(p), ZetaP.zero(p)],
            hopping=ZetaP.one(p)
        )
        t_obs = transmission_coefficient(barrier, zeta)
        self.assertIsInstance(t_obs, Obstruction)
        self.assertIn("only when |T_11|^2 is a unit", t_obs.message)

        t_field = transmission_coefficient_exact(barrier, zeta)
        self.assertIsInstance(t_field, RationalZetaP)
        self.assertEqual(t_field.p, p)
        self.assertGreater(t_field.den, 0)

    def test_cayley_evolution_dynamics(self):
        p = 5
        z = ZetaP.zero(p)
        o = ZetaP.one(p)
        H = MatrixZetaP(2, 2, [[z, o], [-o, z]], p)
        res = cayley_evolution(H)
        self.assertIsInstance(res, tuple)
        U_num, scale_norm = res
        U_proj = ProjectiveUnitaryZetaP(U_num, scale_norm)
        s0 = StateZetaP.basis(0, 2, p)
        s_evolved = U_proj.apply(s0)
        p0 = projective_born_probability(s_evolved, 0)
        p1 = projective_born_probability(s_evolved, 1)
        self.assertEqual(p0[0] * p1[1] + p1[0] * p0[1], p0[1] * p1[1])

    def test_swarm_dynamics_step_and_collapse(self):
        p = 5
        px = pauli_x(p)
        s0 = StateZetaP.basis(0, 2, p)
        swarm = SwarmZetaP(s0, px, project)
        stepped = swarm.step()
        self.assertEqual(stepped.vector, StateZetaP.basis(1, 2, p).vector)
        collapsed = swarm.collapse_to(0)
        self.assertEqual(collapsed.vector, StateZetaP.basis(0, 2, p).vector)


class TestTuringElevations(unittest.TestCase):
    """New elevation tests verifying explicit exception hierarchies and stabilizer measurements."""

    def test_custom_exception_hierarchy(self):
        # RingError on prime mismatch
        p5 = ZetaP.one(5)
        p3 = ZetaP.one(3)
        with self.assertRaises(RingError):
            _ = p5 + p3
        with self.assertRaises(RingError):
            _ = p5 - p3
        with self.assertRaises(RingError):
            _ = p5 * p3

        # DimensionMismatchError
        s2 = StateZetaP.basis(0, 2, 5)
        s3 = StateZetaP.basis(0, 3, 5)
        with self.assertRaises(DimensionMismatchError):
            _ = inner_product(s2, s3)
        with self.assertRaises(DimensionMismatchError):
            _ = superpose(s2, s3, p5, p5)
        with self.assertRaises(DimensionMismatchError):
            StateZetaP([], 5)
        with self.assertRaises(DimensionMismatchError):
            StateZetaP.zero(0, 5)
        with self.assertRaises(DimensionMismatchError):
            StateZetaP.basis(5, 2, 5)
        with self.assertRaises(DimensionMismatchError):
            amplitude(s2, 10)

        # State / Unitary representation and edge checks
        self.assertIn("StateZetaP", repr(s2))
        px = pauli_x(5)
        self.assertIn("UnitaryZetaP", repr(px))

        # Unitary dimension and prime errors
        with self.assertRaises(DimensionMismatchError):
            px.compose(cnot(5))
        with self.assertRaises(RingError):
            px.compose(pauli_x(3))
        with self.assertRaises(DimensionMismatchError):
            px.apply(s3)
        with self.assertRaises(RingError):
            px.apply(StateZetaP.basis(0, 2, 3))

        # Projective unitary scale_norm != 0 and square requirement
        m_rect = MatrixZetaP.zero(2, 3, 5)
        with self.assertRaises(DimensionMismatchError):
            ProjectiveUnitaryZetaP(m_rect, 1)
        with self.assertRaises(ValueError):
            ProjectiveUnitaryZetaP(MatrixZetaP.identity(2, 5), 0)

        # Matrix dimension and prime errors
        m2 = MatrixZetaP.identity(2, 5)
        m3 = MatrixZetaP.identity(3, 5)
        with self.assertRaises(DimensionMismatchError):
            _ = m2 + m3
        with self.assertRaises(RingError):
            _ = m2 + MatrixZetaP.identity(2, 3)
        with self.assertRaises(DimensionMismatchError):
            _ = m2 * m3
        with self.assertRaises(RingError):
            _ = m2 * MatrixZetaP.identity(2, 3)
        with self.assertRaises(DimensionMismatchError):
            m2.apply_to_vector([p5])
        with self.assertRaises(RingError):
            m2.apply_to_vector([p3, p3])
        with self.assertRaises(DimensionMismatchError):
            m_rect.trace()
        with self.assertRaises(DimensionMismatchError):
            m_rect.pow(2)
        with self.assertRaises(ValueError):
            m2.pow(-1)
        with self.assertRaises(DimensionMismatchError):
            m_rect.adjugate()
        with self.assertRaises(RingError):
            m2.kron(MatrixZetaP.identity(2, 3))
        self.assertIn("MatrixZetaP", repr(m2))

        # ZetaP power and galois conjugate errors
        with self.assertRaises(ValueError):
            p5.pow(-1)
        with self.assertRaises(ValueError):
            p5.galois_conjugate(5)
        with self.assertRaises(DimensionMismatchError):
            ZetaP(5, (1, 2))

        # Rational field mismatch
        r5 = RationalZetaP(p5, 1)
        r3 = RationalZetaP(p3, 1)
        with self.assertRaises(RingError):
            _ = r5 + r3
        with self.assertRaises(RingError):
            _ = r5 - r3
        with self.assertRaises(RingError):
            _ = r5 * r3

        # Swarm errors
        with self.assertRaises(DimensionMismatchError):
            SwarmZetaP(s3, px, project)
        with self.assertRaises(RingError):
            SwarmZetaP(StateZetaP.basis(0, 2, 3), px, project)

        # Discrete barrier hopping unit check
        barrier_bad = DiscreteBarrier(1, [ZetaP.zero(5)], ZetaP.from_int(2, 5))
        with self.assertRaises(NonUnitError):
            transmission_coefficient(barrier_bad, ZetaP.zero(5))
        with self.assertRaises(NonUnitError):
            transmission_coefficient_exact(barrier_bad, ZetaP.zero(5))

    def test_stabilizer_measurement_deterministic(self):
        p = 3
        tab = StabilizerTableauZetaP.zero_state(p, 2)
        # In zero_state |00>, measuring qudit 0 in Z basis must deterministically yield 0
        outcome, is_det = tab.measure_z(0)
        self.assertTrue(is_det)
        self.assertEqual(outcome, 0)

        # After applying X gate, measuring qudit 0 must deterministically yield 1
        tab.apply_x(0)
        outcome, is_det = tab.measure_z(0)
        self.assertTrue(is_det)
        self.assertEqual(outcome, 1)

    def test_stabilizer_measurement_random_projection(self):
        p = 3
        tab = StabilizerTableauZetaP.zero_state(p, 2)
        # Apply Fourier to qudit 0 -> |+> state (X eigenstate)
        tab.apply_fourier(0)

        # Measuring qudit 0 in Z basis is now random (non-deterministic)
        outcome, is_det = tab.measure_z(0, outcome_override=2)
        self.assertFalse(is_det)
        self.assertEqual(outcome, 2)

        # Subsequent measurement on the collapsed state must now be deterministic
        outcome2, is_det2 = tab.measure_z(0)
        self.assertTrue(is_det2)
        self.assertEqual(outcome2, 2)


if __name__ == "__main__":
    unittest.main()
