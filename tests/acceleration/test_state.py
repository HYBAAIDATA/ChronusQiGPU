import numpy as np
import pytest
from hypothesis import given, settings, strategies as st
from chronus.acceleration.state import MAX_DIMENSION, TOLERANCE, apply_unitary, normalize
from chronus.acceleration.fourier import qft


class TestInvariant:
    def test_basis_norm_and_identity_exhaustive_bounded(self):
        for n in range(1, 9):
            eye = np.eye(n, dtype=complex)
            for basis in eye:
                np.testing.assert_allclose(apply_unitary(basis, eye), basis, atol=TOLERANCE)
                np.testing.assert_allclose(np.linalg.norm(normalize(basis)), 1, atol=TOLERANCE)


class TestProperty:
    @settings(max_examples=100, deadline=None, derandomize=True)
    @given(st.lists(st.floats(min_value=-1e4, max_value=1e4, allow_nan=False, allow_infinity=False), min_size=4, max_size=4).filter(lambda x: any(v != 0 for v in x)))
    def test_scale_invariance_and_normalization(self, x):
        v = normalize(x)
        np.testing.assert_allclose(np.linalg.norm(v), 1, atol=TOLERANCE)
        np.testing.assert_allclose(normalize(3*np.asarray(x)), v, atol=TOLERANCE)


class TestAdversarial:
    @pytest.mark.parametrize('v', [[float('nan')], [float('inf')], ['bad'], [10**1000], np.ones(MAX_DIMENSION+1)])
    def test_bad_vectors(self, v):
        with pytest.raises(ValueError): normalize(v)

    def test_reject_nonunitary_nonfinite_and_incompatible_matrices(self):
        for m in ([[2]], [[float('nan')]], [[1, 0]], [['bad']]):
            with pytest.raises(ValueError): apply_unitary([1], m)

    def test_overflowing_complex_magnitude(self):
        with np.errstate(over='ignore', invalid='ignore'):
            with pytest.raises(ValueError): normalize([complex(1.7e308, 1.7e308)])


class TestEdge:
    @pytest.mark.parametrize('v', [[], [[1]], [0, 0], None])
    def test_empty_invalid_zero(self, v):
        with pytest.raises(ValueError): normalize(v)

    def test_large_finite_small_finite_and_limit(self):
        for v in ([1e300, 1e300], [1e-300, 1e-300], np.ones(MAX_DIMENSION)):
            np.testing.assert_allclose(np.linalg.norm(normalize(v)), 1, atol=TOLERANCE)

    def test_unnormalized(self):
        with pytest.raises(ValueError, match='unit norm'): apply_unitary([2], [[1]])


class TestUnit:
    def test_known_normalization_and_matrix(self):
        np.testing.assert_allclose(normalize([3, 4]), [0.6, 0.8])
        np.testing.assert_allclose(apply_unitary([1, 0], [[0, 1], [1, 0]]), [0, 1])


class TestIntegration:
    def test_state_with_fourier(self):
        x = normalize([1, 2, 3, 4]); n = len(x)
        basis = np.eye(n, dtype=complex)
        qft_matrix = np.column_stack([qft(col) for col in basis])
        np.testing.assert_allclose(apply_unitary(x, qft_matrix), qft(x), atol=TOLERANCE)


class TestEndToEnd:
    def test_public_api_prepare_transform_and_recover(self):
        prepared = normalize([3+4j, -2j])
        swap = [[0, 1], [1, 0]]
        recovered = apply_unitary(apply_unitary(prepared, swap), swap)
        np.testing.assert_allclose(recovered, prepared, atol=TOLERANCE)
