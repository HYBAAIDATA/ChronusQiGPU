import numpy as np
import pytest

pytestmark = pytest.mark.real
from hypothesis import given, settings, strategies as st
from chronus.acceleration.fourier import MAX_LENGTH, qft


def direct(x, inverse=False):
    n = len(x)
    sign = -1 if inverse else 1
    return np.exp(sign * 2j * np.pi * np.outer(np.arange(n), np.arange(n)) / n) @ x / np.sqrt(n)


class TestInvariant:
    def test_small_basis_exhaustive_and_inverse(self):
        for n in (1, 2, 4, 8, 16):
            for i in range(n):
                x = np.eye(n, dtype=complex)[i]
                np.testing.assert_allclose(qft(x), direct(x), atol=2e-14)
                np.testing.assert_allclose(qft(qft(x), inverse=True), x, atol=2e-14)


class TestProperty:
    @settings(max_examples=100, deadline=None, derandomize=True)
    @given(st.lists(st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False), min_size=8, max_size=8))
    def test_norm_and_linearity(self, values):
        x = np.array(values)
        np.testing.assert_allclose(np.linalg.norm(qft(x)), np.linalg.norm(x), rtol=1e-12, atol=1e-12)
        np.testing.assert_allclose(qft(3*x), 3*qft(x), rtol=1e-12, atol=1e-12)


class TestAdversarial:
    @pytest.mark.parametrize('values', [[float('nan')], [float('inf')], ['bad'], [10**1000], np.ones(8192)])
    def test_invalid_or_excessive_inputs_are_rejected(self, values):
        with pytest.raises(ValueError):
            qft(values)

    def test_invalid_flag_and_overflow(self):
        with pytest.raises(ValueError):
            qft([1], inverse=1)
        with np.errstate(over='ignore', invalid='ignore'):
            with pytest.raises(ValueError, match='overflowed'):
                qft([1e308]*4)


class TestEdge:
    @pytest.mark.parametrize('values', [[], [1, 2, 3], [[1, 2]], None])
    def test_refusal(self, values):
        with pytest.raises(ValueError):
            qft(values)

    def test_singleton_and_limit(self):
        np.testing.assert_array_equal(qft([2j]), [2j])
        assert qft(np.zeros(MAX_LENGTH)).size == MAX_LENGTH


class TestUnit:
    def test_known_transform(self):
        np.testing.assert_allclose(qft([1, 0, 0, 0]), [0.5]*4, atol=1e-15)
        np.testing.assert_allclose(qft([0, 1, 0, 0]), [0.5, 0.5j, -0.5, -0.5j], atol=1e-15)


class TestIntegration:
    def test_transform_convolution(self):
        x = np.array([1., 2., 3., 4.]); y = np.array([3., -1., 2., 0.])
        actual = qft(qft(x) * qft(y), inverse=True) * np.sqrt(len(x))
        expected = np.array([sum(x[j]*y[(i-j)%4] for j in range(4)) for i in range(4)])
        np.testing.assert_allclose(actual, expected, atol=1e-12)


class TestEndToEnd:
    def test_user_public_api_processing_and_recovery(self):
        data = [0.25, -0.5, 0.75, 1.0, -0.25, 0.0, 0.125, -1.0]
        transformed = qft(data)
        recovered = qft(transformed, inverse=True)
        assert transformed.shape == (8,)
        np.testing.assert_allclose(recovered, data, atol=1e-12)
