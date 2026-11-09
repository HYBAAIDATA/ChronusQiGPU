"""Bounded complex state normalization and unitary application.

Floating point tolerance is absolute 1e-10. Public inputs must already fit
memory: array conversion happens before dimensions can be checked.
"""

import numpy as np

MAX_DIMENSION = 256
TOLERANCE = 1e-10


def _array(value):
    try:
        out = np.asarray(value, dtype=np.complex128)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("expected finite numerical values") from exc
    if not np.isfinite(out).all():
        raise ValueError("expected finite numerical values")
    return out


def _vector(value):
    out = _array(value)
    if out.ndim != 1 or not 1 <= out.size <= MAX_DIMENSION:
        raise ValueError("state must be a vector with 1 to 256 entries")
    return out


def normalize(values):
    """Return a unit vector; reject zero, nonfinite, and oversized inputs."""
    state = _vector(values)
    # Scaling first prevents norm overflow for large finite coefficients.
    scale = float(np.max(np.abs(state)))
    if not np.isfinite(scale) or scale == 0:
        raise ValueError("state must have nonzero finite magnitude")
    scaled = state / scale
    return scaled / np.linalg.norm(scaled)


def apply_unitary(values, matrix):
    """Apply a bounded unitary matrix to an already normalized vector.

    Refuse if the state norm or U†U differs from the ideal by more than
    TOLERANCE. Validation is dense and accounts for the explicit matrix.
    """
    state = _vector(values)
    n = state.size
    if not np.isclose(np.linalg.norm(state), 1, rtol=0, atol=TOLERANCE):
        raise ValueError("state must have unit norm")
    unitary = _array(matrix)
    if unitary.shape != (n, n):
        raise ValueError("matrix must match state dimension")
    gram = unitary.conj().T @ unitary
    if not np.allclose(gram, np.eye(n), rtol=0, atol=TOLERANCE):
        raise ValueError("matrix must be unitary")
    result = unitary @ state
    if not np.isfinite(result).all():
        raise ValueError("application produced a nonfinite result")
    return result
