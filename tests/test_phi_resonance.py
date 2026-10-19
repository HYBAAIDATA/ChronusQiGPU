"""Discrete phi-resonance tests. Not a continuum claim."""
import numpy as np
from millennium.discrete.phi_resonance import (
    construct_T_tensor,
    phi_norm_ratio,
    r_phi,
    PHI,
)


def test_T_is_symmetric():
    T = construct_T_tensor()
    assert np.allclose(T, T.T)


def test_flat_returns_phi():
    T = construct_T_tensor()
    F = [np.zeros((2, 2), dtype=complex) for _ in range(3)]
    assert abs(phi_norm_ratio(F, T) - PHI) < 1e-9


def test_r_phi_bounded():
    T = construct_T_tensor()
    rng = np.random.default_rng(0)
    F_list = [[rng.normal(size=(2, 2)) + 1j * rng.normal(size=(2, 2)) for _ in range(3)] for _ in range(4)]
    r = r_phi(F_list, T)
    assert 0.0 <= r <= 1.0
