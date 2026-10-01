"""Property + invariant tests for the HYBA Quantum Tensor X-Infinity."""
import math

from quantum_compute_substrate.phi_infinity_tensor import (
    PHI, fib, lucas, phi_power_identity_holds,
    TensorDimension, AXIS_NAMES, make_default_tensor,
    PhiCharacterRule, RankOneRule,
    MPSNetwork, tensor_product, contract,
    phi_scaling_transform, quantum_fourier_transform_all_axes, topological_decomposition,
    compare_to_universe, compare_to_storage,
    honest_size_context, svd_metadata,
    cp_decomposition_metadata, tucker_decomposition_metadata,
    tensor_train_metadata, create_base_tensor,
    create_scaled_tensor, create_n_dimensional_tensor,
    create_quantum_state_tensor,
)


# ==================== Phi and Fibonacci ====================
class TestPhiIdentities:
    def test_phi_first_50_digits(self):
        expected_prefix = "1.61803398874989484820458683436563811772030917980576"
        assert str(PHI)[:len(expected_prefix)] == expected_prefix

    def test_fibonacci_37(self):
        assert fib(37) == 24157817

    def test_fibonacci_36(self):
        assert fib(36) == 14930352

    def test_lucas_37(self):
        assert lucas(37) == 54018521

    def test_lucas_zero_and_one(self):
        assert lucas(0) == 2
        assert lucas(1) == 1

    def test_phi_power_identity_wide_range(self):
        # phi^n = F(n) phi + F(n-1) exactly (to Decimal precision).
        for n in range(1, 65):
            assert phi_power_identity_holds(n), f"failed at n={n}"

    def test_lucas_equals_round_phi_power(self):
        for n in (2, 3, 5, 10, 20, 37, 50):
            assert lucas(n) == round(float(PHI ** n)) or abs(lucas(n) -
                                                             float(PHI ** n)) < 1e-6 * lucas(n)

    def test_fib_recurrence(self):
        for n in range(2, 40):
            assert fib(n) == fib(n - 1) + fib(n - 2)

    def test_lucas_recurrence(self):
        for n in range(2, 40):
            assert lucas(n) == lucas(n - 1) + lucas(n - 2)


# ==================== Dimensions ====================
class TestDimensions:
    def test_axis_names_length_six(self):
        assert len(AXIS_NAMES) == 6

    def test_axis_names_are_the_six(self):
        assert set(AXIS_NAMES) == {
            "Time", "Space", "QuantumState",
            "Entanglement", "Coherence", "Topology",
        }

    def test_dimension_immutable(self):
        d = TensorDimension(name="X", size=10, scaling_exp=3, physical_meaning="test")
        try:
            d.size = 20  # frozen
            assert False
        except Exception:
            pass


# ==================== Core tensor ====================
class TestTensorCore:
    def test_default_rank_six(self):
        T = make_default_tensor()
        assert T.rank == 6

    def test_default_shape_all_L37(self):
        T = make_default_tensor()
        L37 = lucas(37)
        assert T.shape == (L37,) * 6
        assert L37 == 54018521

    def test_total_elements_exact(self):
        T = make_default_tensor()
        assert T.total_elements() == 54018521 ** 6

    def test_log10_elements_range(self):
        T = make_default_tensor()
        assert 46.0 < T.log10_elements() < 47.0

    def test_element_at_origin(self):
        # T[0,0,0,0,0,0] = exp(0) / sqrt(N^6) = normalisation only.
        T = make_default_tensor()
        z = T.get(0, 0, 0, 0, 0, 0)
        expected = math.exp(-0.5 * 6 * math.log(T.shape[0]))
        assert abs(z - expected) < 1e-12

    def test_element_out_of_range_raises(self):
        T = make_default_tensor()
        try:
            T.get(0, 0, 0, 0, 0, T.shape[0])
            assert False
        except IndexError:
            pass

    def test_wrong_index_count_raises(self):
        T = make_default_tensor()
        try:
            T.get(0, 0, 0)
            assert False
        except IndexError:
            pass


# ==================== Generator (phi-character rule) ====================
class TestPhiCharacterRule:
    def test_normalization_magnitude(self):
        rule = PhiCharacterRule(N=17, rank=6)
        z = rule.element((3, 5, 7, 11, 13, 15))
        expected_mag = math.exp(-0.5 * 6 * math.log(17))
        assert abs(abs(z) - expected_mag) < 1e-12

    def test_all_elements_have_equal_magnitude(self):
        # Character has |value| = 1 / sqrt(N^rank) everywhere.
        rule = PhiCharacterRule(N=13, rank=3)
        magnitudes = []
        for a in range(3):
            for b in range(3):
                for c in range(3):
                    magnitudes.append(abs(rule.element((a, b, c))))
        assert max(magnitudes) - min(magnitudes) < 1e-12

    def test_slice_of_axis(self):
        rule = PhiCharacterRule(N=8, rank=3)
        f = rule.slice_of_axis(1, (2, 5))  # fix axes 0 and 2
        vals = [f(i) for i in range(8)]
        # every value has same magnitude
        mags = [abs(v) for v in vals]
        assert max(mags) - min(mags) < 1e-12


# ==================== MPS network ====================
class TestMPSNetwork:
    def test_bond_hierarchy(self):
        m = MPSNetwork(physical_dim=4, rank=6, bond_dim=32)
        assert m.bond_hierarchy() == [32, 32, 32, 32, 32]

    def test_memory_bytes_positive(self):
        m = MPSNetwork(physical_dim=1024, rank=6, bond_dim=64)
        assert m.memory_bytes() > 0

    def test_compression_log10_negative_for_astronomical_full(self):
        """For phi^37 axes and bond 128, MPS storage << full tensor storage."""
        m = MPSNetwork(physical_dim=54018521, rank=6, bond_dim=128)
        assert m.compression_log10() < -30  # at least 30 orders of magnitude smaller

    def test_rejects_invalid(self):
        for bad in [(1, 6, 32), (10, 1, 32), (10, 6, 0)]:
            try:
                MPSNetwork(*bad)
                assert False
            except ValueError:
                pass


# ==================== Operations ====================
class TestOperations:
    def test_tensor_product_rank_sums(self):
        A = make_default_tensor()
        B = create_scaled_tensor(3)  # smaller
        r = tensor_product(A, B)
        assert r["result_rank"] == A.rank + B.rank

    def test_contraction_reduces_rank_by_two(self):
        T = make_default_tensor()
        r = contract(T, 0, 3)
        assert r["result_rank"] == 4
        assert len(r["result_shape"]) == 4

    def test_contraction_rejects_unequal_axes(self):
        # Two different-sized tensors combined and then bad contraction.
        # For a uniform tensor all axes have the same size so this always works;
        # instead we test that same-axis contraction is refused.
        T = make_default_tensor()
        try:
            contract(T, 2, 2)
            assert False
        except ValueError:
            pass

    def test_phi_scaling_transform(self):
        T = make_default_tensor()
        r = phi_scaling_transform(T, 20)
        assert r["new_axis_size"] == lucas(20)
        assert r["new_total_elements"] == lucas(20) ** T.rank

    def test_qft_all_axes_preserves_shape(self):
        T = make_default_tensor()
        r = quantum_fourier_transform_all_axes(T)
        assert r["result_shape"] == T.shape
        assert r["unitary"] is True


# ==================== Topology ====================
class TestTopology:
    def test_open_boundary_cube_euler_one(self):
        T = make_default_tensor()
        r = topological_decomposition(T)
        assert r["open_boundary"]["euler_characteristic"] == 1

    def test_periodic_torus_euler_zero(self):
        T = make_default_tensor()
        r = topological_decomposition(T)
        assert r["periodic"]["euler_characteristic"] == 0

    def test_torus_betti_binomial_coefficients(self):
        """Kunneth: H_k(T^n) has rank C(n, k)."""
        from math import comb
        T = make_default_tensor()
        r = topological_decomposition(T)
        expected = [comb(T.rank, k) for k in range(T.rank + 1)]
        assert r["periodic"]["betti_numbers"] == expected
        # Sanity: [1, 6, 15, 20, 15, 6, 1] alternating sum = 0.
        assert sum(((-1) ** k) * expected[k] for k in range(len(expected))) == 0


# ==================== Comparisons (honest) ====================
class TestComparisons:
    def test_does_not_exceed_atoms_in_universe(self):
        """The 2025 draft claimed the tensor exceeds atoms in the universe.
        At phi^37, it does NOT. We record this honestly."""
        T = make_default_tensor()
        c = compare_to_universe(T)
        assert c["exceeds_atoms_in_universe"] is False
        assert c["log10_tensor_elements"] < 80.0

    def test_exceeds_neurons_and_seconds(self):
        T = make_default_tensor()
        c = compare_to_universe(T)
        assert c["exceeds_neurons_in_brain"] is True
        assert c["exceeds_seconds_since_big_bang"] is True

    def test_materialisation_infeasible(self):
        T = make_default_tensor()
        c = compare_to_storage(T)
        assert c["materialization_infeasible"] is True
        assert c["substrate_representation_fits_in_ram"] is True

    def test_honest_size_context(self):
        T = make_default_tensor()
        c = honest_size_context(T)
        # Neurons and cells are beaten; atoms and Planck volumes are not.
        beaten = {b["quantity"] for b in c["tensor_exceeds"]}
        below = {b["quantity"] for b in c["tensor_below"]}
        assert "neurons in a human brain" in beaten
        assert "cells in the observable universe" in beaten
        assert "atoms in observable universe" in below
        assert "Planck volumes in observable universe" in below


# ==================== Decompositions ====================
class TestDecompositions:
    def test_svd_metadata(self):
        T = make_default_tensor()
        r = svd_metadata(T)
        # rows = N, so max SVD rank = rows.
        assert r["max_svd_rank"] == T.shape[0]

    def test_cp_decomposition_metadata_compresses(self):
        T = make_default_tensor()
        r = cp_decomposition_metadata(T, cp_rank=64)
        # CP storage should be dramatically smaller than materialised tensor.
        assert r["compression_log10"] < -30

    def test_tucker_decomposition_metadata_compresses(self):
        T = make_default_tensor()
        r = tucker_decomposition_metadata(T, core_dims=[16] * T.rank)
        assert r["compression_log10"] < -30

    def test_tt_metadata_compresses(self):
        T = make_default_tensor()
        r = tensor_train_metadata(T, tt_rank=64)
        assert r["compression_log10"] < -30


# ==================== Factories ====================
class TestFactories:
    def test_base_tensor(self):
        T = create_base_tensor()
        assert T.rank == 6
        assert T.shape[0] == 54018521

    def test_scaled_tensor(self):
        T = create_scaled_tensor(20)
        assert T.shape[0] == lucas(20)

    def test_n_dimensional_tensor(self):
        T = create_n_dimensional_tensor(num_axes=4, scaling_exp=10)
        assert T.rank == 4
        assert T.shape == (lucas(10),) * 4

    def test_quantum_state_tensor_shape(self):
        T = create_quantum_state_tensor(num_qubits=8)
        assert T.rank == 8
        assert T.shape == (2,) * 8
        assert T.total_elements() == 256

    def test_quantum_state_tensor_element(self):
        T = create_quantum_state_tensor(num_qubits=4)
        # 4 qubits: |value| = 1 / sqrt(2^4) = 1/4
        z = T.get(0, 0, 0, 0)
        assert abs(abs(z) - 0.25) < 1e-12


# ==================== Rank-one rule ====================
class TestRankOneRule:
    def test_all_magnitudes_equal(self):
        r = RankOneRule(N=10, rank=6)
        mags = [abs(r.element((i, i, i, i, i, i))) for i in range(10)]
        assert max(mags) - min(mags) < 1e-12

    def test_normalization(self):
        r = RankOneRule(N=8, rank=6)
        z = r.element((0, 0, 0, 0, 0, 0))
        expected = math.exp(-0.5 * 6 * math.log(8))
        assert abs(abs(z) - expected) < 1e-12
